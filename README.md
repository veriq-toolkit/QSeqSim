# Veri-Q QSeqSim

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**QSeqSim** provides structure-aware symbolic simulation of dynamic and
sequential Qiskit circuits using binary decision diagrams (BDDs) and weighted
model counting. It operates directly on `QuantumCircuit` control flow and gives
measurement-driven `while` loops an explicit sequential-circuit semantics with
state retention and feedback.

QSeqSim and Qiskit Aer address different simulation regimes. Aer is a mature,
high-performance numerical simulator with broad methods and noise support;
QSeqSim targets symbolic sharing in structured dynamic and sequential circuits.
It is not presented as a general Aer replacement or as universally faster.

QSeqSim is developed as part of the [**Veri-Q** toolkit](https://www.veri-q.com/).
The Python distribution and import namespace remain `qseqsim`; the public API,
including `QSeqSimulator`, is unchanged. OpenQASM 3 remains available as a
secondary interchange and FM-artifact compatibility frontend.

## Three API layers

```python
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qseqsim import QSeqSamplerV2, QSeqSimBackend, QSeqSimulator

q = QuantumRegister(1, "q")
c = ClassicalRegister(1, "c")
circuit = QuantumCircuit(q, c)
with circuit.while_loop((c[0], 0)):
    circuit.x(q[0])
    circuit.measure(q[0], c[0])

# Native symbolic state/path interface.
native_clbits = QSeqSimulator(circuit).run()

# Qiskit BackendV2: JobV1, Result, counts, and optional memory.
backend_counts = QSeqSimBackend(num_qubits=1).run(
    circuit, shots=128, seed_simulator=7
).result().get_counts()

# Native Primitive V2: PUBs and register-separated BitArray data.
sampler_counts = QSeqSamplerV2(default_shots=128, seed=7).run(
    [circuit]
).result()[0].data.c.get_counts()
```

| API | Use it for |
| --- | --- |
| `QSeqSimulator` | Native symbolic execution, state/path inspection, and preset measurements |
| `QSeqSimBackend` | Qiskit BackendV2 transpilation, jobs, counts, and memory |
| `QSeqSamplerV2` | Primitive V2 PUBs, parameter sweeps, and per-register `BitArray` results |

The public probability contract is binary64 even though model counts and the
pre-conversion algebra use stronger internal representations. See
[Public numerical contract](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/NUMERICAL_CONTRACT.md).

## Scope

- BDD state representation and weighted model counting for structured circuits.
- Sequential circuit semantics with state retention and feedback.
- Direct Qiskit support for tested `if_test`, `while_loop`, and finite
  `for_loop` constructs; unsupported semantics fail explicitly.
- Demonstrated large structured QRW cases in the FM artifact. These results are
  workload-specific, not a general simulator performance claim.

On identical ideal Qiskit workloads with two structured iterations, one-bit
`q[0]` projection, 1,024 shots, and the same backend execution boundary,
QSeqSim crossed the fastest stable Aer method at about 14–16 qubits. Selected
common-width points showed 4.8×–150× lower backend latency for QRW and
9.9×–118× for Grover. Under the 120-second per-worker cutoff on the tested
Apple M2 system, stable completion boundaries were QRW q20/q18/q256 for Aer
statevector/Aer MPS/QSeqSim and Grover q18/q18/q128. Aer still won the small
full-register calibration, and QSeqSim became unfavorable as the requested
symbolic output expanded. These are selected projected-workload results, not a
universal simulator claim; see the [methodology and complete cautious
interpretation](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/ECOSYSTEM_BENCHMARK.md).

## Installation

QSeqSim requires the compiled `dd.cudd` backend and deliberately does not fall
back to `dd.autoref`. The correct installation path therefore depends on
whether PyPI provides a CUDD-enabled `dd` wheel for the platform.

### Linux x86_64 with CPython 3.12 or 3.13

PyPI provides tested manylinux wheels for `dd==0.6.0` on this platform. The
normal one-command install is the primary path:

```bash
python -m pip install qseqsim
python -c "import dd.cudd, qseqsim; print(qseqsim.__version__, dd.cudd.__version__)"
```

This claim is limited to Linux x86_64 with CPython 3.12/3.13. It does not imply
that every `dd` wheel or Linux architecture contains `dd.cudd`.

### macOS arm64 with CPython 3.12 or 3.13

PyPI does not provide a matching `dd==0.6.0` platform wheel. Build `dd` from
source with CUDD enabled before installing QSeqSim:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1 \
  python -m pip install --no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'
python -m pip install qseqsim
python -c "import dd.cudd, qseqsim; print(qseqsim.__version__, dd.cudd.__version__)"
```

Use `python3.13` instead if that is the supported interpreter in the new
environment. The command downloads and builds CUDD, so Xcode Command Line Tools
and network access are required. `--no-cache-dir` prevents pip from reusing a
previously cached pure-Python `dd` wheel. QSeqSim does not claim native Windows
support.

### Docker (reproducible source checkout)

The Docker image includes CUDD and a working `dd` build. This is the easiest way to get a reproducible environment.

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

### Development from a source checkout

#### Prerequisites

- Python 3.12 or 3.13
- A C/C++ toolchain (required when building `dd` from source)

The repository also provides
[`ae/scripts/install_dd_cudd.sh`](https://github.com/veriq-toolkit/QSeqSim/blob/main/ae/scripts/install_dd_cudd.sh)
as a source-checkout convenience. Published installation does not depend on
this helper; use the inline platform commands above when installing from PyPI.

Reference: https://github.com/tulip-control/dd

Create an environment and build the canonical CUDD backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1 \
  python -m pip install --no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'
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

### Qiskit BackendV2 compatibility

Use `QSeqSimulator` for native symbolic execution, state/path inspection, and
preset measurements. Use `QSeqSimBackend` when Qiskit-compatible jobs,
shot-counts, and per-shot memory are required:

```python
from qiskit import QuantumCircuit, transpile
from qseqsim import QSeqSimBackend

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

backend = QSeqSimBackend(num_qubits=2)
compiled = transpile(qc, backend)
result = backend.run(
    compiled, shots=1024, memory=True, seed_simulator=7
).result()
print(result.get_counts())
print(result.get_memory()[:5])
```

The backend directly uses the CP3 `QuantumCircuit` frontend. For each circuit
it performs one symbolic distribution execution, branching and aggregating all
classical outcomes while preserving measurement correlations. The compatibility
layer then samples `shots` from that distribution; it never reruns the symbolic
simulator once per shot. `UnsupportedQiskitFeatureError` and
`SymbolicEvaluationError` propagate from `run()` rather than becoming a
successful `Result`.

### Native Qiskit SamplerV2

Use `QSeqSamplerV2` for Qiskit Primitive V2 PUBs and register-separated
`BitArray` results:

```python
from qiskit import QuantumCircuit
from qseqsim import QSeqSamplerV2

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

sampler = QSeqSamplerV2(default_shots=1024, seed=7)
pub_result = sampler.run([qc]).result()[0]
print(pub_result.data.c.get_counts())
```

The three API layers serve different Qiskit integration levels:

| API | Role |
| --- | --- |
| `QSeqSimulator` | Native symbolic state and path interface |
| `QSeqSimBackend` | BackendV2 compatibility (`JobV1`, counts, memory) |
| `QSeqSamplerV2` | Native Primitive V2 interface (PUBs, `PrimitiveResult`, per-register `BitArray`) |

`QSeqSamplerV2` uses Qiskit's official `SamplerPub.coerce()` and parameter
binding containers. Each bound circuit is executed once to obtain the complete
symbolic classical distribution, after which the requested shots are drawn
from that distribution. It does not invoke BackendV2, serialize OpenQASM, or
run the simulator once per shot. PUB shots override run-level shots, which
override `default_shots`; `shots=None` selects the default rather than exact
probabilities. A single seeded RNG stream advances across all PUBs and bindings
in deterministic order.

| Qiskit feature | Direct frontend |
| --- | --- |
| Supported Clifford+T gates and measurements | Supported |
| Tuple conditions on `Clbit` / `ClassicalRegister` | Supported |
| `IfElseOp`, `WhileLoopOp` | Supported |
| `ForLoopOp` | Supported by finite unrolling and parameter binding |
| `SwitchCaseOp`, `BreakLoopOp`, `ContinueLoopOp` | Explicitly unsupported |
| Classical expression conditions | Explicitly unsupported |
| Dynamic variables and `Store` | Explicitly unsupported |

See [the user guide](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/USER_GUIDE.md) for the complete gate and control-flow matrix.

## Project Structure

- **`src/qseqsim/`**: Installable Python package.
  - `parser.py`: Parses Qiskit circuits through the existing OpenQASM 3 compatibility frontend into internal IR (CQC, DQC, SQC).
  - `qiskit_frontend.py`: Directly maps `QuantumCircuit.data` and control-flow blocks into global-indexed IR.
  - `qiskit_backend.py`: BackendV2 `Target`, synchronous JobV1, standard Result, and distribution-to-shots adapter.
  - `primitives.py`: Native SamplerV2, PrimitiveJob, PUB binding, and register-separated BitArray results.
  - `kernel.py`: Implements the symbolic BDD kernel (`BDDCombSim`, `BDDSeqSim`) and math operations.
  - `simulator.py`: Existing core simulator class `BDDSimulator`.
  - `__init__.py`: Stable public exports, including `QSeqSimulator`, `QSeqSimBackend`, `QuantumCircuitParser`, `OpenQASM3Parser`, and compatibility name `QiskitParser`.
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

- **User guide (library API, semantics, troubleshooting):** [docs/USER_GUIDE.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/USER_GUIDE.md)
- **Public numerical contract:** [docs/NUMERICAL_CONTRACT.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/NUMERICAL_CONTRACT.md)
- **Ecosystem benchmark:** [docs/ECOSYSTEM_BENCHMARK.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/ECOSYSTEM_BENCHMARK.md)
- **Reuse & extension guide (add benchmarks / add gates / testing):** [docs/REUSE.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/REUSE.md)
- **Environment & installation notes (Docker/native, CUDD + dd):** [docs/ENVIRONMENT.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/ENVIRONMENT.md)
- **Package API and FM import migration:** [docs/PACKAGING.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/PACKAGING.md)
- **Results format (CSV schemas):** [docs/RESULTS_FORMAT.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/RESULTS_FORMAT.md)
- **Runnable toy examples:** [examples/](https://github.com/veriq-toolkit/QSeqSim/tree/main/examples)
- **Regression / toy tests:** [test/](https://github.com/veriq-toolkit/QSeqSim/tree/main/test)
- **Artifact Evaluation (FM 2026):** [ae/README.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/ae/README.md)

## Artifact Evaluation (FM 2026)

This repository includes an AE package under `ae/` with scripts, frozen benchmarks, and detailed, step-by-step instructions.

**Quick smoke test (recommended):**

```bash
chmod +x ae/scripts/run_smoke.sh
./ae/scripts/run_smoke.sh
```

This runs small subsets of Tables 1–5 and writes CSV results under `ae/results/`.

**Full AE instructions:** see [ae/README.md](https://github.com/veriq-toolkit/QSeqSim/blob/main/ae/README.md) for Docker usage, full reproduction steps, expected outputs, and reuse guidance.

**Docker build (optional):**

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](https://github.com/veriq-toolkit/QSeqSim/blob/main/LICENSE) file for details.
