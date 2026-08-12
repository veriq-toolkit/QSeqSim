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

The recommended public workflow is:

1. Write a supported `qiskit.QuantumCircuit` with gates, measurements, and optionally `if_test`, `while_loop`, or `for_loop`.
2. Pass it directly to `qseqsim.QSeqSimulator`.
3. Execute it; the direct frontend maps Qiskit bits and control-flow blocks to `CQC/DQC/SQC` IR without OpenQASM serialization.

`OpenQASM3Parser` (and its compatibility name `QiskitParser`) remains the
secondary interchange/FM path. It is intentionally separate from the direct
frontend.

### 2.1 End-to-end minimal snippet

```python
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qseqsim import QSeqSimulator

q = QuantumRegister(1, "q")
c = ClassicalRegister(1, "c")
qc = QuantumCircuit(q, c)

qc.h(q[0])
qc.measure(q[0], c[0])     # may become "final" or "mid" depending on later control use

sim = QSeqSimulator(qc, precision=32)
clbits = sim.run(mode="sample")
print("classical store:", clbits)
sim.print_state_vec()
```

---

## 3. Core APIs (stable surface)

This section documents the API that users should rely on for reuse.

The one-shot spelling `QSeqSimulator().run(qc)` is also supported. Existing IR
callers can continue to construct `QSeqSimulator(parsed_blocks)`.

### 3.1 `QuantumCircuitParser` (recommended direct frontend)

**Public import:** `from qseqsim import QuantumCircuitParser`

```python
blocks = QuantumCircuitParser(qc).parse()
```

The parser walks `QuantumCircuit.data`. For each control-flow instruction, its
outer `qubits`/`clbits` are first translated through the current circuit frame;
the resulting global indices are then positionally zipped with every inner
block's `qubits`/`clbits`. This is why reordered and subset operands do not rely
on coincident local/global indices.

`QiskitCircuitFrontend` is an equivalent descriptive alias.

### 3.2 `OpenQASM3Parser` / `QiskitParser` (secondary frontend)

**Public import:** `from qseqsim import OpenQASM3Parser, QiskitParser`

**Class:** `QiskitParser`

#### Constructor

```python
OpenQASM3Parser(circuit: QuantumCircuit | None = None, *, qasm_str: str | None = None)
```

* `qasm_str`: raw OpenQASM 3 interchange text.
* `circuit`: compatibility input. If provided, this secondary path exports via `qiskit.qasm3.dumps` before parsing.

#### Main method

```python
parse() -> list
```

Returns a list of *blocks* preserving program order:

* `CQC`: straight-line quantum gates and measurements
* `DQC`: branching controlled by classical bits
* `SQC`: `while` loops with validation and external/internal qubit partitioning

#### Supported gate set (Clifford+T + a few multi-qubit gates)

The parser accepts (after normalization/decomposition):

* 1-qubit: `x y z h s sdg t tdg x2p y2p`
* 2-qubit: `cx cz swap`
* 3-qubit: `ccx` (Toffoli), `cswap` (Fredkin)
* ops: `measure`, `break` (OpenQASM compatibility path only)
* `for_loop` is unrolled if Qiskit emits it as `ForInLoop` in QASM3.

Rotation support:

* `rx(±pi/2)` → `x2p` / `z; x2p; z`
* `ry(±pi/2)` → `y2p` / `x; y2p; x`
* `rz` / `p` only for angles in `{0, ±pi/2, ±pi, ±pi/4, ±3pi/2, ±7pi/4}` mapped to `s/sdg/z/t/tdg`.

If a gate/angle is unsupported, `parse()` raises a `ValueError` with a descriptive message.

### 3.3 Direct Qiskit feature matrix

| Feature | Status | Direct frontend behavior |
| --- | --- | --- |
| `x y z h s sdg t tdg` | Supported | Direct `GateOp` mapping |
| `cx cz swap ccx cswap mcx` | Supported | Direct operand mapping |
| `rx(±pi/2)`, `ry(±pi/2)` | Supported | Existing discrete decomposition |
| `rz` / `p` Clifford+T angles | Supported | Existing discrete decomposition |
| `measure` | Supported | Global qubit/clbit targets; existing final-readout pass |
| Tuple condition `(Clbit, int)` | Supported | One global condition bit |
| Tuple condition `(ClassicalRegister, int)` | Supported | Little-endian ordered global bits |
| `IfElseOp` | Supported | `DQC` case + default block |
| `WhileLoopOp` | Supported | `SQC`; existing validation and 1000-iteration guard |
| `ForLoopOp` | Supported | Finite frontend unrolling; loop parameter bound per iteration |
| Nested `if` inside `while` | Supported | Nested `DQC` in `SQC` for the general executor |
| `SwitchCaseOp` | Unsupported | `UnsupportedQiskitFeatureError` naming op/type |
| `BreakLoopOp`, `ContinueLoopOp` | Unsupported | Same explicit error; no partial semantics |
| Classical expression conditions | Unsupported | Explicit error naming the owning control-flow op |
| Dynamic variables / `Store` | Unsupported | Explicit dynamic-variable or `Store` error |
| Nonzero or symbolic circuit `global_phase` | Unsupported | Explicit error; never silently discarded |
| Other gates/instructions | Unsupported | Explicit error naming instruction type and op name |

`ForLoopOp` is not represented by a new runtime IR node because the current IR
has no counted-loop semantics. Finite unrolling is exact for the supported body,
including parameter binding and nested supported control flow.

### 3.4 IR objects: `GateOp`, `CQC`, `DQC`, `SQC`

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

### 3.5 `QSeqSimulator` (small-step semantics over blocks)

**Public import:** `from qseqsim import QSeqSimulator`

`QSeqSimulator` is a lightweight public subclass of the research implementation's
`BDDSimulator`; the latter remains exported during migration.

#### Constructor

```python
QSeqSimulator(program: QuantumCircuit | list | None = None, precision: int = 32)
```

* A `QuantumCircuit` is parsed through `QuantumCircuitParser` without OpenQASM.
* A list preserves the CP2 parsed-IR contract.
* `None` permits later use of `run(qc)` or `run(circuit=qc, ...)`.

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
* To load while running, use `run(qc)` for sample mode or
  `run(mode="preset", presets=..., circuit=qc)`.

#### Inspect final state

```python
print_state_vec()
```

Prints the **normalized** state vector using `global_probability` as a normalization factor.

For performance, it refuses to print full vectors when `num_qubits > 20`.

### 3.6 `QSeqSimBackend` (Qiskit BackendV2 compatibility)

**Public imports:**

```python
from qseqsim import QSeqSimBackend, QSeqSimJob
```

`QSeqSimBackend` is a real `qiskit.providers.BackendV2`. Its `Target` is an
ideal all-to-all simulator target with no invented durations, errors, pulse
data, or qubit properties. The target declares the complete-domain native
operations `x y z h s sdg t tdg cx cz swap ccx cswap mcx measure` and the
official class-form `IfElseOp`, `WhileLoopOp`, and `ForLoopOp` capabilities.
Discrete-angle `rx/ry/rz/p` operations remain valid for direct execution but
are not advertised as general parameterized Target operations. Unsupported
`switch/break/continue` operations are not declared.

```python
backend = QSeqSimBackend(num_qubits=32, precision=32)
job = backend.run(
    qc,
    shots=1024,
    memory=True,
    seed_simulator=1234,
)
result = job.result()
counts = result.get_counts()
memory = result.get_memory()
```

`run()` accepts one `QuantumCircuit` or a non-empty circuit sequence. Runtime
options are `shots` (default `1024`), `memory` (default `False`), and
`seed_simulator` (default `None`). Unknown or ill-typed options fail before
execution. `QSeqSimJob` is a synchronous, already-completed `JobV1`; its result
is Qiskit's public `Result`, not a QSeqSim-specific dictionary. Raw experiment
counts and memory use Qiskit's hexadecimal schema, so `get_counts()` and
`get_memory()` apply the official classical-register formatting, including
multiple-register ordering.

The execution layers are:

```text
QuantumCircuit
  -> QuantumCircuitParser (direct; no qasm3.dumps)
  -> one symbolic branch-distribution execution per circuit
  -> complete integer classical outcome -> binary64 probability map
  -> seeded compatibility-layer shot sampling
  -> QSeqSimJob / qiskit.result.Result
```

At each measurement the distribution executor clones the canonical CUDD state,
collapses each nonzero branch, continues that branch through `DQC`/`SQC`
control flow, and aggregates equal final classical stores. This preserves joint
readout correlations such as Bell `00/11`. Increasing `shots` does not increase
the number of symbolic circuit executions. The existing 1000-iteration guard
still applies to every reachable loop branch. Symbolic and unsupported-feature
failures propagate directly from `backend.run()` and do not produce a success
result.

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

The direct `QuantumCircuit` frontend removes limitations caused solely by the
OpenQASM 3 translation route. It does not change the
specialized `BDDSeqSim` lowering contract, the SQC IR validation, or the
1000-iteration executor guard; those require separate explicit changes.

---

## 7. Extending QSeqSim (high-level)

For adding a new gate end-to-end (parser → simulator → kernel), see [docs/REUSE.md](REUSE.md).
