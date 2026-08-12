"""Circuits used by the research benchmarks and regression suite."""

from __future__ import annotations

from collections.abc import Sequence

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

BenchmarkOp = tuple[str, tuple[int, ...]]
COMPACT_QASM_METADATA_KEY = "qseqsim_compact_qasm"


def apply_multi_controlled_x(circuit: QuantumCircuit, controls: Sequence, target) -> None:
    controls = list(controls)
    if not controls:
        circuit.x(target)
    elif len(controls) == 1:
        circuit.cx(controls[0], target)
    elif len(controls) == 2:
        circuit.ccx(controls[0], controls[1], target)
    else:
        circuit.mcx(controls, target)


def apply_qrw_iteration(circuit: QuantumCircuit, qubits: Sequence) -> None:
    """Append the QRW body used by exp/simulation/qrw.py."""
    qubits = list(qubits)
    _apply_ops(circuit, qubits, qrw_iteration_ops(len(qubits)))


def apply_grover_iteration(circuit: QuantumCircuit, qubits: Sequence) -> None:
    """Append the Grover body used by exp/simulation/grover.py."""
    qubits = list(qubits)
    _apply_ops(circuit, qubits, grover_iteration_ops(len(qubits)))


def qrw_iteration_ops(n: int) -> list[BenchmarkOp]:
    if n < 3:
        raise ValueError("QRW requires at least 3 qubits.")

    ops: list[BenchmarkOp] = [("h", (1,))]
    ops.extend(_cwalk_ops(1, list(range(2, n))))
    _append_multi_controlled_x_op(ops, list(range(1, n)), 0)
    return ops


def grover_iteration_ops(n: int) -> list[BenchmarkOp]:
    if n < 3:
        raise ValueError("Grover requires at least 3 qubits.")

    ops: list[BenchmarkOp] = []
    for i in range(n - 1):
        ops.append(("h", (i,)))
    ops.append(("h", (n - 1,)))
    _append_multi_controlled_x_op(ops, list(range(n - 1)), n - 1)
    ops.append(("h", (n - 1,)))

    for i in range(n - 1):
        ops.append(("h", (i,)))
        ops.append(("x", (i,)))
    ops.append(("h", (n - 2,)))
    _append_multi_controlled_x_op(ops, list(range(n - 2)), n - 2)
    ops.append(("h", (n - 2,)))

    for i in range(n - 1):
        ops.append(("h", (i,)))
        ops.append(("x", (i,)))

    return ops


def build_qrw_loop_circuit(n: int) -> QuantumCircuit:
    q = QuantumRegister(n, "q")
    c = ClassicalRegister(1, "c")
    circ = QuantumCircuit(q, c, name=f"qrw_loop_{n}")

    with circ.while_loop((c[0], 0)):
        apply_qrw_iteration(circ, q)
        circ.measure(q[0], c[0])

    _attach_compact_qasm(circ, build_qrw_loop_qasm(n))
    return circ


def build_grover_loop_circuit(n: int) -> QuantumCircuit:
    q = QuantumRegister(n, "q")
    c = ClassicalRegister(1, "c")
    circ = QuantumCircuit(q, c, name=f"grover_loop_{n}")

    with circ.while_loop((c[0], 0)):
        apply_grover_iteration(circ, q)
        circ.measure(q[0], c[0])

    _attach_compact_qasm(circ, build_grover_loop_qasm(n))
    return circ


def build_qrw_loop_qasm(n: int) -> str:
    return _build_loop_qasm(n, qrw_iteration_ops(n))


def build_grover_loop_qasm(n: int) -> str:
    return _build_loop_qasm(n, grover_iteration_ops(n))


def _cwalk_ops(control: int, targets: Sequence[int]) -> list[BenchmarkOp]:
    targets = list(targets)
    ops: list[BenchmarkOp] = [("x", (control,))]

    for i, target in enumerate(targets):
        _append_multi_controlled_x_op(ops, [control] + targets[i + 1 :], target)

    ops.append(("x", (control,)))
    for i in range(len(targets) - 1, -1, -1):
        _append_multi_controlled_x_op(ops, [control] + targets[i + 1 :], targets[i])

    return ops


def _append_multi_controlled_x_op(
    ops: list[BenchmarkOp], controls: Sequence[int], target: int
) -> None:
    controls = list(controls)
    if not controls:
        ops.append(("x", (target,)))
    elif len(controls) == 1:
        ops.append(("cx", (controls[0], target)))
    elif len(controls) == 2:
        ops.append(("ccx", (controls[0], controls[1], target)))
    else:
        ops.append(("mcx", tuple(controls) + (target,)))


def _apply_ops(circuit: QuantumCircuit, qubits: Sequence, ops: Sequence[BenchmarkOp]) -> None:
    for name, indices in ops:
        operands = [qubits[i] for i in indices]
        if name == "h":
            circuit.h(operands[0])
        elif name == "x":
            circuit.x(operands[0])
        elif name == "cx":
            circuit.cx(operands[0], operands[1])
        elif name == "ccx":
            circuit.ccx(operands[0], operands[1], operands[2])
        elif name == "mcx":
            apply_multi_controlled_x(circuit, operands[:-1], operands[-1])
        else:
            raise ValueError(f"Unsupported benchmark operation: {name}")


def _build_loop_qasm(n: int, ops: Sequence[BenchmarkOp]) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "bit[1] c;",
        f"qubit[{n}] q;",
        "while (c[0] == 0) {",
    ]

    for name, indices in ops:
        args = ", ".join(f"q[{i}]" for i in indices)
        lines.append(f"  {name} {args};")

    lines.extend(
        [
            "  c[0] = measure q[0];",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _attach_compact_qasm(circuit: QuantumCircuit, qasm: str) -> None:
    metadata = dict(circuit.metadata or {})
    metadata[COMPACT_QASM_METADATA_KEY] = qasm
    circuit.metadata = metadata
