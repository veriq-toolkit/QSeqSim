# Qiskit ecosystem benchmark

QSeqSim complements, rather than replaces, Aer. Aer remains the stronger
default for small and general numerical simulation. QSeqSim targets structured
dynamic and sequential workloads whose requested symbolic output remains
compact. The positive result below is deliberately presented first, followed
immediately by its output-semantics and platform boundaries.

## Q4-A — fair projected-backend comparison

Q4-A gives Aer statevector, Aer matrix-product state (MPS), and
`QSeqSimBackend` the same source `QuantumCircuit` for each case. Both QRW and
Grover use the same two finite structured iterations, measure only `q[0]` into
one classical bit, request 1,024 shots with seed 20260812, and time the same
region: `backend.run(...).result()`. Circuit construction and optimization-level
0 transpilation for each backend target are recorded but excluded. Each point
runs in three fresh workers with the same 120-second per-worker cutoff.

The one-bit projection is not a hidden engine-specific simplification: it is a
legitimate projected-observable/backend task, and all three engines receive the
same requested output. Its importance is part of the result. Q3 later provides
the full-register negative control: expanding the requested symbolic output can
increase QSeqSim's branch count and reverse the performance conclusion.

At q12, 4,096-shot correctness bridges passed for both families. Aer MPS and
statevector produced identical seeded counts; QSeqSim's TVD from statevector
was 0.00488 for QRW and 0.00146 for Grover. All methods had support `0/1`.

### Backend latency

The tables report median seconds only for completed workers. `TO` is a
120-second timeout, `—` means not run after that method's earlier boundary,
and `mixed` is not a stable baseline.

| QRW qubits | Aer statevector | Aer MPS | QSeqSim |
| ---: | ---: | ---: | ---: |
| 12 | 0.0571 | 24.5641 | 0.1782 |
| 14 | 0.2485 | 35.3508 | 0.2471 |
| 16 | 1.6333 | 58.9623 | 0.3425 |
| 18 | 7.3757 | 91.9451 | 0.3175 |
| 20 | 40.2905 | mixed: 2/3, 115.9696 median | 0.2678 |
| 24 | TO | — | 0.3400 |
| 32 | — | — | 0.5957 |
| 64 | — | — | 1.7534 |
| 128 | — | — | 7.7620 |
| 256 | — | — | 44.5866 |
| 512 | — | — | TO |

| Grover qubits | Aer statevector | Aer MPS | QSeqSim |
| ---: | ---: | ---: | ---: |
| 12 | 0.3282 | 14.0183 | 0.3099 |
| 14 | 3.1560 | 22.0089 | 0.3177 |
| 16 | 11.3096 | 25.4989 | 0.3726 |
| 18 | 54.0111 | 43.8055 | 0.3707 |
| 20 | TO | mixed: 1 success, 115.6566 | 0.4186 |
| 24 | — | — | 0.4888 |
| 32 | — | — | 0.6839 |
| 64 | — | — | 2.7160 |
| 128 | — | — | 16.3595 |
| 256 | — | — | TO |

The main latency ratios use only points where both QSeqSim and at least one Aer
method completed all 3/3 workers. They compare medians from the same machine,
case, shots, and timed boundary, using the fastest stable Aer method at that
point. QRW improves from 4.77× at q16 to 23.23× at q18 and 150.45× at q20;
Grover improves from 9.93× at q14 to 30.35× at q16 and 118.16× at q18. The q20
MPS mixed points are shown for completeness but are excluded from these ratios.
The observed crossover region is approximately q14–q16 for these selected
one-bit workloads, not for large circuits or projections in general.

### Stable-width boundary under the cutoff

“Stable” means all 3/3 fresh workers completed. A 2/3 or 1-success point is
mixed evidence and never promoted to the stable boundary.

| Family | Aer statevector | Aer MPS | QSeqSim |
| --- | --- | --- | --- |
| QRW | stable through q20; q24 TO | stable through q18; q20 mixed 2/3 | stable through q256; q512 TO |
| Grover | stable through q18; q20 TO | stable through q18; q20 mixed 1 success | stable through q128; q256 TO |

Thus QSeqSim reached a larger stable tested width only under this 120-second
per-worker cutoff and for these projected two-iteration workloads. Later widths
after a method's boundary are `not_run_after_boundary`, not “unsupported.”

Selected memory figures are absolute isolated-worker peak RSS: QRW q20 was
790.8 MiB for statevector and 148.6 MiB for QSeqSim; Grover q18 was
250.4/139.7/140.3 MiB for statevector/MPS/QSeqSim. QSeqSim was 138.2 MiB at
QRW q256 and 153.2 MiB at Grover q128. These totals include imports, runtime,
and allocators; they are not pure statevector, MPS, or BDD-state allocations.

### Symbolic build and sampling decomposition

All successful Q4-A QSeqSim points had exactly two output branches. Sampling
was negligible relative to constructing the complete projected distribution:

| Family / width | Build (s) | Sampling (s) | Total (s) | Outcomes |
| --- | ---: | ---: | ---: | ---: |
| QRW q16 | 0.3414 | 0.000208 | 0.3425 | 2 |
| QRW q128 | 7.7616 | 0.000101 | 7.7620 | 2 |
| QRW q256 | 44.5857 | 0.000180 | 44.5866 | 2 |
| Grover q16 | 0.3723 | 0.000075 | 0.3726 | 2 |
| Grover q128 | 16.3591 | 0.000070 | 16.3595 | 2 |

This is why output semantics cannot be separated from the performance claim:
Q4 constructs a two-outcome `q[0]` marginal, while Q3's full-register Grover
distribution reaches 2,048 branches at only q12.

## Q4-B — conditioned-path capability

Q4-B parses an actual Qiskit measurement-driven `while` circuit and uses the
existing BDDSeqSim lowering to retain sequential symbolic state along the fixed
measurement path `[0, ..., 0, 1]`.

| Family | Qubits | Path iterations | Total (s) | Peak RSS (MiB) | Probability |
| --- | ---: | ---: | ---: | ---: | ---: |
| QRW | 16 | 1 | 0.0326 | 146.6 | 0.5 |
| QRW | 128 | 1 | 0.3400 | 135.6 | 0.5 |
| QRW | 1,024 | 1 | 99.1037 | 273.8 | 0.5 |
| QRW | 16 | 3 | 0.0476 | 146.9 | 0.125 |
| QRW | 128 | 3 | 1.0408 | 160.2 | 0.125 |
| Grover | 16 | 1 | 0.0527 | 146.4 | 0.5 |
| Grover | 128 | 1 | 0.3238 | 150.9 | 0.5 |
| Grover | 256 | 1 | 0.7728 | 156.3 | 0.5 |

The 1,024-qubit row proves that one conditioned symbolic path actually ran; it
is not merely circuit construction or parsing. It is capability evidence only:
it is neither a full distribution nor a sampled `Backend.run`, and no Aer
speedup is calculated because the output objects differ. Dense-state storage
arithmetic is not evidence that MPS is infeasible; the only MPS boundary claimed
here is the measured Q4-A boundary on the identical projected task.

## Q1 — Qiskit compatibility

At 4,096 shots per engine, Aer statevector and QSeqSim passed all nine tested
circuits: Bell, two measurement-driven dynamic cases, three QRW cases, and
three Grover cases. TVD was 0.0049–0.0337, below the predeclared 0.10 sampling
sanity threshold. Aer 0.17.2 needs a repeated deterministic guard measurement
after a while-last-instruction shape; both engines receive that same semantic
circuit rather than engine-specific variants.

## Q2 — shot amortization

Mac median backend-call times show the expected one-time symbolic-build
amortization. Measurement-while crosses between 1k and 10k shots and QRW q8/i2
between 10k and 100k; Grover q6/i2 has no crossover through 100k shots.

| Case | Engine | 1 shot | 1k | 10k | 100k |
| --- | --- | ---: | ---: | ---: | ---: |
| Measurement while | Aer statevector | 0.0018 | 0.0056 | 0.0538 | 0.1785 |
|  | QSeqSim | 0.0401 | 0.0399 | 0.0401 | 0.0464 |
| QRW q8/i2 | Aer statevector | 0.0025 | 0.0146 | 0.0993 | 1.0067 |
|  | QSeqSim | 0.3009 | 0.3042 | 0.3043 | 0.3185 |
| Grover q6/i2 | Aer statevector | 0.0027 | 0.0103 | 0.0547 | 0.6489 |
|  | QSeqSim | 0.7130 | 0.7161 | 0.7204 | 0.7152 |

Aer 0.17.2 warns that shot branching can be unstable on macOS. The checked-in
macOS shot-branching run is therefore a diagnostic only. Native Linux x86_64
is the right platform for a formal shot-branching reproduction.

## Q3 — small/full-output negative control

Q3 uses the same two structured iterations and 1,024 shots but measures the
full register at q4–q12. Aer statevector is fastest at every selected point.

| Family / q12 | Aer statevector | Aer MPS | QSeqSim | QSeqSim outcomes |
| --- | ---: | ---: | ---: | ---: |
| QRW | 0.1833 s | 12.3068 s | 0.5740 s | 4 |
| Grover | 0.4724 s | 9.0386 s | 47.9123 s | 2,048 |

At Grover q12 the absolute worker peaks were 98.9 MiB for statevector,
110.3 MiB for MPS, and 1,947.6 MiB for QSeqSim. Q3 already supplies the needed
output-width sensitivity: changing from full-register output to Q4's one-bit
projection changes branch growth and can reverse which simulator is favorable.
No extra post-hoc sensitivity experiment is required.

## Environment and claim boundary

| Setting | Value |
| --- | --- |
| Host | macOS 26.5.2 arm64; Apple M2, 8 cores; 16 GiB RAM |
| Python / Qiskit / Aer | 3.13.9 / 2.4.2 / 0.17.2 |
| `dd` / NumPy | 0.6.0 with `dd.cudd` / 2.4.2 |
| Simulation | ideal/no-noise |
| Q4-A | two iterations; q0 projection; 1,024 shots; 3 repeats |
| Timed region | `backend.run(...).result()` |
| Q4-A cutoff | 120 seconds per fresh worker |
| Memory | absolute fresh-worker peak RSS |

Absolute ratios are calculated only within this run: same host, case, timed
boundary, and stable completion. Results do not generalize to noise, other Aer
methods, arbitrary circuit families, or wider requested output distributions.

A lightweight manual GitHub-hosted Ubuntu run would improve cross-platform Q2
shot-branching and Q4 anchor reproducibility, but shared-runner variability is
unsuitable for precise timing claims and its absolute times must never be mixed
with Apple M2 ratios. It is a post-0.1 reproducibility item, not a v0.1.0 release
blocker: the macOS Q4-A statevector/MPS comparison is internally same-machine
and does not depend on the separate shot-branching warning.

## Reproduce

From an environment with CUDD-backed `dd.cudd`:

```bash
python -m pip install '.[test,benchmark]'
python benchmarks/ecosystem_benchmark.py \
  --suite all --repeats 3 \
  --shots-grid 1,10,100,1000,10000,100000 \
  --q3-shots 1024 --q3-qubits 4,6,8,10,12 \
  --q3-iterations 2 --correctness-shots 4096 --timeout 120

python benchmarks/ecosystem_large_scale_benchmark.py \
  --repeats 3 --shots 1024 --correctness-shots 4096 --iterations 2 \
  --qrw-widths 12,14,16,18,20,24,32,64,128,256,512,1024 \
  --grover-widths 12,14,16,18,20,24,32,64,128,256 \
  --timeout 120 --capability-timeout 600 --statevector-max-gib 2
```

On Linux the Q2 harness automatically includes Aer shot branching. On macOS it
is disabled unless `--enable-macos-shot-branching` requests a non-formal probe.
A Q4 method stops after its first timeout/error; later widths remain recorded
as `not_run_after_boundary` rather than being mislabeled unsupported.

Machine-readable results are in `benchmarks/results/`: the original result,
the extended macOS Q1–Q3 run, the non-formal macOS shot-branching probe, and the
macOS Q4-A/Q4-B run. No statevectors, CUDD dumps, or large logs are retained.
