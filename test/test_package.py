import importlib.metadata

from qiskit import QuantumCircuit

import qseqsim
from qseqsim import (
    BDDSimulator,
    OpenQASM3Parser,
    QSeqSimulator,
    QiskitParser,
    QuantumCircuitParser,
    SymbolicEvaluationError,
    UnsupportedQiskitFeatureError,
)
from qseqsim._backend import cudd


def test_public_api_and_canonical_backend():
    assert issubclass(QSeqSimulator, BDDSimulator)
    assert cudd.__name__ == "dd.cudd"
    assert qseqsim.__version__ == "0.1.0.dev0"
    assert issubclass(SymbolicEvaluationError, RuntimeError)
    assert issubclass(UnsupportedQiskitFeatureError, ValueError)
    assert OpenQASM3Parser is QiskitParser
    assert QuantumCircuitParser.__name__ == "QuantumCircuitParser"


def test_public_api_runs_existing_parser_pipeline():
    circuit = QuantumCircuit(1)
    circuit.x(0)

    simulator = QSeqSimulator(QiskitParser(circuit).parse())
    simulator.run()

    assert simulator.kernel.get_amplitude(0) == 0
    assert simulator.kernel.get_amplitude(1) == 1


def test_installed_distribution_metadata_when_available():
    try:
        metadata = importlib.metadata.metadata("qseqsim")
    except importlib.metadata.PackageNotFoundError:
        return

    assert set(metadata["Requires-Python"].split(",")) == {">=3.12", "<3.14"}
    requirements = metadata.get_all("Requires-Dist") or []
    assert any(requirement.startswith("dd<0.7,>=0.6") for requirement in requirements)
    assert any(requirement.startswith("qiskit<2.5,>=2.2") for requirement in requirements)
