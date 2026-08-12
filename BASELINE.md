# QSeqSim Baseline for Qiskit Ecosystem Productization

This file records the immutable FM 2026 artifact baseline and the repository
state from which Qiskit Ecosystem productization begins. Changes that may alter
the paper's experimental behavior must be made only on the
`qiskit-ecosystem` branch (or its descendants), never on the FM baseline.

## Frozen revisions

### FM 2026 paper artifact

- Commit: `67ae05726951e56fa0ffff9f46b222acb8153a78`
- Commit subject: `fm2026-ae:v0.4`
- Permanent tag: `fm-artifact-2026`
- Preservation branch: `fm-artifact`
- Artifact instructions: `ae/README.md`

This is the authoritative version for reproducing the FM 2026 artifact.

### Productization starting point

- Commit: `f32d799f2dc29aad565d29b0ecf5c08c6fa795f7`
- Commit subject: `Add parser-compatible QRW and Grover lowering`
- Snapshot tag: `pre-ecosystem-baseline-2026`
- Development branch: `qiskit-ecosystem`

The productization starting point includes the later parser-compatible QRW and
Grover lowering work. It is preserved separately so that the exact repository
state immediately before productization remains recoverable.

## Installation at the baseline

There is no installable Python distribution or `pyproject.toml` at this
baseline. Imports assume that commands are run from the repository root and use
the `src.*` module path.

The recommended reproducible installation is Docker:

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

The native development path is:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
./ae/scripts/install_dd_cudd.sh
python -m pip install -r requirements.txt
```

The CUDD-backed `dd.cudd` module is required. Detailed environment and artifact
instructions are in `docs/ENVIRONMENT.md` and `ae/README.md`.

## Declared Python dependencies

`requirements.txt` pins:

- `astutils==0.0.6`
- `Cython==3.2.4`
- `GitPython==3.1.46`
- `networkx==3.6`
- `numpy==2.4.2`
- `openqasm3[parser]==1.0.1`
- `ply==3.10`
- `pytest==9.0.2`
- `qiskit==2.2.3`
- `setuptools==80.9.0`

The simulator additionally requires `dd` with its CUDD extension. The baseline
repository includes `third_party/dd-0.6.0.tar.gz` and the installation helper
`ae/scripts/install_dd_cudd.sh`; `dd` is not pinned in `requirements.txt`.

## Existing entry points

The documented library-level entry points are:

- `src.parser.QiskitParser`: translate a Qiskit `QuantumCircuit` through
  OpenQASM 3 into QSeqSim's CQC/DQC/SQC internal representation.
- `src.simulator.BDDSimulator`: execute parsed blocks; the main method is
  `run(mode="sample", presets=None)`.

Advanced kernel entry points are:

- `src.kernel.BDDCombSim`
- `src.kernel.BDDSeqSim`

The pre-productization snapshot also exposes benchmark/lowering helpers:

- `src.benchmark_circuits.build_qrw_loop_circuit`
- `src.benchmark_circuits.build_grover_loop_circuit`
- the single-loop structural lowering functions in `src.seqsim_lowering`

These paths describe the existing research-code interface; they are not yet a
packaged or versioned public API.

## Reproduction checks

From the repository root, the baseline documentation recommends:

```bash
./ae/scripts/run_smoke.sh
python test/test_parser.py
python test/test_kernel.py
```

Full paper-table reproduction is documented in `ae/README.md`.

## Productization sequence

Work after this baseline should proceed in this order:

1. correctness audit and differential testing;
2. package layout and `pyproject.toml`;
3. direct Qiskit frontend;
4. Qiskit `BackendV2` integration;
5. `SamplerV2` integration;
6. PyPI `v0.1.0` release;
7. user documentation and benchmarks;
8. Qiskit Ecosystem submission.
