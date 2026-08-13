# Changelog

All notable user-facing changes will be recorded here. The project follows
semantic versioning after its first public release.

## [0.1.0] - 2026-08-13

- Installable `qseqsim` package for Python 3.12 and 3.13.
- Direct `QuantumCircuit` frontend for supported gates, measurements,
  conditions, `if_test`, `while_loop`, and finite `for_loop` operations.
- Native `QSeqSimulator` symbolic state/path API.
- Qiskit `BackendV2` integration with synchronous jobs, counts, and memory.
- Native SamplerV2 integration with PUB binding and per-register `BitArray`
  results.
- Shared complete symbolic branch-distribution execution and seeded shot
  sampling.
- Explicit binary64 public probability contract with regression-tested
  underflow boundary.
- Reproducible FM artifact and ecosystem-oriented Qiskit Aer benchmark.

## 0.1.0.dev1 - 2026-08-13

- Repair the published-installation contract after the first TestPyPI staging:
  document the verified CUDD-backed `dd` paths for Linux x86_64 and macOS
  arm64, and make repository links in the package description absolute.
- Update public project URLs to the current `veriq-toolkit/QSeqSim` owner.

[0.1.0]: https://github.com/veriq-toolkit/QSeqSim/releases/tag/v0.1.0
