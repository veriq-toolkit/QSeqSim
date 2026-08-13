# Environment & Installation Notes (QSeqSim)

This document describes recommended environments for running QSeqSim and provides detailed guidance for **native installation**, with a focus on installing the Python package **`dd`** with the **CUDD backend** (`dd.cudd`), which is the most common source of installation issues.

Upstream reference for `dd` (official build notes and troubleshooting):
- https://github.com/tulip-control/dd


## 1. Recommended environment: Docker (reproducible)

Docker is the recommended way to run QSeqSim for:
- Artifact Evaluation (AE),
- stable reproduction of experiments,
- avoiding CUDD build/linker issues.

### 1.1 Build and run

From the repository root:

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

### 1.2 Quick sanity checks (inside container)
```bash
python examples/while_minimal.py
python examples/branching_if_switch.py
python test/test_parser.py
```
If these succeed, your environment is correct.

## 2. Native installation (advanced / for development & reuse)
Native installation is possible but **less robust** than Docker, mainly due to:

- the need for a correct CUDD build,
- linking `dd`’s C extensions against CUDD,
- architecture mismatches (especially on macOS Apple Silicon).

Supported platforms:
- Python: **3.12 and 3.13**
- OS: Linux or macOS recommended
- Windows: no native support claim; consider a Linux environment such as WSL2

The package metadata deliberately excludes Python 3.14. Python 3.13.9 was used
for the CP1 correctness audit, while Python 3.12 remains the Docker and FM/AE
baseline. No broader version claim is made until CI validates it.

## 3. What exactly needs to work (core requirement)
QSeqSim imports CUDD-backed BDDs via:

```python
from dd import cudd as _bdd
```

So the environment must satisfy:

1. `pip install dd` succeeds, and
2. `python -c "import dd.cudd"` succeeds.

Importing `qseqsim` performs the same check and fails with installation guidance
when the extension is absent. There is no automatic `dd.autoref` fallback.

If `dd.cudd` is missing, QSeqSim will not run.

## 4. Native install paths

On Linux x86_64 with CPython 3.12 or 3.13, ordinary pip selects a tested
manylinux `dd==0.6.0` wheel containing `dd.cudd`:

```bash
python -m pip install qseqsim
python -c "import dd.cudd, qseqsim; print(qseqsim.__version__, dd.cudd.__version__)"
```

This is a deliberately narrow platform claim. Always run the import check.

On macOS arm64, create a fresh environment and force the `dd` source build:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1 \
  python -m pip install --no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'
python -m pip install qseqsim
python -c "import dd.cudd, qseqsim; print(qseqsim.__version__, dd.cudd.__version__)"
```

The repository's `ae/scripts/install_dd_cudd.sh` performs the equivalent
download/unpack/build flow and remains useful for development or AE from a
source checkout. It is not included in the wheel or sdist and is not part of
the published-install contract.

### 4.1 What the source-checkout helper does (for debugging)

The helper performs:

1. `pip install dd`
- to install build dependencies / ensure pip can resolve requirements

2. `pip uninstall -y dd`
- remove it so we can rebuild from source

3. `pip download --no-deps dd --no-binary dd`
- download the **source distribution** (dd-*.tar.gz)

4. unpack sdist and set environment variables:
- `DD_FETCH=1`
fetch required third-party code (including CUDD) during build
- `DD_CUDD=1`
build the `dd.cudd` extension
- `DD_CUDD_ZDD=1`
build the `dd.cudd_zdd` extension

5. `pip install . -vvv --use-pep517 --no-build-isolation`
- build with verbose output and without build isolation (so toolchains/env are visible)

6. verify installation with: `python -c 'import dd.cudd'`

If you encounter errors, the -vvv logs usually show the missing header/library or compiler issue.

Note: Installing `dd` before CUDD exists may produce a non-CUDD installation.
Always run the explicit import check to ensure `dd.cudd` is present.

## 5. Verifying the installation
### 5.1 Verify `dd.cudd`
```bash
python -c "import dd.cudd; print('dd.cudd OK')"
```
### 5.2 Install and import QSeqSim
```bash
python -m pip install .
python -c "from qseqsim import QSeqSimulator; print(QSeqSimulator)"
```

For an editable development checkout:

```bash
python -m pip install -e '.[test,build]'
```

### 5.3 Run QSeqSim toy tests
From repository root:

```bash
python test/test_parser.py
python test/test_kernel.py
```

### 5.3 Minimal BDD check (optional)
```bash
python - <<'PY'
from dd import cudd
bdd = cudd.BDD()
bdd.declare('x', 'y')
u = bdd.add_expr(r'x /\ y')
s = bdd.to_expr(u)
print(s)
PY
```

## 6. Common problems & fixes
### 6.1 `ImportError: cannot import name 'cudd' from 'dd'`
Cause:

- `dd` was installed without CUDD extensions.

Fix (force a source rebuild with CUDD):

```bash
python -m pip uninstall -y dd
DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1 \
  python -m pip install --no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'
```

### 6.2 Build fails: missing compiler / Python headers
Linux:

- ensure you have build-essential and Python dev headers.
Example (Debian/Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y build-essential python3-dev
```
macOS:

ensure command line tools are installed:
```bash
xcode-select --install
```

Then rerun the source build:

```bash
DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1 \
  python -m pip install --no-cache-dir --no-binary=dd --no-build-isolation 'dd==0.6.0'
```

### 6.3 macOS: architecture mismatch (arm64 vs x86_64)
Symptoms:

- linker errors, “wrong architecture”, or `.so` cannot be loaded.

Check:

```bash
python -c "import platform; print(platform.machine())"
```

Fix:

- ensure Python and compiled extensions are the same architecture.
- if in doubt, prefer Docker.

### 6.4 Offline / restricted network environments
The script uses `DD_FETCH=1`, which may fetch dependencies during build.
If network access is restricted, use Docker or ensure dependencies are vendored in advance.

This repository includes:

- `third_party/dd-0.6.0.tar.gz`

You can try:

```bash
pip install third_party/dd-0.6.0.tar.gz
```

But **you still need** `dd.cudd`; if the build cannot fetch CUDD, prefer Docker for evaluation.

## 7. Reproducibility settings (sampling)
Some experiments (e.g., AE Table 3) use `mode="sample"` (random branching).
If supported by the runner, fix randomness via:

```bash
export QSEQSIM_RNG_SEED=123
```

See [ae/README.md](../ae/README.md) for AE-specific reproducibility strategy (frozen circuits + SHA256 manifest).
