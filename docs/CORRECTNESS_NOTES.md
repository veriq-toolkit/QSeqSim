# Correctness and soundness notes

This document records durable semantic invariants, tested failure behavior,
and numerical boundaries for the current QSeqSim implementation. The immutable
FM artifact baseline remains recorded in [BASELINE.md](../BASELINE.md).

## CUDD ownership and exact model counting

QSeqSim imports only `dd.cudd`; it has no `dd.autoref` runtime fallback. Each
`BDDCombSim` owns one manager. `BDDSeqSim` owns separate input, stored, and
combined managers and transfers functions between managers explicitly during
sequential composition. CUDD functions never cross manager boundaries without
`BDD.copy(function, other_manager)`.

Dynamic variable reordering is enabled by default. Exact model counting
temporarily disables reordering during graph traversal and restores the prior
configuration afterward. The counter traverses `succ`, function levels, and
complemented edges to produce Python integers, including skipped levels and
terminal nodes. It does not use `BDD.count`, whose binary64 return value cannot
represent all large integer counts exactly.

Regression tests cover manager transfers, repeated top-level runs, complemented
edges, skipped variables, explicit variable reordering, and counts beyond the
binary64 exact-integer range.

## Execution-state isolation

Each call to `BDDSimulator.run()` creates a fresh kernel and defensively copies
preset measurement lists. Reusing a simulator therefore cannot reuse a
collapsed state or consume caller-owned preset data from an earlier run.

Measurement probability traversal that exceeds Python's recursion limit raises
the public `SymbolicEvaluationError`, with the original `RecursionError` as its
cause. QSeqSim never substitutes a uniform distribution for an incomplete
symbolic calculation. A failed run does not fabricate a classical result, and
the next run starts from a fresh kernel.

## Numerical boundary

The probability path is:

1. `_symbolic_inner_product()` accumulates model counts as Python integers.
2. `BDDCombSim.get_prob()` combines terms using a Decimal context with 150
   digits of precision.
3. The public `get_prob()` return value is converted to binary64 `float`.
4. Sampling normalization, `global_probability`, sequential probability lists,
   and lowering result traces use binary64 values.

Consequently, model counting is exact but the public probability interface is
not arbitrary precision. The exact Decimal value `2**-1074` converts to the
smallest positive binary64 subnormal, while `2**-1075` rounds to zero. Repeated
binary64 factors of `0.5` have the same underflow boundary. Decimal precision
can also become insufficient for much larger cancellation problems.

Changing this boundary would affect sampling, normalization, result types,
sequential traces, and artifact formatting. The current contract is therefore
documented and regression-tested rather than partially changed. See
[NUMERICAL_CONTRACT.md](NUMERICAL_CONTRACT.md) for the public-facing contract.

## Control-flow boundaries

Two execution paths have different supported shapes:

- The general `BDDSimulator` path supports tested conditional branches nested
  inside measurement-driven `while` loops and stops after 1000 loop bodies with
  an exception.
- Specialized `BDDSeqSim` lowering rejects nested control flow and arbitrary
  mid-body measurements. A measurement that updates a loop condition must meet
  the documented trailing-measurement shape.

These rejections are preferable to partial or unsound execution. The direct
Qiskit frontend does not remove kernel or specialized-lowering restrictions;
unsupported shapes raise explicit errors.

## Regression scope

The correctness suite covers:

1. ordinary Clifford+T circuits against Qiskit `Statevector`;
2. preset mid-circuit measurement against dense branch states and probabilities;
3. repeatability and caller-owned preset isolation;
4. measurement-driven loops over multiple iterations;
5. supported conditional branches nested inside loops;
6. nested parsing, execution, and classical-store behavior;
7. state retention across sequential manager copies;
8. amplitudes and probabilities across variable reordering;
9. exact model counting above the binary64 exact-integer limit; and
10. explicit failure behavior for unsupported operations and symbolic resource
    failures.

The supported dependency range and concrete compatibility results are recorded
in [QISKIT_COMPATIBILITY.md](QISKIT_COMPATIBILITY.md).
