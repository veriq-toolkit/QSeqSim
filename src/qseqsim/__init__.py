"""Stable public API for the QSeqSim library."""

from __future__ import annotations

from qiskit import QuantumCircuit

from ._backend import cudd as _cudd
from .exceptions import SymbolicEvaluationError, UnsupportedQiskitFeatureError
from .parser import CQC, DQC, SQC, GateOp, OpenQASM3Parser, QiskitParser
from .qiskit_frontend import QiskitCircuitFrontend, QuantumCircuitParser
from .qiskit_backend import QSeqSimBackend, QSeqSimJob
from .simulator import BDDSimulator

__version__ = "0.1.0.dev0"


class QSeqSimulator(BDDSimulator):
    """Public simulator with direct-Qiskit and existing-IR entry points.

    ``program`` may be a :class:`~qiskit.QuantumCircuit`, parsed IR blocks, or
    omitted when a circuit will be supplied to :meth:`run` later.
    """

    def __init__(self, program: QuantumCircuit | list | None = None, precision: int = 32):
        blocks = self._parse_program(program)
        super().__init__(blocks, precision=precision)

    @classmethod
    def from_circuit(cls, circuit: QuantumCircuit, precision: int = 32) -> "QSeqSimulator":
        """Construct a simulator from a circuit without OpenQASM serialization."""
        return cls(circuit, precision=precision)

    def run(
        self,
        mode: str | QuantumCircuit = "sample",
        presets=None,
        *,
        circuit: QuantumCircuit | None = None,
    ):
        """Run the loaded program, optionally loading a direct circuit first.

        ``QSeqSimulator().run(qc)`` is shorthand for sample-mode execution.
        Use ``run(mode="preset", presets=..., circuit=qc)`` when both a circuit
        and execution options are supplied.
        """
        if isinstance(mode, QuantumCircuit):
            if circuit is not None:
                raise TypeError("Pass a QuantumCircuit either positionally or by 'circuit', not both.")
            circuit = mode
            mode = "sample"
        if circuit is not None:
            self._load_blocks(QuantumCircuitParser(circuit).parse())
        if not isinstance(mode, str):
            raise TypeError(f"mode must be a string, got {type(mode).__name__}.")
        return super().run(mode=mode, presets=presets)

    @staticmethod
    def _parse_program(program: QuantumCircuit | list | None) -> list:
        if program is None:
            return []
        if isinstance(program, QuantumCircuit):
            return QuantumCircuitParser(program).parse()
        if isinstance(program, list):
            return program
        raise TypeError(
            "QSeqSimulator expects a QuantumCircuit, parsed IR block list, or None; "
            f"got {type(program).__name__}."
        )

    def _load_blocks(self, blocks: list) -> None:
        self.blocks = blocks
        self.num_qubits = blocks[0].global_num_qubits if blocks else 0


__all__ = [
    "BDDSimulator",
    "CQC",
    "DQC",
    "GateOp",
    "OpenQASM3Parser",
    "QSeqSimulator",
    "QSeqSimBackend",
    "QSeqSimJob",
    "QiskitParser",
    "QiskitCircuitFrontend",
    "QuantumCircuitParser",
    "SQC",
    "SymbolicEvaluationError",
    "UnsupportedQiskitFeatureError",
    "__version__",
]
