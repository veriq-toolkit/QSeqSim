# CP4 BackendV2 integration gate

## Architecture

CP4 adds a compatibility layer without changing or copying the symbolic
kernel:

```text
QuantumCircuit
  -> CP3 QuantumCircuitParser
  -> CQC / DQC / SQC
  -> BDDCombSim branch-distribution execution
  -> {classical integer: probability}
  -> seeded shot sampling
  -> QSeqSimJob(JobV1) / qiskit.result.Result
```

`QSeqSimulator` remains the native symbolic/path API. `QSeqSimBackend` is the
Qiskit provider API for `transpile`, jobs, counts, and memory. The Backend path
does not call `qiskit.qasm3.dumps`, `openqasm3.parse`, the compatibility
`QiskitParser`, BackendV1, or any primitive/Sampler interface.

## Target

The default target has 256 qubits and is configurable with
`QSeqSimBackend(num_qubits=...)`. It is an ideal all-to-all simulator target and
does not claim durations, errors, calibrations, or physical qubit properties.

Advertised fixed-domain operations are:

```text
x y z h s sdg t tdg cx cz swap ccx cswap measure
```

`MCXGate` is declared as the official variable-width class-form `mcx`
operation. `IfElseOp`, `WhileLoopOp`, and `ForLoopOp` are likewise added by
class with the public Qiskit names `if_else`, `while_loop`, and `for_loop`.
Switch, break, continue, classical-expression, and Store capabilities are not
claimed. The direct frontend's discrete rotation subset is intentionally not
advertised as an unrestricted parameterized Target instruction.

## Distribution and result semantics

The pre-CP4 native sampled executor selects one measurement path and therefore
cannot supply a complete backend distribution. CP4 adds a separate
`run_distribution()` path. Each measurement forks independent CUDD-backed
kernel states, weights them by conditional probability, continues dynamic
control flow independently, and aggregates final classical stores. Final
readouts use the same sequential conditioning, which preserves multi-qubit
correlations.

Each input circuit invokes this symbolic distribution computation exactly once,
regardless of `shots`. The Backend layer uses one seeded Python RNG to sample
the resulting probability map. Counts and optional per-shot memory are encoded
as hexadecimal raw values in the Qiskit Result schema; Qiskit's public
`get_counts()` and `get_memory()` perform register-aware formatting.

Defaults and supported runtime options are:

- `shots=1024` (positive integer)
- `memory=False` (boolean)
- `seed_simulator=None` (integer or `None`)

Unknown options and invalid types fail explicitly. The local job is synchronous
and returned in `DONE` state. Parser, loop-guard, and exact symbolic evaluation
errors propagate from `run()`; no successful error-bearing Result is created.

## Transpilation boundary

Ordinary supported circuits transpile against the target. Supported dynamic
circuits also transpile when their bodies and conditions remain inside the
declared Target subset. Direct execution does not require prior transpilation.
Any future Qiskit transpiler restriction should be reported separately from
the direct execution capability.

## Scope

CP4 adds no `BaseSamplerV2`, `BackendSamplerV2`, BackendV1, PyPI upload, or
ecosystem submission. The FM tag and branches remain at commit `67ae057`.

## Validation

Validated on Python 3.12.3 with Qiskit 2.4.2 and canonical `dd.cudd` 0.6.0:

- full pytest suite: 51 passed;
- BackendV2/Target, Bell correlation, deterministic results, seeded memory,
  multiple circuits, multiple classical registers, dynamic execution,
  failure propagation, and one-distribution-call-per-circuit regressions passed;
- ordinary and supported dynamic circuits transpiled against the Target and
  executed successfully;
- wheel and sdist built successfully;
- `twine check` passed for both artifacts;
- a fresh repository-external wheel environment passed import, transpile,
  backend counts/memory, and raw OpenQASM compatibility smoke tests;
- AE smoke Table 1, Table 2a, Table 2b, Table 3, Table 4, and Table 5 all
  completed successfully.
