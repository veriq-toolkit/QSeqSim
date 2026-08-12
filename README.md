# QSeqSim: A Symbolic Simulator for Qiskit While Loops using Sequential Quantum Circuits

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**QSeqSim** is a Qiskit-integrated symbolic backend that fills the current gap of having no Qiskit-native support for simulating `while`-loop quantum programs and their induced sequential quantum circuits (SQCs).

QSeqSim directly consumes Qiskit `QuantumCircuit` and `ControlFlowOp` objects and organises them into combinational, dynamic, and sequential circuits. It assigns `while`-loops a precise sequential circuit semantics with explicit internal and external qubits. An OpenQASM 3 parser remains available as a secondary interchange and FM-compatibility frontend.

Building on this semantics, QSeqSim adopts a BDD-based symbolic representation and systematically integrates model counting techniques to optimise probability computation over structured and sparse BDDs. It enables efficient symbolic execution of sequential quantum circuits, scaling to substantial while-induced circuits (e.g., simulating Quantum Random Walks with over 1000 qubits for more than 10 loop iterations).

## Key Features

- **Direct While-Loop Support**: Executes Qiskit programs containing `while`-loops by giving them an executable small-step semantics, unlike standard simulators that often fail or unroll loops.
- **Symbolic Simulation**: Uses Binary Decision Diagrams (BDDs) (based on `dd` package) for efficient state representation.
- **Sequential Circuit Semantics**: Models loops as Sequential Quantum Circuits (SQCs) with state retention and feedback.
- **High Precision & Scalability**:
  - Implements **Exact Zero Check** using integer arithmetic to eliminate floating-point noise.
  - Uses `Decimal` for high-precision probability calculations (supporting probabilities as low as $10^{-78}$).
  - Scales to 1000+ qubits for specific structured circuits like Quantum Random Walks.

## Installation

### Option A: Docker (recommended)

The Docker image includes CUDD and a working `dd` build. This is the easiest way to get a reproducible environment.

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

### Option B: Native package install

#### Prerequisites

- Python 3.12 or 3.13
- A C/C++ toolchain (required by `dd`)

The `dd` package depends on the CUDD library. The dd authors recommend building CUDD from source; we provide a helper script under `ae/scripts/install_dd_cudd.sh` that follows that approach.

Reference: https://github.com/tulip-control/dd

#### Dependencies

Install CUDD (recommended method):

```bash
chmod +x ae/scripts/install_dd_cudd.sh
./ae/scripts/install_dd_cudd.sh
```

Create an environment and build the canonical CUDD backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
./ae/scripts/install_dd_cudd.sh
```

Install QSeqSim from the repository:

```bash
python -m pip install .
```

For development, use an editable install with the test dependencies:

```bash
python -m pip install -e '.[test,build]'
```

QSeqSim requires `dd.cudd` and validates it during import. It never falls back to
`dd.autoref`. A plain `dd` installation can succeed without a usable CUDD
extension, so verify the environment explicitly:

```bash
python -c "import dd.cudd; import qseqsim; print('QSeqSim + CUDD OK')"
```

For a fully reproducible environment, use the Docker image described in the
Artifact Evaluation section. The formal runtime dependency ranges live in
`pyproject.toml`; `requirements.txt` remains the pinned FM/AE environment.

## Usage

QSeqSim integrates directly with Qiskit. The recommended entry point accepts a `QuantumCircuit` without serializing it through OpenQASM 3. The currently supported control-flow operations are `if_test`, `while_loop`, and finite `for_loop`; unsupported operations such as `switch`, `break_loop`, and `continue_loop` fail explicitly.

### Example: Simulating a Simple While Loop

```python
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qseqsim import QSeqSimulator

# 1. Define Qiskit Circuit
q = QuantumRegister(2, 'q')
c = ClassicalRegister(2, 'c')
qc = QuantumCircuit(q, c)

# Initialize qubits
qc.h(q[0])
qc.cx(q[0], q[1])

# Define a while loop: run while c[0] == 0
# Note: This is a conceptual example. Ensure your loop has a termination condition.
with qc.while_loop((c[0], 0)):
    qc.h(q[0])
    qc.cx(q[0], q[1])
    qc.measure(q[0], c[0])

# Final measurement
qc.measure(q[1], c[1])

# 2. Simulate directly (no qasm3.dumps/parser round trip)
print("Starting simulation...")
sim = QSeqSimulator(qc)
final_clbits = sim.run(mode='sample')

# 3. Output Results
print("Final Classical Register:", final_clbits)
sim.print_state_vec()
```

The equivalent one-shot form is `QSeqSimulator().run(qc)`. Existing code may
continue to use `QSeqSimulator(QiskitParser(qc).parse())`; that compatibility
path still serializes through OpenQASM 3. Raw interchange text can be parsed
with `OpenQASM3Parser(qasm_str=text)`.

| Qiskit feature | Direct frontend |
| --- | --- |
| Supported Clifford+T gates and measurements | Supported |
| Tuple conditions on `Clbit` / `ClassicalRegister` | Supported |
| `IfElseOp`, `WhileLoopOp` | Supported |
| `ForLoopOp` | Supported by finite unrolling and parameter binding |
| `SwitchCaseOp`, `BreakLoopOp`, `ContinueLoopOp` | Explicitly unsupported |
| Classical expression conditions | Explicitly unsupported |
| Dynamic variables and `Store` | Explicitly unsupported |

See [the user guide](docs/USER_GUIDE.md) for the complete gate and control-flow matrix.

## Project Structure

- **`src/qseqsim/`**: Installable Python package.
  - `parser.py`: Parses Qiskit circuits through the existing OpenQASM 3 compatibility frontend into internal IR (CQC, DQC, SQC).
  - `qiskit_frontend.py`: Directly maps `QuantumCircuit.data` and control-flow blocks into global-indexed IR.
  - `kernel.py`: Implements the symbolic BDD kernel (`BDDCombSim`, `BDDSeqSim`) and math operations.
  - `simulator.py`: Existing core simulator class `BDDSimulator`.
  - `__init__.py`: Stable public exports, including `QSeqSimulator`, `QuantumCircuitParser`, `OpenQASM3Parser`, and compatibility name `QiskitParser`.
- **`src/*.py`**: Thin compatibility modules for existing FM research scripts. New library code should import `qseqsim`.
- **`exp/`**: Experiment scripts and benchmarks.
  - `simulation/`: Contains specific experiments for RQC, Grover, and QRW.
    - `exp_engine.py`: Engine for running experiments and collecting metrics.
    - `gen_rqc.py`: Generates Random Quantum Circuit benchmarks.
    - `run_rqc_exp.py`: Runs the RQC benchmark suite.
- **`test/`**: Unit tests for parser and kernel.

## Experiments

The repository contains scripts to reproduce the experiments presented in the paper.

### Random Quantum Circuits (RQC)

To run the RQC benchmark suite which tests performance on combinational, dynamic, and sequential structures:

```bash
python exp/simulation/run_rqc_exp.py
```

This will generate benchmark circuits, run simulations, log results to `exp/simulation/data/rqc.log`, and generate a LaTeX table `rqc_result.tex`.

### Quantum Random Walk (QRW)

To run the Quantum Random Walk experiment (scaling up to 1024 qubits):

```bash
python exp/simulation/qrw.py
```

To run the parser-compatible Qiskit QRW loop benchmark using the BDDSeqSim
lowering backend:

```bash
python exp/simulation/exp_engine.py qiskit_qrw
```

### Grover's Algorithm

To run the Grover search experiment:

```bash
python exp/simulation/grover.py
```

To run the parser-compatible Qiskit Grover loop benchmark using the BDDSeqSim
lowering backend:

```bash
python exp/simulation/exp_engine.py qiskit_grover
```

## Documentation (User / Reuse / AE)

- **User guide (library API, semantics, troubleshooting):** [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- **Reuse & extension guide (add benchmarks / add gates / testing):** [docs/REUSE.md](docs/REUSE.md)
- **Environment & installation notes (Docker/native, CUDD + dd):** [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
- **Package API and FM import migration:** [docs/PACKAGING.md](docs/PACKAGING.md)
- **Results format (CSV schemas):** [docs/RESULTS_FORMAT.md](docs/RESULTS_FORMAT.md)
- **Runnable toy examples:** [examples/](examples/)
- **Regression / toy tests:** [test/](test/)
- **Artifact Evaluation (FM 2026):** [ae/README.md](ae/README.md)

## Artifact Evaluation (FM 2026)

This repository includes an AE package under `ae/` with scripts, frozen benchmarks, and detailed, step-by-step instructions.

**Quick smoke test (recommended):**

```bash
chmod +x ae/scripts/run_smoke.sh
./ae/scripts/run_smoke.sh
```

This runs small subsets of Tables 1–5 and writes CSV results under `ae/results/`.

**Full AE instructions:** see [ae/README.md](ae/README.md) for Docker usage, full reproduction steps, expected outputs, and reuse guidance.

**Docker build (optional):**

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
