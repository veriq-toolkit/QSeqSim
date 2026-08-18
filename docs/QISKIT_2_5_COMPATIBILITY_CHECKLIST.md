# Qiskit 2.5 compatibility follow-up

This is an internal checklist for a future compatibility change. It does not
authorize a dependency edit, version change, release, or publication. The
current package contract remains `qiskit>=2.4,<2.5` at version 0.1.0.

## Compatibility sweep

- [ ] Select the latest available Qiskit 2.5.x patch and record the exact
  Qiskit, Python, `dd`, and platform versions used.
- [ ] Build isolated Python 3.12 and 3.13 environments with a working
  `dd.cudd`, then install QSeqSim without editing `pyproject.toml`.
- [ ] Run the full test suite, including the direct `QuantumCircuit` frontend,
  supported dynamic control flow, BackendV2 jobs/results, and SamplerV2 PUBs.
- [ ] Run the numerical-contract and correctness-audit regression tests.
- [ ] Run the small ecosystem benchmark correctness checks against the pinned
  Aer comparison environment; do not reinterpret performance results from a
  different dependency set.
- [ ] Review Qiskit 2.5 deprecations and API changes affecting `Target`,
  `BackendV2`, `JobV1`, `Result`, `BaseSamplerV2`, `SamplerPub`, `DataBin`, and
  `BitArray`.
- [ ] Record any failures, warnings, unsupported paths, or platform-specific
  installation issues before proposing a metadata change.

## Decision gate

Only if the compatibility sweep passes:

- [ ] Prepare a separate pull request proposing `qiskit>=2.4,<3`.
- [ ] Add Qiskit 2.5.x to the supported CI matrix and update compatibility
  documentation and the changelog.
- [ ] Re-run release gates before separately deciding whether a patch release
  is warranted.

If any compatibility check fails, keep the existing `<2.5` upper bound and
open focused follow-up work for the failing surface instead.
