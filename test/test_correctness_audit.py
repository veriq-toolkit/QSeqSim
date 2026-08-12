import math

import numpy as np
import pytest
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Statevector

from src.kernel import BDDCombSim, BDDSeqSim
from src.parser import CQC, DQC, SQC, QiskitParser
from src.simulator import BDDSimulator


def _kernel_state(sim):
    return np.asarray([sim.get_amplitude(i) for i in range(1 << sim.n)])


def _qiskit_state_in_qseq_order(state):
    """Translate Qiskit's little-endian basis indexing to QSeqSim's q0-first order."""
    vector = np.asarray(state.data)
    width = int(math.log2(len(vector)))
    reordered = np.empty_like(vector)
    for qseq_index in range(len(vector)):
        qiskit_index = int(f"{qseq_index:0{width}b}"[::-1], 2)
        reordered[qseq_index] = vector[qiskit_index]
    return reordered


def _run_preset(circuit, presets):
    blocks = QiskitParser(circuit).parse()
    simulator = BDDSimulator(blocks)
    simulator.run(mode="preset", presets={key: list(values) for key, values in presets.items()})
    state = _kernel_state(simulator.kernel) / math.sqrt(simulator.global_probability)
    return blocks, simulator, state


def test_ordinary_gate_circuit_matches_statevector():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.t(0)
    circuit.cx(0, 1)
    circuit.s(2)
    circuit.x(2)
    circuit.cz(1, 2)

    expected = _qiskit_state_in_qseq_order(Statevector.from_instruction(circuit))
    blocks = QiskitParser(circuit).parse()
    simulator = BDDSimulator(blocks)
    simulator.run()

    assert np.allclose(_kernel_state(simulator.kernel), expected, atol=1e-12)


def test_mid_circuit_measurement_matches_dense_branch():
    q = QuantumRegister(2, "q")
    c = ClassicalRegister(1, "c")
    circuit = QuantumCircuit(q, c)
    circuit.h(q[0])
    circuit.measure(q[0], c[0])
    circuit.cx(q[0], q[1])

    _, simulator, state = _run_preset(circuit, {0: [1]})

    assert simulator.global_probability == pytest.approx(0.5)
    assert np.allclose(state, _qiskit_state_in_qseq_order(Statevector.from_label("11")), atol=1e-12)


def test_repeated_run_starts_fresh_and_does_not_consume_caller_presets():
    q = QuantumRegister(1, "q")
    c = ClassicalRegister(1, "c")
    circuit = QuantumCircuit(q, c)
    circuit.h(q[0])
    circuit.measure(q[0], c[0])
    circuit.x(q[0])
    blocks = QiskitParser(circuit).parse()
    simulator = BDDSimulator(blocks)
    presets = {0: [0]}

    first_result = simulator.run(mode="preset", presets=presets)
    first_state = _kernel_state(simulator.kernel) / math.sqrt(simulator.global_probability)
    second_result = simulator.run(mode="preset", presets=presets)
    second_state = _kernel_state(simulator.kernel) / math.sqrt(simulator.global_probability)

    assert first_result == second_result == {0: 0}
    assert np.allclose(first_state, second_state, atol=1e-12)
    assert presets == {0: [0]}


def test_measurement_driven_while_retains_state_across_iterations():
    q = QuantumRegister(2, "q")
    c = ClassicalRegister(1, "c")
    circuit = QuantumCircuit(q, c)
    with circuit.while_loop((c[0], 0)):
        circuit.x(q[1])
        circuit.h(q[0])
        circuit.measure(q[0], c[0])

    blocks, simulator, state = _run_preset(circuit, {0: [0, 1]})

    assert any(isinstance(block, SQC) for block in blocks)
    assert simulator.global_probability == pytest.approx(0.25)
    assert simulator.clbit_store == {0: 1}
    assert np.allclose(state, _qiskit_state_in_qseq_order(Statevector.from_label("01")), atol=1e-12)


def test_if_inside_while_and_nested_control_flow_follow_classical_results():
    q = QuantumRegister(3, "q")
    c = ClassicalRegister(2, "c")
    circuit = QuantumCircuit(q, c)
    with circuit.while_loop((c[0], 0)):
        circuit.h(q[0])
        circuit.measure(q[0], c[1])
        with circuit.if_test((c[1], 0)) as else_:
            circuit.x(q[1])
        with else_:
            circuit.z(q[1])
        circuit.h(q[2])
        circuit.measure(q[2], c[0])

    blocks, simulator, state = _run_preset(circuit, {1: [0], 0: [1]})

    loop = next(block for block in blocks if isinstance(block, SQC))
    assert any(isinstance(block, DQC) for block in loop.body_block)
    assert simulator.global_probability == pytest.approx(0.25)
    assert simulator.clbit_store == {0: 1, 1: 0}
    assert np.allclose(state, _qiskit_state_in_qseq_order(Statevector.from_label("110")), atol=1e-12)


def test_dynamic_reordering_preserves_amplitudes_and_probabilities():
    simulator = BDDCombSim(4, 32)
    simulator.init_basis_state(0)
    simulator.H(0)
    simulator.T(0)
    simulator.CNOT(0, 3)
    simulator.H(2)

    amplitudes_before = _kernel_state(simulator)
    probabilities_before = [simulator.get_prob([0, 2], bits) for bits in ([0, 0], [0, 1], [1, 0], [1, 1])]

    simulator.BDD.reorder({f"q{i}": 3 - i for i in range(4)})

    assert np.allclose(_kernel_state(simulator), amplitudes_before, atol=1e-12)
    assert [simulator.get_prob([0, 2], bits) for bits in ([0, 0], [0, 1], [1, 0], [1, 1])] == pytest.approx(probabilities_before)
    assert simulator.BDD.configure()["reordering"] is True


def test_sequential_manager_copy_retains_and_composes_stored_state():
    simulator = BDDSeqSim(2, 1, 16)
    simulator.init_stored_state_by_basis(0)

    for measured_bit in (0, 1):
        simulator.init_input_state_by_basis(0)
        simulator.init_comb_bdd()
        simulator.H(0)
        simulator.CNOT(0, 1)
        simulator.measure([measured_bit])

    assert simulator.prob_list == pytest.approx([0.5, 0.25])
    normalized_stored_state = np.asarray(
        [simulator.stored_bdd.get_amplitude(i) for i in range(2)]
    ) / math.sqrt(simulator.prob_list[-1])
    assert np.allclose(normalized_stored_state, Statevector.from_label("1").data, atol=1e-12)


def test_exact_model_count_above_binary64_integer_limit():
    simulator = BDDCombSim(60, 3)
    all_zero = simulator.BDD.cube({f"q{i}": False for i in range(60)})
    all_but_zero = ~all_zero

    rounded_count = int(simulator.BDD.count(all_but_zero))
    exact_count = simulator._exact_model_count(all_but_zero)

    assert rounded_count == 1 << 60
    assert exact_count == (1 << 60) - 1
