# QSeqSim User Guide (Library Usage & Reuse)

This guide explains how to **use QSeqSim as a Python library**, how to run **toy examples** and **tests**, and how to **extend** the supported gate set / benchmarks.
It complements:

- AE reproduction instructions: [ae/README.md](../ae/README.md)
- Project overview: [README.md](../README.md)

> Recommended environment: **Docker** (contains CUDD + dd). Native installs are possible but less stable.

---

## 1. Quickstart (Docker, recommended)

### 1.1 Enter the container

From the repository root:

```bash
docker build -t qseqsim-ae .
docker run --rm -it qseqsim-ae:latest bash
```

Inside the container, `cd` to the repo root if needed.

### 1.2 Run toy examples

```bash
python examples/while_minimal.py
python examples/branching_if_switch.py
python examples/reachability_rus_pattern.py
```

### 1.3 Run the built-in tests (toy programs + regression)

```bash
python test/test_parser.py
python test/test_kernel.py
```

---

## 2. Minimal library workflow

The intended “public” workflow is:

1. Write a `qiskit.QuantumCircuit` with classical control (`if_test`, `switch`, `while_loop`, `for_loop`, mid measurements).
2. Parse it with `qseqsim.QiskitParser` into an internal IR (blocks of `CQC/DQC/SQC`).
3. Execute the IR with `qseqsim.QSeqSimulator`, which delegates state updates and probability computations to the existing BDD kernel.

The parser still uses the FM implementation's Qiskit → OpenQASM 3 → IR route.
A direct `QuantumCircuit`/`ControlFlowOp` frontend is not part of CP2.

### 2.1 End-to-end minimal snippet

```python
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qseqsim import QSeqSimulator, QiskitParser

q = QuantumRegister(1, "q")
c = ClassicalRegister(1, "c")
qc = QuantumCircuit(q, c)

qc.h(q[0])
qc.measure(q[0], c[0])     # may become "final" or "mid" depending on later control use

parser = QiskitParser(qc)
blocks = parser.parse()

sim = QSeqSimulator(blocks, precision=32)
clbits = sim.run(mode="sample")
print("classical store:", clbits)
sim.print_state_vec()
```

---

## 3. Core APIs (stable surface)

This section documents the API that users should rely on for reuse.

### 3.1 `QiskitParser` (OpenQASM 3 → CQC/DQC/SQC blocks)

**Public import:** `from qseqsim import QiskitParser`

**Class:** `QiskitParser`

#### Constructor

```python
QiskitParser(circuit: QuantumCircuit | None = None)
```

* `circuit`: optional Qiskit circuit. If provided, `parse()` will export QASM3 via `qiskit.qasm3.dumps`.

#### Main method

```python
parse() -> list
```

Returns a list of *blocks* preserving program order:

* `CQC`: straight-line quantum gates and measurements
* `DQC`: branching (`if/else`, `switch`) controlled by classical bits
* `SQC`: `while` loops with validation and external/internal qubit partitioning

#### Supported gate set (Clifford+T + a few multi-qubit gates)

The parser accepts (after normalization/decomposition):

* 1-qubit: `x y z h s sdg t tdg x2p y2p`
* 2-qubit: `cx cz swap`
* 3-qubit: `ccx` (Toffoli), `cswap` (Fredkin)
* ops: `measure`, `break`
* `for_loop` is unrolled if Qiskit emits it as `ForInLoop` in QASM3.

Rotation support:

* `rx(±pi/2)` → `x2p` / `z; x2p; z`
* `ry(±pi/2)` → `y2p` / `x; y2p; x`
* `rz` / `p` only for angles in `{0, ±pi/2, ±pi, ±pi/4, ±3pi/2, ±7pi/4}` mapped to `s/sdg/z/t/tdg`.

If a gate/angle is unsupported, `parse()` raises a `ValueError` with a descriptive message.

---

### 3.2 IR objects: `GateOp`, `CQC`, `DQC`, `SQC`

**Public import:** `from qseqsim import CQC, DQC, SQC, GateOp`

* `GateOp(name, qubits, params=None, c_targets=None, is_final_measure=False)`
  * `name`: gate name (lowercase, e.g. `"h"`, `"cx"`, `"measure"`)
  * `qubits`: global integer qubit indices
  * `c_targets`: global integer classical bit indices (for measurement)
  * `is_final_measure`: set by a global marking pass (see §4)
* `CQC(ops, global_num_qubits)`: straight-line sequence of `GateOp`
* `DQC(target_clbits, cases, default_block, global_num_qubits)`: branch selection by a classical value
* `SQC(loop_condition, body_block, global_num_qubits)`: while-loop, validated such that trigger measurements are final in the loop body 

---

### 3.3 `QSeqSimulator` (small-step semantics over blocks)

**Public import:** `from qseqsim import QSeqSimulator`

`QSeqSimulator` is a lightweight public subclass of the research implementation's
`BDDSimulator`; the latter remains exported during migration.

#### Constructor

```python
QSeqSimulator(parsed_blocks: list, precision: int = 32)
```

* Initializes a BDD kernel `BDDCombSim(num_qubits, precision)` and sets basis state to |0…0⟩ if supported by the kernel.

#### Execute

```python
run(mode: str = "sample", presets: dict[int, list[int]] | None = None) -> dict[int, int]
```

* `mode="sample"`: measurement outcomes are sampled using exact probabilities from the kernel (`get_prob`) when available.
* `mode="preset"`: mid-circuit measurements consume preset bits from `presets[c_idx]` (FIFO). If missing for **mid** measurement → error.
* Returns `clbit_store: dict[int,int]` mapping global classical-bit indices to observed values.
* If exact symbolic probability evaluation exceeds Python's recursion limit,
  raises `qseqsim.SymbolicEvaluationError`. QSeqSim does not substitute a
  uniform or approximate distribution.

#### Inspect final state

```python
print_state_vec()
```

Prints the **normalized** state vector using `global_probability` as a normalization factor.

For performance, it refuses to print full vectors when `num_qubits > 20`.

---

## 4. Measurement semantics: mid vs final (important)

QSeqSim distinguishes between mid-circuit measurements and final measurements.

### 4.1 Mid-circuit measurements (`is_final_measure == False`)

* Used for control flow or subsequent computation.
* Simulator behavior:
  1. Query unnormalized joint probabilities via `kernel.get_prob([q],[0/1])`
  2. Normalize to obtain real distribution
  3. Decide outcome (sample/preset)
  4. Multiply `global_probability` by the chosen branch probability
  5. Collapse the symbolic state using `kernel.mid_measure([q],[b])`
  6. Write `clbit_store[c] = b`

### 4.2 Final measurements (`is_final_measure == True`)

* Intended as “readout” only.
* Simulator behavior:
  * Generates a classical value (sample or preset if provided),
  * **does not collapse** the quantum state,
  * **does not update** `global_probability`,
  * writes `clbit_store[c]`.

### 4.3 How final measurements are marked

After parsing, the parser runs a global IR pass:

* For each qubit, find its **last operation** in the program’s (conservatively linearized) traversal.
* If the last operation is `measure`, and its classical target is **not used in any control-flow condition** (`if/switch/while` guards), mark it as `is_final_measure=True`.

This makes readout behave like a final observation rather than a semantic state collapse that affects earlier probabilities.

---

## 5. “Reachability query” patterns (how to use preset mode)

A common formal-methods use case is to ask:

> What is the probability of a specific measurement-outcome pattern across iterations?

In QSeqSim this is implemented via:

* `mode="preset"` for mid-measurements (fixes a unique execution path)
* the simulator accumulates `global_probability`, which equals the probability of that path.

See `examples/reachability_rus_pattern.py` for a minimal pattern query.

---

## 6. Troubleshooting / common errors

### 6.1 Unsupported gates / angles

* Error: `Unsupported Gate: ...` or `Unsupported Rx angle: ...`
* Fix: transpile/decompose the circuit into the supported Clifford+T fragment and allowed angles.

### 6.2 Infinite loops / too many iterations

* Error: `Max iterations (= 1000) reached in SQC.`
* Cause: loop guard never changes to terminate.
* Fix: ensure the loop body measures and updates the guard bits; or reduce the workload / adjust the program.

### 6.3 Symbolic probability evaluation failure

* Error: `SymbolicEvaluationError: Exact symbolic evaluation failed because the recursion limit was reached ...`
* Meaning: the exact kernel probability query could not complete within
  Python's recursion limit. The run stops; no 0.5 fallback or approximate
  result is returned. Simplify the circuit or symbolic state before retrying.

### 6.4 Printing state vectors for many qubits

* `print_state_vec()` is intentionally limited (`>20` qubits) to avoid exponential output.

### 6.5 Numeric result limits

The kernel performs integer model counts exactly and evaluates the final
algebraic probability with 150-digit `Decimal` arithmetic. The current public
`get_prob()` result and `QSeqSimulator.global_probability`, however, are Python
binary64 floats. They therefore retain about 16 significant decimal digits and
can represent positive values down to approximately `4.94e-324`; an exact
probability of `2**-1075` converts to zero. Long path-probability products have
the same binary64 underflow boundary. This is a result-API limit, not a switch
to approximate symbolic model counting.

### 6.6 Control-flow and lowering boundaries

* The general `QSeqSimulator`/`BDDSimulator` IR executor supports the tested
  nested `if`-inside-`while` and measurement-driven loops.
* A loop run stops before iteration 1001 and raises
  `RuntimeError("Max iterations (= 1000) reached in SQC.")` if its guard still
  holds.
* The specialized `BDDSeqSim` structural lowering accepts one top-level SQC
  with a flat CQC body and trailing loop-flag measurements. It deliberately
  rejects nested `DQC`/`SQC` blocks and mid-body measurements.
* Measurements that update an SQC loop guard must be the last operation on
  their measured qubits under the current parser/IR validation.

The CP3 direct-`QuantumCircuit` frontend may remove limitations caused solely
by the OpenQASM 3 translation route. It does not by itself change the
specialized `BDDSeqSim` lowering contract, the SQC IR validation, or the
1000-iteration executor guard; those require separate explicit changes.

---

## 7. Extending QSeqSim (high-level)

For adding a new gate end-to-end (parser → simulator → kernel), see [docs/REUSE.md](REUSE.md).
