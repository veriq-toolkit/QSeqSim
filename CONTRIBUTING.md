# Contributing

Small, focused issues and pull requests are welcome. Before starting a large
change, open an issue so that its semantics and compatibility scope can be
agreed first.

## Development setup

QSeqSim supports Python 3.12 and 3.13 and requires the CUDD-backed `dd.cudd`
extension. Follow the native or Docker setup in
[the environment guide](docs/ENVIRONMENT.md), then install development tools:

```bash
python -m pip install -e '.[test,build]'
python -m pytest -q
```

Changes should include focused tests and user-facing documentation when they
alter public behavior. Keep the direct Qiskit frontend independent of OpenQASM
serialization, preserve explicit failures for unsupported semantics, and do
not weaken the binary64 probability contract documented in
`docs/NUMERICAL_CONTRACT.md` without a separately reviewed API decision.

By participating, you agree to follow [the Code of Conduct](CODE_OF_CONDUCT.md).
