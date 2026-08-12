import math

import pytest
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import Parameter, SwitchCaseOp
from qiskit.primitives import BasePrimitiveJob, BaseSamplerV2, StatevectorSampler
from qiskit.primitives.containers import BitArray, DataBin, PrimitiveResult, SamplerPubResult
from qiskit.providers import JobStatus

from qseqsim import (
    QSeqPrimitiveJob,
    QSeqSampler,
    QSeqSamplerV2,
    QSeqSimBackend,
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


def _constant_circuit(value, name):
    circuit = QuantumCircuit(1, 1, name=name)
    if value:
        circuit.x(0)
    circuit.measure(0, 0)
    return circuit


def test_public_sampler_and_job_use_qiskit_v2_types():
    sampler = QSeqSamplerV2(default_shots=8, seed=3)
    assert QSeqSampler is QSeqSamplerV2
    assert isinstance(sampler, BaseSamplerV2)

    job = sampler.run([_constant_circuit(0, "zero")])
    result = job.result()
    assert isinstance(job, (BasePrimitiveJob, QSeqPrimitiveJob))
    assert job.status() is JobStatus.DONE
    assert job.done() and job.in_final_state()
    assert not job.running() and not job.cancelled()
    assert isinstance(result, PrimitiveResult)
    assert isinstance(result[0], SamplerPubResult)
    assert isinstance(result[0].data, DataBin)
    assert isinstance(result[0].data.c, BitArray)
    assert result[0].metadata["shots"] == 8
    assert result.metadata == {
        "version": 2,
        "simulator": "qseqsim",
        "execution_mode": "symbolic_distribution",
    }


def test_bare_tuple_multiple_pubs_and_shots_precedence():
    zero = _constant_circuit(0, "zero")
    one = _constant_circuit(1, "one")
    sampler = QSeqSamplerV2(default_shots=13, seed=1)

    default_result = sampler.run([zero]).result()[0]
    run_result = sampler.run([zero], shots=9).result()[0]
    results = sampler.run([zero, (one, None, 7)], shots=5).result()

    assert default_result.data.c.get_counts() == {"0": 13}
    assert run_result.data.c.get_counts() == {"0": 9}
    assert results[0].data.c.get_counts() == {"0": 5}
    assert results[1].data.c.get_counts() == {"1": 7}
    assert [result.metadata["shots"] for result in results] == [5, 7]


def test_parameter_binding_sweep_and_for_loop_parameter_scope():
    theta = Parameter("theta")
    parameterized = QuantumCircuit(1, 1)
    parameterized.x(0)
    parameterized.rz(theta, 0)
    parameterized.measure(0, 0)

    result = QSeqSamplerV2(seed=2).run(
        [(parameterized, [[0.0], [math.pi / 4], [math.pi]])], shots=6
    ).result()[0]
    assert result.data.c.shape == (3,)
    assert result.data.c.get_counts(0) == {"1": 6}
    assert result.data.c.get_counts(1) == {"1": 6}
    assert result.data.c.get_counts(2) == {"1": 6}

    loop = QuantumCircuit(1, 1)
    with loop.for_loop([1, 2]) as index:
        loop.rz(index * math.pi / 4, 0)
    loop.measure(0, 0)
    assert loop.num_parameters == 0
    assert QSeqSamplerV2().run([loop], shots=4).result()[0].data.c.get_counts() == {
        "0": 4
    }


def test_bound_parameter_outside_supported_domain_is_explicit_failure():
    theta = Parameter("theta")
    circuit = QuantumCircuit(1, 1)
    circuit.rx(theta, 0)
    circuit.measure(0, 0)
    job = QSeqSamplerV2().run([(circuit, [math.pi / 3])], shots=2)
    with pytest.raises(UnsupportedQiskitFeatureError, match="Unsupported angle.*rx"):
        job.result()
    assert job.status() is JobStatus.ERROR


def test_deterministic_and_bell_counts_match_backend_with_same_seed():
    deterministic = _constant_circuit(1, "one")
    bell = _bell_circuit()
    sampler = QSeqSamplerV2(seed=17)

    deterministic_counts = sampler.run([deterministic], shots=25).result()[0].data.c.get_counts()
    backend_deterministic = QSeqSimBackend(num_qubits=2).run(
        deterministic, shots=25, seed_simulator=17
    ).result().get_counts()
    assert deterministic_counts == backend_deterministic == {"1": 25}

    sampler_counts = sampler.run([bell], shots=1000).result()[0].data.c.get_counts()
    backend_counts = QSeqSimBackend(num_qubits=2).run(
        bell, shots=1000, seed_simulator=17
    ).result().get_counts()
    assert sampler_counts == backend_counts
    assert set(sampler_counts) == {"00", "11"}
    assert sum(sampler_counts.values()) == 1000


@pytest.mark.parametrize(
    "circuit",
    [_measurement_while_circuit(), _if_in_while_circuit()],
    ids=["measurement-driven-while", "if-in-while"],
)
def test_dynamic_circuits_preserve_distribution_semantics(circuit):
    counts = QSeqSamplerV2(seed=4).run([circuit], shots=200).result()[0].data.c.get_counts()
    assert set(counts) == {"01", "11"}
    assert sum(counts.values()) == 200


def test_multiple_registers_are_separate_fields_with_qiskit_bit_ordering():
    qreg = QuantumRegister(3, "q")
    low = ClassicalRegister(2, "low")
    high = ClassicalRegister(1, "high")
    circuit = QuantumCircuit(qreg, low, high)
    circuit.x(qreg[0])
    circuit.x(qreg[2])
    circuit.measure(qreg[0], low[0])
    circuit.measure(qreg[1], low[1])
    circuit.measure(qreg[2], high[0])

    pub_result = QSeqSamplerV2().run([circuit], shots=10).result()[0]
    reference = StatevectorSampler(default_shots=10, seed=1).run([circuit]).result()[0]
    backend_counts = QSeqSimBackend(num_qubits=3).run(circuit, shots=10).result().get_counts()

    assert list(pub_result.data.keys()) == ["low", "high"]
    assert pub_result.data.low.get_counts() == {"01": 10}
    assert pub_result.data.high.get_counts() == {"1": 10}
    assert pub_result.join_data().get_counts() == reference.join_data().get_counts() == {"101": 10}
    assert pub_result.join_data(["high", "low"]).get_counts() == {"011": 10}
    assert backend_counts == {"1 01": 10}


def test_seed_reproducibility_and_single_stream_across_pubs():
    sampler = QSeqSamplerV2(seed=991)
    circuits = [_bell_circuit("first"), _bell_circuit("second")]
    first = sampler.run(circuits, shots=128).result()
    second = sampler.run(circuits, shots=128).result()

    first_strings = [result.data.c.get_bitstrings() for result in first]
    second_strings = [result.data.c.get_bitstrings() for result in second]
    assert first_strings == second_strings
    assert first_strings[0] != first_strings[1]


def test_no_register_and_unmeasured_register_match_reference_style():
    no_register = QuantumCircuit(1)
    with pytest.warns(UserWarning, match="no output classical registers"):
        result = QSeqSamplerV2().run([no_register], shots=3).result()[0]
    assert list(result.data.keys()) == []
    assert result.data.shape == ()

    unmeasured = QuantumCircuit(1, 2)
    result = QSeqSamplerV2().run([unmeasured], shots=3).result()[0]
    assert result.data.c.get_counts() == {"00": 3}


def test_unsupported_and_symbolic_failures_propagate_through_job(monkeypatch):
    unsupported = QuantumCircuit(1, 1)
    with unsupported.switch(unsupported.clbits[0]) as case:
        with case(0):
            unsupported.x(0)
    assert isinstance(unsupported.data[0].operation, SwitchCaseOp)
    with pytest.raises(UnsupportedQiskitFeatureError, match="SwitchCaseOp"):
        QSeqSamplerV2().run([unsupported]).result()

    def recursion_failure(*args, **kwargs):
        raise RecursionError("forced")

    monkeypatch.setattr(BDDCombSim, "get_prob", recursion_failure)
    measured = QuantumCircuit(1, 1)
    measured.measure(0, 0)
    with pytest.raises(SymbolicEvaluationError) as caught:
        QSeqSamplerV2().run([measured]).result()
    assert isinstance(caught.value.__cause__, RecursionError)


def test_each_bound_circuit_executes_distribution_once_independent_of_shots(monkeypatch):
    calls = 0
    original = BDDSimulator.run_distribution

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BDDSimulator, "run_distribution", counted)
    theta = Parameter("theta")
    circuit = QuantumCircuit(1, 1)
    circuit.rz(theta, 0)
    circuit.measure(0, 0)
    sampler = QSeqSamplerV2(seed=1)
    sampler.run([(circuit, [[0.0], [math.pi / 4]])], shots=1).result()
    sampler.run([_bell_circuit()], shots=10000).result()
    assert calls == 3


def test_sampler_uses_direct_frontend_and_never_serializes_qasm(monkeypatch):
    import openqasm3
    import qiskit.qasm3

    def forbidden(*args, **kwargs):
        raise AssertionError("OpenQASM path was called")

    monkeypatch.setattr(qiskit.qasm3, "dumps", forbidden)
    monkeypatch.setattr(openqasm3, "parse", forbidden)
    counts = QSeqSamplerV2(seed=3).run([_bell_circuit()], shots=8).result()[0].data.c.get_counts()
    assert set(counts) <= {"00", "11"}


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"default_shots": 0}, ValueError, "default_shots"),
        ({"default_shots": True}, TypeError, "default_shots"),
        ({"precision": 0}, ValueError, "precision"),
        ({"seed": "bad"}, TypeError, "seed"),
    ],
)
def test_constructor_validation(kwargs, error, match):
    with pytest.raises(error, match=match):
        QSeqSamplerV2(**kwargs)


def test_pub_coercion_parameter_errors_are_clear():
    theta = Parameter("theta")
    circuit = QuantumCircuit(1, 1)
    circuit.rz(theta, 0)
    circuit.measure(0, 0)
    with pytest.raises(ValueError, match="number of values"):
        QSeqSamplerV2().run([circuit])
    with pytest.raises(ValueError, match="shots"):
        QSeqSamplerV2().run([(circuit, [0.0], 0)])
