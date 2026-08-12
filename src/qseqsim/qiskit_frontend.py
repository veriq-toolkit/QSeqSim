"""Direct ``QuantumCircuit`` to QSeqSim IR frontend.

This module deliberately does not import or invoke Qiskit's OpenQASM exporter.
Control-flow block operands are mapped positionally through each enclosing
``CircuitInstruction`` before operations are lowered to global IR bit indices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit
from qiskit.circuit import (
    BreakLoopOp,
    ClassicalRegister,
    Clbit,
    ContinueLoopOp,
    ControlFlowOp,
    ForLoopOp,
    IfElseOp,
    Store,
    SwitchCaseOp,
    WhileLoopOp,
)

from .exceptions import UnsupportedQiskitFeatureError
from .parser import CQC, DQC, SQC, GateOp, mark_final_measurements


@dataclass(frozen=True)
class _BitFrame:
    qubits: dict[Any, int]
    clbits: dict[Any, int]


class QuantumCircuitParser:
    """Lower a Qiskit :class:`QuantumCircuit` directly to QSeqSim IR."""

    SUPPORTED_GATES = {
        "x", "y", "z", "h", "s", "sdg", "t", "tdg",
        "cx", "cz", "ccx", "mcx", "cswap", "swap", "id",
        "rx", "ry", "rz", "p", "measure",
    }

    def __init__(self, circuit: QuantumCircuit):
        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "QuantumCircuitParser expects qiskit.QuantumCircuit, "
                f"got {type(circuit).__name__}."
            )
        self.circuit = circuit
        self.global_num_qubits = circuit.num_qubits

    def parse(self) -> list:
        self._reject_circuit_features(self.circuit)
        frame = _BitFrame(
            {bit: self.circuit.find_bit(bit).index for bit in self.circuit.qubits},
            {bit: self.circuit.find_bit(bit).index for bit in self.circuit.clbits},
        )
        blocks = self._process_circuit(self.circuit, frame)
        mark_final_measurements(blocks)
        return blocks

    def _process_circuit(self, circuit: QuantumCircuit, frame: _BitFrame) -> list:
        self._reject_circuit_features(circuit)
        blocks: list = []
        gate_buffer: list[GateOp] = []

        def flush() -> None:
            if gate_buffer:
                blocks.append(CQC(list(gate_buffer), self.global_num_qubits))
                gate_buffer.clear()

        for instruction in circuit.data:
            operation = instruction.operation
            if isinstance(operation, (Store, BreakLoopOp, ContinueLoopOp, SwitchCaseOp)):
                self._unsupported(operation)
            if isinstance(operation, IfElseOp):
                flush()
                blocks.append(self._parse_if_else(instruction, frame))
            elif isinstance(operation, WhileLoopOp):
                flush()
                blocks.append(self._parse_while(instruction, frame))
            elif isinstance(operation, ForLoopOp):
                flush()
                blocks.extend(self._parse_for(instruction, frame))
            elif isinstance(operation, ControlFlowOp):
                self._unsupported(operation)
            else:
                gate_buffer.extend(self._parse_operation(instruction, frame))

        flush()
        return blocks

    def _parse_if_else(self, instruction, frame: _BitFrame) -> DQC:
        operation = instruction.operation
        qargs, cargs = self._outer_operands(instruction, frame)
        true_frame = self._block_frame(operation.blocks[0], qargs, cargs, operation)
        indices, value = self._condition(operation.condition, true_frame, operation)
        true_blocks = self._process_circuit(operation.blocks[0], true_frame)
        false_blocks = []
        if len(operation.blocks) > 1:
            false_frame = self._block_frame(operation.blocks[1], qargs, cargs, operation)
            false_blocks = self._process_circuit(operation.blocks[1], false_frame)
        return DQC(indices, {value: true_blocks}, false_blocks, self.global_num_qubits)

    def _parse_while(self, instruction, frame: _BitFrame) -> SQC:
        operation = instruction.operation
        qargs, cargs = self._outer_operands(instruction, frame)
        body = operation.blocks[0]
        body_frame = self._block_frame(body, qargs, cargs, operation)
        indices, value = self._condition(operation.condition, body_frame, operation)
        body_blocks = self._process_circuit(body, body_frame)
        return SQC({"indices": indices, "value": value}, body_blocks, self.global_num_qubits)

    def _parse_for(self, instruction, frame: _BitFrame) -> list:
        operation = instruction.operation
        indexset, loop_parameter, body = operation.params
        try:
            values = list(indexset)
        except TypeError as exc:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported Qiskit ForLoopOp indexset type: {type(indexset).__name__}."
            ) from exc

        qargs, cargs = self._outer_operands(instruction, frame)
        unrolled: list = []
        for value in values:
            iteration_body = body
            if loop_parameter is not None:
                try:
                    iteration_body = body.assign_parameters({loop_parameter: value}, inplace=False)
                except Exception as exc:
                    raise UnsupportedQiskitFeatureError(
                        "Unsupported parameter use in Qiskit ForLoopOp body "
                        f"({type(exc).__name__})."
                    ) from exc
            iteration_frame = self._block_frame(iteration_body, qargs, cargs, operation)
            unrolled.extend(self._process_circuit(iteration_body, iteration_frame))
        return unrolled

    def _parse_operation(self, instruction, frame: _BitFrame) -> list[GateOp]:
        operation = instruction.operation
        name = operation.name.lower()
        if name == "store" or isinstance(operation, Store):
            self._unsupported(operation)
        condition = getattr(operation, "condition", None)
        if condition is not None:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported classically conditioned instruction: {type(operation).__name__} "
                f"(op '{name}'). Use IfElseOp for supported classical control."
            )
        if name not in self.SUPPORTED_GATES:
            self._unsupported(operation)

        qubits = [self._map_bit(bit, frame.qubits, "qubit", operation) for bit in instruction.qubits]
        clbits = [self._map_bit(bit, frame.clbits, "clbit", operation) for bit in instruction.clbits]
        if name == "measure":
            if len(qubits) != len(clbits) or not qubits:
                raise UnsupportedQiskitFeatureError(
                    f"Unsupported measurement arity for {type(operation).__name__}: "
                    f"{len(qubits)} qubits, {len(clbits)} clbits."
                )
            return [GateOp("measure", qubits, c_targets=clbits)]
        if name == "id":
            return []

        params = [self._numeric_parameter(value, operation) for value in operation.params]
        return self._lower_gate(name, qubits, params, operation)

    def _lower_gate(self, name: str, qubits: list[int], params: list[float], operation) -> list[GateOp]:
        if name == "rx":
            self._require_param_count(name, params, 1, operation)
            theta = (params[0] + math.pi) % (2 * math.pi) - math.pi
            if math.isclose(theta, math.pi / 2):
                return [GateOp("x2p", qubits)]
            if math.isclose(theta, -math.pi / 2):
                return [GateOp("z", qubits), GateOp("x2p", qubits), GateOp("z", qubits)]
            self._unsupported_angle(operation, theta)
        if name == "ry":
            self._require_param_count(name, params, 1, operation)
            theta = (params[0] + math.pi) % (2 * math.pi) - math.pi
            if math.isclose(theta, math.pi / 2):
                return [GateOp("y2p", qubits)]
            if math.isclose(theta, -math.pi / 2):
                return [GateOp("x", qubits), GateOp("y2p", qubits), GateOp("x", qubits)]
            self._unsupported_angle(operation, theta)
        if name in {"rz", "p"}:
            self._require_param_count(name, params, 1, operation)
            theta = params[0] % (2 * math.pi)
            if math.isclose(theta, math.pi / 2):
                return [GateOp("s", qubits)]
            if math.isclose(theta, 3 * math.pi / 2):
                return [GateOp("sdg", qubits)]
            if math.isclose(theta, math.pi / 4):
                return [GateOp("t", qubits)]
            if math.isclose(theta, 7 * math.pi / 4):
                return [GateOp("tdg", qubits)]
            if math.isclose(theta, math.pi):
                return [GateOp("z", qubits)]
            if math.isclose(theta, 0):
                return []
            self._unsupported_angle(operation, theta)
        return [GateOp(name, qubits)]

    def _outer_operands(self, instruction, frame: _BitFrame) -> tuple[list[int], list[int]]:
        operation = instruction.operation
        return (
            [self._map_bit(bit, frame.qubits, "qubit", operation) for bit in instruction.qubits],
            [self._map_bit(bit, frame.clbits, "clbit", operation) for bit in instruction.clbits],
        )

    def _block_frame(
        self, block: QuantumCircuit, qargs: list[int], cargs: list[int], operation
    ) -> _BitFrame:
        if len(block.qubits) != len(qargs) or len(block.clbits) != len(cargs):
            raise UnsupportedQiskitFeatureError(
                f"Invalid {type(operation).__name__} block operand mapping: block has "
                f"{len(block.qubits)} qubits/{len(block.clbits)} clbits but outer instruction "
                f"has {len(qargs)} qubits/{len(cargs)} clbits."
            )
        return _BitFrame(dict(zip(block.qubits, qargs)), dict(zip(block.clbits, cargs)))

    def _condition(self, condition, block_frame: _BitFrame, operation) -> tuple[list[int], int]:
        if not isinstance(condition, tuple) or len(condition) != 2:
            raise UnsupportedQiskitFeatureError(
                "Unsupported Qiskit classical expression condition on "
                f"{type(operation).__name__}: {type(condition).__name__}."
            )
        target, value = condition
        if isinstance(target, Clbit):
            indices = [self._map_bit(target, block_frame.clbits, "condition clbit", operation)]
        elif isinstance(target, ClassicalRegister):
            indices = [
                self._map_bit(bit, block_frame.clbits, "condition clbit", operation)
                for bit in target
            ]
        else:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported Qiskit condition target type on {type(operation).__name__}: "
                f"{type(target).__name__}."
            )
        try:
            return indices, int(value)
        except (TypeError, ValueError) as exc:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported Qiskit condition value type on {type(operation).__name__}: "
                f"{type(value).__name__}."
            ) from exc

    @staticmethod
    def _map_bit(bit, mapping: dict, role: str, operation) -> int:
        try:
            return mapping[bit]
        except KeyError as exc:
            raise UnsupportedQiskitFeatureError(
                f"Cannot map {role} for {type(operation).__name__} (op '{operation.name}')."
            ) from exc

    @staticmethod
    def _numeric_parameter(value, operation) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported symbolic parameter on {type(operation).__name__} "
                f"(op '{operation.name}'): {type(value).__name__}."
            ) from exc

    @staticmethod
    def _require_param_count(name: str, params: list[float], count: int, operation) -> None:
        if len(params) != count:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported parameter arity for {type(operation).__name__} "
                f"(op '{name}'): expected {count}, got {len(params)}."
            )

    @staticmethod
    def _unsupported_angle(operation, theta: float) -> None:
        raise UnsupportedQiskitFeatureError(
            f"Unsupported angle for {type(operation).__name__} (op '{operation.name}'): "
            f"{theta}. Only the existing QSeqSim Clifford+T decompositions are supported."
        )

    @staticmethod
    def _unsupported(operation) -> None:
        raise UnsupportedQiskitFeatureError(
            f"Unsupported Qiskit operation {type(operation).__name__} (op '{operation.name}')."
        )

    @staticmethod
    def _reject_circuit_features(circuit: QuantumCircuit) -> None:
        if getattr(circuit, "num_vars", 0):
            raise UnsupportedQiskitFeatureError(
                f"Unsupported Qiskit dynamic variables in QuantumCircuit '{circuit.name}'."
            )
        try:
            global_phase = float(circuit.global_phase)
        except (TypeError, ValueError) as exc:
            raise UnsupportedQiskitFeatureError(
                f"Unsupported symbolic global_phase in QuantumCircuit '{circuit.name}'."
            ) from exc
        if not math.isclose(global_phase % (2 * math.pi), 0.0, abs_tol=1e-15):
            raise UnsupportedQiskitFeatureError(
                f"Unsupported nonzero global_phase in QuantumCircuit '{circuit.name}': "
                f"{global_phase}."
            )


QiskitCircuitFrontend = QuantumCircuitParser


__all__ = ["QiskitCircuitFrontend", "QuantumCircuitParser"]
