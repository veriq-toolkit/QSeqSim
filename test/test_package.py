import importlib.metadata
from pathlib import Path
import re
import tomllib

from qiskit import QuantumCircuit

import qseqsim
from qseqsim import (
    BDDSimulator,
    OpenQASM3Parser,
    QSeqSimBackend,
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
    assert qseqsim.__version__ == "0.1.0.dev1"
    assert issubclass(SymbolicEvaluationError, RuntimeError)
    assert issubclass(UnsupportedQiskitFeatureError, ValueError)
    assert OpenQASM3Parser is QiskitParser
    assert QuantumCircuitParser.__name__ == "QuantumCircuitParser"


def test_release_version_sources_are_consistent():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    citation = (root / "CITATION.cff").read_text()

    assert project["project"]["version"] == qseqsim.__version__
    assert QSeqSimBackend(num_qubits=1).backend_version == qseqsim.__version__
    assert re.search(
        rf"^version: {re.escape(qseqsim.__version__)}$", citation, re.MULTILINE
    )


def test_published_metadata_and_readme_install_contract():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    readme = (root / "README.md").read_text()

    assert all(
        value.startswith("https://github.com/veriq-toolkit/QSeqSim")
        for key, value in project["project"]["urls"].items()
        if key != "Paper"
    )
    assert "github.com/Veri-Q/QSeqSim" not in readme
    assert "](docs/" not in readme
    assert "](LICENSE)" not in readme
    assert "](ae/" not in readme
    assert "./ae/scripts/install_dd_cudd.sh" not in readme
    assert "QSeqSim requires the compiled `dd.cudd` backend" in readme
    assert (
        "--no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'"
        in readme
    )


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
    assert any(requirement.startswith("qiskit<2.5,>=2.4") for requirement in requirements)
