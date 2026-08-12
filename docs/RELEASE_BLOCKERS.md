# v0.1.0 release-blocker triage

This triage records the release sweep completed on **2026-08-13**. A blocker
is limited to a defect that can produce an incorrect result, hide a failed
execution, break installation, overstate declared compatibility, or violate a
public API contract.

## Blockers

No open technical blocker remains.

The sweep found one declared-compatibility blocker. Qiskit 2.2.3 and 2.3.1 do
not re-export `SamplerPub` from the same public container namespace as 2.4,
and, more importantly, expose a `for_loop` index through
`QuantumCircuit.parameters`. Their `SamplerPub.coerce()` therefore rejects a
supported loop with no user PUB parameters. The stable import path is now used
and the dependency range is narrowed to `qiskit>=2.4,<2.5`; Qiskit 2.4.2
passes the complete suite and installed-package smoke tests.

The sweep also confirmed that unsupported Qiskit operations, unsupported
parameter angles, recursion failures, and the sequential-loop iteration guard
raise exceptions through the direct frontend, BackendV2, and SamplerV2 paths.
They do not return successful jobs or normalized placeholder distributions.

## Documented limitations

- `SwitchCaseOp`, `BreakLoopOp`, `ContinueLoopOp`, classical expression
  conditions, dynamic variables, and `Store` are rejected explicitly.
- Gate parameters are limited to the documented discrete Clifford+T-compatible
  angles after binding.
- Specialized sequential lowering requires its documented trailing
  measurement shape and does not support arbitrary nested or mid-body
  measurements.
- Sequential loops stop with an exception at the 1000-iteration safety guard.
- Public probabilities are IEEE 754 binary64 values. Integer model counts and
  branch algebra are exact before the documented Decimal-to-float boundary;
  no arbitrary-precision public probability API is provided.
- CUDD-backed `dd.cudd` is mandatory. QSeqSim does not fall back to
  `dd.autoref`.

These limits are part of the v0.1.0 scope and are not release blockers because
they fail explicitly and are described in the user documentation.

## Post-0.1 candidates

- Additional control-flow operations and classical-expression support.
- Broader parameterized-gate domains.
- An optional high-precision public probability interface with one consistent
  result model.
- More general specialized sequential lowering.
- A configurable or semantically stronger long-loop resource policy.
- Compatibility work for later Qiskit and Python release lines after their
  public APIs and native dependencies are tested.

## Verified compatibility scope

- Python 3.12 and 3.13; neither 3.11 nor 3.14 is declared.
- Qiskit 2.4.x, tested with 2.4.2; the final requirement is
  `qiskit>=2.4,<2.5`.
- `dd>=0.6,<0.7` with a working native `dd.cudd` import.
- `openqasm3[parser]>=1.0,<1.1`, tested through the compatibility frontend.
- Native validation was performed on macOS arm64. Linux remains the CI and
  Docker target. Windows is not advertised as natively supported; the
  environment guide recommends WSL2.
