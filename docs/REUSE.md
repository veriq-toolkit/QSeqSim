# Reuse & Extension Guide (QSeqSim)

This document explains how to **extend QSeqSim** for new research usage:

- add new benchmarks / toy programs,
- add new gates end-to-end (parser → simulator → kernel),
- create regression tests,
- recommended project conventions.

This guide complements:

- [docs/USER_GUIDE.md](USER_GUIDE.md) (library API & semantics)
- [ae/README.md](../ae/README.md) (artifact evaluation reproduction)

---

## 1. Reuse entry points (recommended)

### 1.1 Use QSeqSim as a library (recommended stable API)

- Parse: `src.parser.QiskitParser`
- Execute: `src.simulator.BDDSimulator`

See: [docs/USER_GUIDE.md](USER_GUIDE.md)

### 1.2 Use the kernel directly (advanced)

For very large structured sequential workloads (e.g., QRW/Grover style), some experiments may bypass Qiskit parsing and call the kernel directly.

- Combinational kernel: `src.kernel.BDDCombSim`
- Sequential kernel: `src.kernel.BDDSeqSim`

> Kernel-level usage is considered “advanced”: it is powerful but closer to the implementation details.

Parser-compatible QRW/Grover constructors are also available when a downstream
harness needs standard Qiskit circuits:

- `src.benchmark_circuits.build_qrw_loop_circuit(n)`
- `src.benchmark_circuits.build_grover_loop_circuit(n)`

These builders mirror the operation order in `exp/simulation/qrw.py` and
`exp/simulation/grover.py`, then encode the benchmark as a Qiskit `while_loop`
whose guard is updated by measuring `q[0]` into `c[0]`.

Single-loop SQC programs can also be lowered from the parsed IR to the
`BDDSeqSim` execution model through `src.seqsim_lowering`. The lowering is
structural rather than benchmark-name based: it accepts one top-level `SQC`
whose body is linear `CQC` code followed by measurements of the loop's external
input qubits into the loop flag. Those external qubits are remapped to the
`BDDSeqSim` input prefix and the remaining qubits become stored state.

---

## 2. Add a new benchmark (recommended workflow)

### 2.1 Add a runnable toy example (preferred for reuse)

Place a self-contained script under:

- `examples/<name>.py`

Guidelines:

- keep it < 100 lines if possible,
- always add repo root to `sys.path` at runtime (to support `python examples/x.py`),
- print something users can sanity-check (e.g., parsed blocks, clbits, global_probability),
- avoid huge circuits by default.

Minimal template:

```python
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from src.parser import QiskitParser
from src.simulator import BDDSimulator

# build circuit ...
parser = QiskitParser(qc)
blocks = parser.parse()

sim = BDDSimulator(blocks)
out = sim.run(mode="sample")  # or preset
print(out)
```

### 2.2 Add an experiment benchmark (paper/AE style)

If you want integration with the existing experiment engine, follow the convention used by:

* `exp/simulation/<group>/<name>.py`

Typical contract (as used by the experiment runner):

* define `circ: QuantumCircuit`
* define `sim_mode: Literal["sample","preset"]`
* if preset: define `preset_values: dict[int, list[int]]`

Then run:

```bash
python exp/simulation/exp_engine.py <group>/<name>
```

---

## 3. Add a new gate end-to-end (Parser → Simulator → Kernel)

Supporting a new gate usually requires updates in  **three places** .

### Step A: Parser (`src/parser.py`)

Goal: ensure the gate appears in the IR as a supported `GateOp`.

1. Add the gate name to:

* `QiskitParser.SUPPORTED_GATES`

2. Update `_parse_gate`:

* If the gate is already in the kernel’s native set: map its name directly.
* If it is a rotation gate: either (i) decompose it into existing supported gates, or (ii) reject unsupported parameters with a clear error message.

**Example patterns already implemented**

* `rx(±pi/2)` → `x2p` (or `z; x2p; z` for `-pi/2`)
* `ry(±pi/2)` → `y2p` (or `x; y2p; x`)
* `rz/p` → `{s, sdg, t, tdg, z}` for discrete angles

### Step B: Simulator dispatch (`src/simulator.py`)

Goal: ensure `GateOp.name` maps to a kernel method.

Update:

* `BDDSimulator.GATE_METHOD_MAP`

Example:

* parser emits `op.name == "cx"`
* simulator maps `"cx" -> "CNOT"`
* kernel implements `CNOT(control, target)`

### Step C: Kernel implementation (`src/kernel.py`)

Goal: implement the actual symbolic state update.

* In `BDDCombSim`, implement a method with the mapped name (e.g., `U3`, `RX`, etc.), **or**
* implement a generic `apply_gate(name, qubits)` method and rely on simulator fallback (currently the simulator checks for `apply_gate` if direct method is absent).

> Recommendation: implement explicit methods for new gates if they are used often, for better performance and clarity.

---

## 4. Add/modify measurement behavior (advanced)

QSeqSim distinguishes:

* mid-circuit measurement: collapses and updates `global_probability`,
* final measurement: readout only.

This behavior is controlled by:

* parser pass: `_mark_final_measurements` (sets `GateOp.is_final_measure`)
* simulator: `_handle_measurement` and `_decide_final_measure_value`

If you change the rule for “final measurement”, document it in:

* [docs/USER_GUIDE.md](USER_GUIDE.md): §4.3.

---

## 5. Testing (recommended minimal standard)

QSeqSim includes runnable regression scripts under `test/`:

* `test/test_parser.py`: exercises CQC/DQC/SQC parsing + simulation
* `test/test_kernel.py`: exercises kernel gate updates and amplitude printing

### 5.1 Add a new regression test

Add a new script:

* `test/test_<feature>.py`

Guidelines:

* keep runtime short (< 5 seconds in Docker),
* avoid huge qubit counts,
* test one feature per script (e.g., “new gate decomposition”, “new control-flow pattern”).

### 5.2 Run tests

```bash
python test/test_parser.py
python test/test_kernel.py
```

---

## 6. Reproducibility tips (sampling)

* For experiments involving sampling (`mode="sample"`), consider fixing randomness.
* If you use an environment variable (e.g., `QSEQSIM_RNG_SEED`) in scripts, document it and ensure it is applied consistently (e.g., `random.seed(...)` in the experiment entry point).

---

## 7. Documentation rules (for maintainability)

* Put user-facing docs under `docs/` only.
* Ensure [README.md](../README.md) links to:
  * [docs/USER_GUIDE.md](USER_GUIDE.md)
  * [docs/REUSE.md](REUSE.md)
  * [examples/](../examples/)
  * [test/](../test/)
  * [ae/README.md](../ae/README.md)
* Keep AE instructions in [ae/README.md](../ae/README.md) (stable for reviewers).
