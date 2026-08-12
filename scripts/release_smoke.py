#!/usr/bin/env python3
"""Public API smoke tests intended to run against an installed wheel."""

from __future__ import annotations

import math

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit.circuit import Parameter

from qseqsim import OpenQASM3Parser, QSeqSamplerV2, QSeqSimBackend, QSeqSimulator


def native_smoke() -> None:
    circuit = QuantumCircuit(1, 1)
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.x(0)
        circuit.measure(0, 0)
    assert QSeqSimulator(circuit).run() == {0: 1}


def backend_smoke() -> None:
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    backend = QSeqSimBackend(num_qubits=2)
    compiled = transpile(circuit, backend, optimization_level=0)
    result = backend.run(
        compiled, shots=64, memory=True, seed_simulator=7
    ).result()
    assert set(result.get_counts()) <= {"00", "11"}
    assert len(result.get_memory()) == 64


def sampler_smoke() -> None:
    qreg = QuantumRegister(2, "q")
    low = ClassicalRegister(1, "low")
    high = ClassicalRegister(1, "high")
    theta = Parameter("theta")
    circuit = QuantumCircuit(qreg, low, high)
    circuit.x(qreg[0])
    circuit.rz(theta, qreg[1])
    circuit.measure(qreg[0], low[0])
    circuit.measure(qreg[1], high[0])
    result = QSeqSamplerV2(default_shots=8, seed=7).run(
        [(circuit, [[0.0], [math.pi / 4]])]
    ).result()[0]
    assert result.data.low.get_counts(0) == {"1": 8}
    assert result.data.low.get_counts(1) == {"1": 8}
    assert result.data.high.get_counts(0) == {"0": 8}
    assert result.data.high.get_counts(1) == {"0": 8}


def openqasm_smoke() -> None:
    program = """OPENQASM 3.0;
include \"stdgates.inc\";
bit[1] c;
qubit[1] q;
x q[0];
c[0] = measure q[0];
"""
    blocks = OpenQASM3Parser(qasm_str=program).parse()
    assert QSeqSimulator(blocks).run() == {0: 1}


if __name__ == "__main__":
    native_smoke()
    backend_smoke()
    sampler_smoke()
    openqasm_smoke()
    print("Installed-wheel public API smoke tests passed")
