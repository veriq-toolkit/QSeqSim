# Qiskit ecosystem benchmark

This benchmark positions QSeqSim relative to Qiskit Aer without treating either
simulator as a universal replacement for the other. It was run on 2026-08-12
with the checked-in `benchmarks/ecosystem_benchmark.py` harness.

## Environment and configuration

| Component | Value |
| --- | --- |
| Platform | macOS 26.5.2, Apple arm64 |
| Python | 3.13.9 |
| Qiskit | 2.4.2 |
| Qiskit Aer | 0.17.2 |
| Aer method | `statevector` |
| `dd` / NumPy | 0.6.0 / 2.4.2 |
| Seed | 20260812 |
| Performance shots | 512 |
| Correctness shots | 4096 per engine |
| Repeats / cutoff | 3 / 60 seconds per worker |

Each engine ran in a fresh worker process. The timed region is
`backend.run(...).result()`; circuit construction and transpilation are measured
separately and excluded from the table. Memory is the absolute peak RSS of that
isolated worker, so it includes the engine runtime and imports and should not be
interpreted as a pure circuit-state allocation.

Both engines receive the same source circuit and shots. QSeqSim executes a
complete symbolic classical-outcome distribution once and then samples it;
Aer performs its configured numerical shot simulation. The resulting counts
have comparable user semantics, but the internal computational tasks differ.
The wall-time ratios below are therefore **not** labeled speedups.

## Workloads and correctness

The suite contains:

- an ordinary Bell baseline, where Aer is expected to be highly competitive;
- a measurement-driven `while` and an `if` nested inside `while`;
- QRW bodies from the FM benchmark family at `(qubits, iterations)` equal to
  `(4, 1)`, `(8, 2)`, and `(12, 4)`; and
- Grover bodies from the FM benchmark family at `(4, 1)`, `(6, 2)`, and
  `(8, 4)`.

The structured families use a finite Qiskit `for_loop` around the original FM
QRW/Grover iteration body and measure all qubits at the end. This makes the
executed task finite and identical for both backends; it does not reproduce the
paper's specialized preset-path task or its largest scale.

For each case, 4096-shot runs were compared before performance measurement.
All nine cases had matching observed outcome support. Bell and both dynamic
cases also matched their analytical support (`00/11` and `01/11`,
respectively). Total-variation distances between engine counts ranged from
0.0049 to 0.0337, below the predeclared 0.10 sampling sanity threshold.

Aer 0.17.2 rejected the measurement-driven while when the `WhileLoopOp` was
literally the final circuit instruction, reporting `Invalid jump destination`.
Repeating the already deterministic guard measurement after the loop preserves
the result semantics and made the circuit executable. This compatibility detail
is recorded separately from performance; Aer successfully executed every
benchmark circuit actually reported below.

## Results

Median of three execution repeats:

| Case | Qubits | Iterations | Structure ops | Aer wall (s) | QSeqSim wall (s) | Aer peak RSS (MiB) | QSeqSim peak RSS (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bell | 2 | 0 | 3 | 0.0014 | 0.0349 | 96.9 | 163.5 |
| Measurement while | 2 | 1 | 5 | 0.0037 | 0.0400 | 96.9 | 163.6 |
| If in while | 3 | 1 | 6 | 0.0053 | 0.0406 | 96.7 | 163.3 |
| QRW | 4 | 1 | 12 | 0.0036 | 0.0593 | 96.7 | 171.1 |
| QRW | 8 | 2 | 40 | 0.0084 | 0.3052 | 96.9 | 204.2 |
| QRW | 12 | 4 | 108 | 0.1098 | 1.2768 | 97.9 | 301.3 |
| Grover | 4 | 1 | 25 | 0.0033 | 0.2438 | 97.2 | 275.9 |
| Grover | 6 | 2 | 68 | 0.0061 | 0.7276 | 97.0 | 655.2 |
| Grover | 8 | 4 | 172 | 0.0192 | 2.0987 | 96.8 | 1288.2 |

`Structure ops` is the expanded number of family-body operations plus final
measurements. The current distribution adapter does not expose a stable public
peak-BDD-node counter, so this reproducible structural metric is reported
instead of inventing a BDD-node number.

## Interpretation

Aer is faster and uses less process memory on every selected small-to-medium
case. This is an important negative result for broad performance claims:
QSeqSim should not be described as generally faster than Aer, including merely
because a circuit contains dynamic control flow.

The benchmark does validate the intended integration and semantics: current
Aer and QSeqSim can execute the reported dynamic circuits, and their sampled
results agree at small scale. QSeqSim's distinct value remains its BDD/WMC
representation, explicit sequential semantics, state retention, and complete
branch-distribution construction for structured workloads. Evidence for very
large structured preset-path cases remains in the separately reproducible FM
artifact and is not presented here as an apples-to-apples Aer advantage.

## Reproduce

From an environment with CUDD-backed `dd.cudd`:

```bash
python -m pip install -e '.[test,benchmark]'
python benchmarks/ecosystem_benchmark.py \
  --repeats 3 --shots 512 --correctness-shots 4096 --timeout 60
```

Machine-readable results are committed as:

- `benchmarks/results/ecosystem_benchmark_2026-08-12.csv`
- `benchmarks/results/ecosystem_benchmark_2026-08-12.json`

No temporary statevectors, CUDD dumps, or other large artifacts are retained.
