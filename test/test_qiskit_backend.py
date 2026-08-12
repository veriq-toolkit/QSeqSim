import pytest
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit.circuit import SwitchCaseOp
from qiskit.providers import BackendV2, JobStatus, JobV1
from qiskit.result import Result

from qseqsim import (
    QSeqSimBackend,
    QSeqSimJob,
    SymbolicEvaluationError,
    UnsupportedQiskitFeatureError,
)
from qseqsim.kernel import BDDCombSim
from qseqsim.simulator import BDDSimulator


def _bell_circuit(name="bell"):
    circuit = QuantumCircuit(2, 2, name=name)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return circuit


def _measurement_while_circuit():
    circuit = QuantumCircuit(2, 2, name="measurement_while")
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.h(0)
        circuit.measure(0, 1)
        circuit.x(1)
        circuit.measure(1, 0)
    return circuit


def _if_in_while_circuit():
    circuit = QuantumCircuit(3, 2, name="if_in_while")
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.h(0)
        circuit.measure(0, 1)
        with circuit.if_test((circuit.clbits[1], 1)):
            circuit.x(1)
        circuit.x(2)
        circuit.measure(2, 0)
    circuit.measure(1, 1)
    return circuit


def test_backend_v2_target_is_conservative_and_has_official_control_flow_classes():
    backend = QSeqSimBackend(num_qubits=6)

    assert isinstance(backend, BackendV2)
    assert backend.num_qubits == 6
    assert backend.max_circuits is None
    expected = {
        "x", "y", "z", "h", "s", "sdg", "t", "tdg", "cx", "cz",
        "swap", "ccx", "cswap", "mcx", "measure", "if_else", "while_loop",
        "for_loop",
    }
    assert set(backend.operation_names) == expected
    assert "switch_case" not in backend.operation_names
    assert "break" not in backend.operation_names
    assert "rx" not in backend.operation_names
    assert all(properties is None for _, properties in backend.target.instructions)


def test_bell_counts_are_correlated_and_result_job_are_qiskit_types():
    backend = QSeqSimBackend(num_qubits=2)
    job = backend.run(_bell_circuit(), shots=1000, seed_simulator=17)
    result = job.result()

    assert isinstance(job, (JobV1, QSeqSimJob))
    assert job.status() is JobStatus.DONE
    assert job.done()
    assert isinstance(result, Result)
    counts = result.get_counts()
    assert set(counts) == {"00", "11"}
    assert sum(counts.values()) == 1000
    assert counts["00"] == pytest.approx(500, abs=80)


def test_deterministic_counts_memory_and_seeded_reproducibility():
    backend = QSeqSimBackend(num_qubits=2)
    deterministic = QuantumCircuit(2, 2)
    deterministic.x(0)
    deterministic.measure([0, 1], [0, 1])
    result = backend.run(deterministic, shots=25, memory=True).result()
    assert result.get_counts() == {"01": 25}
    assert result.get_memory() == ["01"] * 25

    first = backend.run(
        _bell_circuit("seeded"), shots=100, memory=True, seed_simulator=991
    ).result()
    second = backend.run(
        _bell_circuit("seeded"), shots=100, memory=True, seed_simulator=991
    ).result()
    assert first.get_memory() == second.get_memory()
    assert first.get_counts() == second.get_counts()


def test_multiple_circuits_return_multiple_experiment_results():
    backend = QSeqSimBackend(num_qubits=2)
    zero = QuantumCircuit(1, 1, name="zero")
    zero.measure(0, 0)
    one = QuantumCircuit(1, 1, name="one")
    one.x(0)
    one.measure(0, 0)

    result = backend.run([zero, one], shots=8, memory=True, seed_simulator=2).result()
    assert result.get_counts() == [{"0": 8}, {"1": 8}]
    assert result.get_memory(0) == ["0"] * 8
    assert result.get_memory(1) == ["1"] * 8


def test_multiple_classical_register_ordering_uses_qiskit_result_schema():
    qreg = QuantumRegister(3, "q")
    low = ClassicalRegister(2, "low")
    high = ClassicalRegister(1, "high")
    circuit = QuantumCircuit(qreg, low, high)
    circuit.x(qreg[0])
    circuit.x(qreg[2])
    circuit.measure(qreg[0], low[0])
    circuit.measure(qreg[1], low[1])
    circuit.measure(qreg[2], high[0])

    result = QSeqSimBackend(num_qubits=3).run(
        circuit, shots=4, memory=True
    ).result()
    assert result.data()["counts"] == {"0x5": 4}
    assert result.get_counts() == {"1 01": 4}
    assert result.get_memory() == ["1 01"] * 4


@pytest.mark.parametrize(
    "circuit",
    [
        _measurement_while_circuit(),
        _if_in_while_circuit(),
    ],
    ids=["measurement-driven-while", "if-in-while"],
)
def test_supported_dynamic_circuits_execute_directly(circuit):
    result = QSeqSimBackend(num_qubits=3).run(
        circuit, shots=200, seed_simulator=4
    ).result()
    counts = result.get_counts()
    assert set(counts) == {"01", "11"}
    assert sum(counts.values()) == 200


def test_unsupported_feature_and_symbolic_evaluation_failures_propagate(monkeypatch):
    unsupported = QuantumCircuit(1, 1)
    with unsupported.switch(unsupported.clbits[0]) as case:
        with case(0):
            unsupported.x(0)
    assert isinstance(unsupported.data[0].operation, SwitchCaseOp)
    with pytest.raises(UnsupportedQiskitFeatureError, match="SwitchCaseOp"):
        QSeqSimBackend(num_qubits=1).run(unsupported)

    def recursion_failure(*args, **kwargs):
        raise RecursionError("forced")

    monkeypatch.setattr(BDDCombSim, "get_prob", recursion_failure)
    measured = QuantumCircuit(1, 1)
    measured.measure(0, 0)
    with pytest.raises(SymbolicEvaluationError) as caught:
        QSeqSimBackend(num_qubits=1).run(measured)
    assert isinstance(caught.value.__cause__, RecursionError)


def test_transpile_ordinary_and_dynamic_circuits_against_target():
    backend = QSeqSimBackend(num_qubits=3)
    ordinary = transpile(_bell_circuit(), backend, optimization_level=0)
    assert backend.run(ordinary, shots=5).result().get_counts().keys() <= {"00", "11"}

    dynamic = transpile(_measurement_while_circuit(), backend, optimization_level=0)
    assert any(instruction.operation.name == "while_loop" for instruction in dynamic.data)
    counts = backend.run(dynamic, shots=100, seed_simulator=3).result().get_counts()
    assert set(counts) == {"01", "11"}


def test_backend_path_never_serializes_qasm(monkeypatch):
    import openqasm3
    import qiskit.qasm3

    def forbidden(*args, **kwargs):
        raise AssertionError("OpenQASM path was called")

    monkeypatch.setattr(qiskit.qasm3, "dumps", forbidden)
    monkeypatch.setattr(openqasm3, "parse", forbidden)
    assert QSeqSimBackend(num_qubits=2).run(
        _bell_circuit(), shots=4
    ).result().get_counts().keys() <= {"00", "11"}


def test_each_circuit_has_one_distribution_execution_independent_of_shots(monkeypatch):
    calls = 0
    original = BDDSimulator.run_distribution

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BDDSimulator, "run_distribution", counted)
    backend = QSeqSimBackend(num_qubits=2)
    backend.run(_bell_circuit(), shots=1)
    backend.run(_bell_circuit(), shots=10000)
    backend.run([_bell_circuit("a"), _bell_circuit("b")], shots=3)
    assert calls == 4


def test_unknown_and_invalid_options_are_rejected():
    backend = QSeqSimBackend(num_qubits=2)
    with pytest.raises(AttributeError, match="unknown"):
        backend.run(_bell_circuit(), unknown=True)
    with pytest.raises(ValueError, match="shots"):
        backend.run(_bell_circuit(), shots=0)
    with pytest.raises(TypeError, match="memory"):
        backend.run(_bell_circuit(), memory=1)
    with pytest.raises(TypeError, match="seed_simulator"):
        backend.run(_bell_circuit(), seed_simulator="seed")
