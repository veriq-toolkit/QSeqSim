# CP1 Correctness Audit

This audit applies to the `qiskit-ecosystem` branch after the immutable FM
artifact baseline recorded in `BASELINE.md`. It deliberately does not include
package-layout, public-API, `BackendV2`, or `SamplerV2` work.

## CUDD API and lifecycle inventory

QSeqSim imports only `dd.cudd`; there is no `autoref` runtime fallback.

- `BDD()`: one manager per `BDDCombSim`. `BDDSeqSim` owns input, stored, and
  combined managers and recreates the combined/stored manager while composing
  iterations.
- `configure(reordering=True)`: dynamic reordering is enabled when each manager
  is created. Exact model counting temporarily disables it during traversal and
  restores the previous setting.
- `add_var`, `var`, `cube`, `add_expr`: declare variables and build Boolean
  functions.
- `let`: Boolean restriction and variable renaming. It is used in gate
  transforms, measurement collapse, reset, and sequential state transfer.
- Boolean function operators (`&`, `|`, `~`) and equality with manager
  constants: construct and inspect `dd.cudd.Function` values. The functions are
  manager-owned; they must not cross managers directly.
- `Function.copy()`: list-level Python copies in gate transformations copy
  references, not functions or managers. This is safe because functions are
  immutable handles owned by the same manager.
- `BDD.copy(function, other_manager)`: transfers input/stored functions into a
  combined manager and transfers the retained result back to a new stored
  manager.
- `support`: determines how many logical free variables a term uses.
- `succ`, `Function.level`, and `Function.negated`: traverse the CUDD graph for
  exact integer model counting, including skipped levels and complemented
  edges.
- `count`: no longer used by the probability kernel. It returns binary64 and is
  retained only in a regression test that demonstrates the former precision
  failure.

Python references keep functions and managers alive; there is no explicit
manager close call in this API. Sequential manager transfers and repeated
top-level runs have regression coverage.

## Differential and regression scope

`test/test_correctness_audit.py` covers:

1. an ordinary Clifford+T circuit against Qiskit `Statevector`;
2. preset mid-circuit measurement against a dense branch state and probability;
3. repeatability of `BDDSimulator.run`, including caller-owned preset data;
4. measurement-driven `while` execution over multiple iterations;
5. `if` nested inside `while`, including classical branch selection;
6. nested control-flow parsing/execution and classical-store results;
7. state retention/composition across `BDDSeqSim` manager copies;
8. amplitudes and probabilities before and after an explicit reverse variable
   ordering, with automatic reordering still enabled;
9. exact model counting above the binary64 exact-integer limit.

The repository test suite passes with CUDD-backed `dd==0.6.0`, Qiskit 2.4.1,
NumPy 2.4.2, and Python 3.13.9. The pinned baseline Qiskit version is 2.2.3;
the newer local version was used as an additional compatibility check.

## Findings and release disposition

### CP1-01: binary64 model-count rounding

- Severity: critical.
- Reproduction: for 60 supported variables, count the complement of one cube.
  The exact result is `2**60 - 1`; `int(BDD.count(node))` returns `2**60`.
- Impact: `_symbolic_inner_product` could silently perturb WMC terms and final
  probabilities in large-support models.
- Resolution: fixed with iterative integer model counting over the CUDD graph.
  Complemented edges, skipped levels, terminal nodes, and reordering stability
  are tested.
- PyPI v0.1.0: must be fixed; resolved in CP1.

### CP1-02: repeated runs reused collapsed quantum state

- Severity: high for a reusable library API; low for one-shot artifact scripts.
- Reproduction: construct one `BDDSimulator`, run the same preset mid-measure
  circuit twice, and compare state/probability. The former implementation reset
  bookkeeping but not its BDD kernel and also consumed the caller's preset list.
- Resolution: each `run` creates a fresh kernel and makes defensive copies of
  preset lists.
- PyPI v0.1.0: must be fixed; resolved in CP1.

### CP1-03: `RecursionError` becomes an assumed uniform distribution

- Severity: high.
- Reproduction: make `kernel.get_prob` raise `RecursionError` during a mid or
  final measurement; `BDDSimulator` substitutes `0.5` probabilities.
- Impact: an implementation/resource failure can silently produce a plausible
  but incorrect result.
- Resolution: fixed in CP2.5. Both mid-circuit and final-readout probability
  paths now raise the public `SymbolicEvaluationError` (a `RuntimeError`
  subclass), with the original `RecursionError` retained as its cause. No
  heuristic fallback is provided. A failed run does not collapse state or
  write a classical result, and the next `run()` starts with a fresh kernel.
- PyPI v0.1.0: must be fixed; resolved in CP2.5.

### CP1-04: probability API returns binary64 after Decimal evaluation

- Severity: medium.
- Reproduction: `get_prob` computes with global `Decimal` precision 150 and then
  returns `float`; `global_probability` also accumulates in binary64.
- Impact: exact integer WMC is now preserved, but the public result and long path
  products are approximate and can eventually underflow. Precision 150 also
  becomes insufficient for substantially larger cancellation problems.
- Resolution: documented, not changed to avoid widening the API/kernel change
  in CP1. A future API should expose an exact algebraic or high-precision result
  and define precision from circuit scale.
- PyPI v0.1.0: must be documented; a precise result type is recommended but is
  not required for the already advertised roughly 256-qubit scale.

CP2.5 quantified this boundary. `get_prob()` returns the smallest positive
binary64 value for the exactly representable Decimal result `2**-1074`
(approximately `4.9406564584124654e-324`) and returns zero for `2**-1075` due
to round-to-nearest-even. Likewise, multiplying binary64 branch probabilities
of `0.5` underflows after 1075 factors. The exact-zero test still distinguishes
an algebraic zero before conversion, but the public float result cannot convey
that distinction after underflow. This does not block CP3, which does not need
to change the numeric core, but it remains a documentation/API decision for the
v0.1.0 release gate. See `docs/CP2_5_CORRECTNESS_GATE.md`.

### CP1-05: unsupported control-flow shapes

- Severity: medium (capability boundary, not a demonstrated kernel error).
- Reproduction: `BDDSeqSim` lowering rejects nested control flow and mid-body
  measurements, while the general `BDDSimulator` path supports the tested
  `if`-inside-`while` case but has a hard 1000-iteration cap.
- Resolution: current rejection is preferable to unsound execution. Supported
  shapes and the iteration limit must be explicit in release documentation.
- PyPI v0.1.0: document before release; expansion is not required for v0.1.0.

### CP1-06: CUDD dependency is not pinned in `requirements.txt`

- Severity: medium release/reproducibility risk.
- Reproduction: baseline requirements omit `dd`; the Dockerfile builds the
  vendored 0.6.0 source while the native helper downloads the current release.
- Resolution: deferred to CP2 packaging metadata. No `autoref` fallback should
  be introduced.
- PyPI v0.1.0: must be fixed in dependency metadata and installation checks.

## CP1 gate

The tested correctness scope is green, and the two demonstrated semantic bugs
are fixed. CP2 may start after accepting the three v0.1.0 obligations above:
fail loudly instead of silently assuming uniform probabilities, declare and
verify the CUDD dependency, and document numeric precision/control-flow limits.
