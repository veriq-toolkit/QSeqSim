# QSeqSim: A Symbolic Simulator for Qiskit While Loops using Sequential Quantum Circuits

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**QSeqSim** is a Qiskit-integrated symbolic backend that fills the current gap of having no Qiskit-native support for simulating `while`-loop quantum programs and their induced sequential quantum circuits (SQCs).

QSeqSim takes Qiskit `QuantumCircuit` objects, translates them into OpenQASM 3 code, and organises the resulting program into a combination of combinational, dynamic, and sequential circuits. It assigns `while`-loops a precise sequential circuit semantics with explicit internal and external qubits.

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

### Option B: Native

#### Prerequisites

- Python 3.12 (tested)
- A C/C++ toolchain (required by `dd`)

The `dd` package depends on the CUDD library. The dd authors recommend building CUDD from source; we provide a helper script under `ae/scripts/install_dd_cudd.sh` that follows that approach.

Reference: https://github.com/tulip-control/dd

#### Dependencies

Install CUDD (recommended method):

```bash
chmod +x ae/scripts/install_dd_cudd.sh
./ae/scripts/install_dd_cudd.sh
```

Install Python packages:

```bash
pip install -r requirements.txt
```

Note: `openqasm3[parser]` is required and already included in `requirements.txt`.

Install `dd` after CUDD is available:

```bash
pip install dd
```

If `dd` was installed before CUDD, reinstall it after CUDD is available:

```bash
pip uninstall -y dd
pip install dd
```

For a fully reproducible environment, use the Docker image described in the Artifact Evaluation section.

## Usage

QSeqSim integrates with Qiskit. You can define your circuit using Qiskit's standard control flow operations (like `while_loop`, `if_test`, `switch`) and simulate it using `QiskitParser` and `BDDSimulator`.

### Example: Simulating a Simple While Loop

```python
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from src.parser import QiskitParser
from src.simulator import BDDSimulator

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

# 2. Parse the Circuit
print("Parsing circuit...")
parser = QiskitParser(qc)
structure = parser.parse()

# 3. Simulate
print("Starting simulation...")
sim = BDDSimulator(structure)
final_clbits = sim.run(mode='sample')

# 4. Output Results
print("Final Classical Register:", final_clbits)
sim.print_state_vec()
```

## Project Structure

- **`src/`**: Core source code.
  - `parser.py`: Parses Qiskit circuits and OpenQASM 3 into internal IR (CQC, DQC, SQC).
  - `kernel.py`: Implements the symbolic BDD kernel (`BDDCombSim`, `BDDSeqSim`) and math operations.
  - `simulator.py`: Main simulator class `BDDSimulator` orchestrating the execution flow.
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
