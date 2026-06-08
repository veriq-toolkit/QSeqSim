import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from src.benchmark_circuits import build_grover_loop_circuit, build_qrw_loop_circuit
from src.parser import QiskitParser
from src.seqsim_lowering import can_lower_to_bddseqsim, run_bddseqsim_lowered


def test_qrw_and_grover_lower_to_bddseqsim():
    cases = [
        (build_qrw_loop_circuit(4), [0, 1], [0.5, 0.0]),
        (build_grover_loop_circuit(4), [0, 1], [0.5, 0.25]),
    ]

    for circ, preset_path, expected_trace in cases:
        blocks = QiskitParser(circ).parse()
        assert can_lower_to_bddseqsim(blocks)
        lowered = run_bddseqsim_lowered(blocks, preset_path)
        assert lowered.probability_trace == expected_trace


def test_multi_external_loop_lowers_to_bddseqsim():
    q = QuantumRegister(3, "q")
    c = ClassicalRegister(2, "c")
    circ = QuantumCircuit(q, c)

    with circ.while_loop((c, 0)):
        circ.measure(q[0], c[0])
        circ.measure(q[1], c[1])

    blocks = QiskitParser(circ).parse()
    assert can_lower_to_bddseqsim(blocks)
    assert run_bddseqsim_lowered(blocks, [[0, 0]]).probability == 1.0


if __name__ == "__main__":
    test_qrw_and_grover_lower_to_bddseqsim()
    test_multi_external_loop_lowers_to_bddseqsim()
    print("Qiskit benchmark lowering tests passed.")
