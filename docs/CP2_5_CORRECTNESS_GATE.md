# CP2.5 Correctness and Debt Gate

This gate applies to the `qiskit-ecosystem` branch after CP2. It does not alter
the immutable FM baseline and does not include the direct `QuantumCircuit`
frontend, `BackendV2`, or `SamplerV2`.

## Recursion failure semantics

The simulator had two catches for `RecursionError`: mid-circuit measurement and
final readout. Both surrounded calls to `BDDCombSim.get_prob()`. When symbolic
probability traversal exceeded Python's recursion limit, each catch silently
substituted a uniform distribution (`p(0) = p(1) = 0.5`). This turned a resource
or implementation failure into a plausible but potentially false result.

Both paths now raise `qseqsim.SymbolicEvaluationError`, a public
`RuntimeError` subclass. The message identifies exact symbolic evaluation and
the recursion-limit failure, and exception chaining preserves the original
`RecursionError`. There is no approximation mode or heuristic fallback. The
same audit also removed the final-readout path's uniform fallback for a kernel
without `get_prob`; that invalid kernel contract now raises `AttributeError`.

Regression tests force each catch path without depending on a fragile
platform-specific recursion depth. They verify the public exception and cause,
the absence of a fabricated classical result, and a successful clean rerun
after a failed mid-measurement evaluation.

## Decimal-to-float boundary

The exactness boundary inventory is:

1. `_symbolic_inner_product()` accumulates model counts as Python integers.
2. `BDDCombSim.get_prob()` combines the integer terms using the process Decimal
   context at 150 digits.
3. The final `Decimal` probability is converted to `float` at the public
   `get_prob()` return boundary.
4. `BDDSimulator` normalizes those float results for sampling and accumulates
   the selected branch probabilities in float `global_probability`.
5. `BDDSeqSim.prob_list` and the lowering result's `probability` and
   `probability_trace` are consequently also floats.

The only other production `float()` conversion is OpenQASM integer-literal
conversion for gate parameters in the compatibility parser; it is not a
probability or model-count path.

A deterministic regression injects the exact algebraic numerator 1 and varies
the denominator exponent. The observed boundary is:

| Exact Decimal value | binary64 result | Effect |
| --- | --- | --- |
| `2**-1074` | `4.9406564584124654e-324` | Smallest positive subnormal |
| `2**-1075` | `0.0` | Underflows by round-to-nearest-even |

The same threshold applies to repeated path factors: `0.5**1074` is the
smallest positive binary64 value and `0.5**1075` is zero. Values well above the
underflow boundary, including the documented scale around `1e-78`, remain
representable, but only with binary64 output precision (roughly 16 significant
decimal digits). Decimal precision 150 can also become insufficient for much
larger cancellation problems; that limit depends on circuit-generated integer
terms rather than only the final exponent.

Changing `get_prob()` to return `Decimal` would propagate through random
sampling, normalization, `global_probability`, sequential traces, public result
types, and artifact output formatting. There is no isolated internal float
conversion that can be delayed without changing those contracts. CP2.5
therefore records and tests the boundary instead of performing a broad numeric
rewrite. This is not a CP3 blocker. Before the v0.1.0 release gate, the project
must choose and document whether binary64 remains the public result contract or
whether to add a separate high-precision result API.

## Capability boundaries

The boundaries were checked against code and regression tests:

| Boundary | Enforced by | Current behavior | CP3 effect |
| --- | --- | --- | --- |
| Nested control flow in specialized lowering | `seqsim_lowering._flatten_cqc_ops` | Explicit `LoweringError` | Direct frontend does not remove it |
| Mid-body measurement in specialized lowering | `lower_to_bddseqsim` | Explicit `LoweringError` | Direct frontend does not remove it |
| Loop-guard measurement ordering | `SQC._validate_and_extract` | Guard-updating measurement must be last on that qubit | Must be preserved or deliberately redesigned |
| General executor loop count | `BDDSimulator._run_sqc` | Executes at most 1000 bodies, then raises | Direct frontend does not remove it |
| Nested `if` inside `while` in general executor | parser IR plus `BDDSimulator` | Supported by CP1 differential regression | CP3 should preserve it |

CP3 can bypass behavior specific to conversion through OpenQASM 3, but it must
not infer expanded kernel/lowering capability from that frontend change.
