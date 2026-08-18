# Qiskit compatibility

QSeqSim supports Qiskit `>=2.4,<3`. The lower bound is Qiskit 2.4; Qiskit
2.0–2.3 and Qiskit 3 are not included in the supported range.

## Validated environments

The Qiskit 2.5 compatibility study was performed on 2026-08-18 against source
commit `f8a90eb74038a37fec2caaa8280366595c1ce461`. The initial study selected
Qiskit 2.5.1, and the latest-2.x CI rehearsal resolved Qiskit 2.5.2. Every
environment retained `dd==0.6.0`, `dd.cudd`, and CUDD 3.0.0.

| Purpose | Python | Qiskit | NumPy | OpenQASM 3 | pytest |
| --- | --- | --- | --- | --- | --- |
| Current 2.5, primary | 3.12.3 | 2.5.1 | 2.5.2 | 1.0.1 | 9.1.1 |
| Current 2.5, second Python | 3.13.9 | 2.5.1 | 2.5.2 | 1.0.1 | 9.1.1 |
| Lower-bound regression | 3.12.3 | 2.4.2 | 2.5.2 | 1.0.1 | 9.1.1 |
| Latest-2.x rehearsal | 3.13.9 | 2.5.2 | 2.5.2 | 1.0.1 | 9.1.1 |

Testing used isolated environments on macOS arm64. The CUDD-enabled `dd`
package was built from the vendored `third_party/dd-0.6.0.tar.gz` with
`DD_FETCH=1`, `DD_CUDD=1`, and `DD_CUDD_ZDD=1`.

## Results

- Qiskit 2.5.1 / Python 3.12: 77 tests passed.
- Qiskit 2.5.1 / Python 3.13: 77 tests passed.
- Qiskit 2.5.1 / Python 3.12 with warnings treated as errors: 77 tests passed.
- Qiskit 2.4.2 / Python 3.12: 77 tests passed.
- Qiskit 2.5.2 / Python 3.13 with warnings treated as errors: 77 tests passed.
- `pip check` passed in every environment.

The tests cover the direct `QuantumCircuit` frontend, OpenQASM 3 compatibility,
supported dynamic control flow, BackendV2 transpilation/jobs/results,
SamplerV2 PUB coercion and parameter binding, multi-register result ordering,
and the standalone symbolic simulator.

The Qiskit 2.5 release notes were reviewed for changes affecting `Target`,
`BackendV2`, `JobV1`, `Result`, `BaseSamplerV2`, `SamplerPub`, `DataBin`, and
`BitArray`. The suite emits no Qiskit deprecation warning with warnings treated
as errors.

## Continuous compatibility coverage

CI uses three focused lanes instead of a full Python-by-Qiskit product:

- Python 3.12 resolves the declared `qiskit>=2.4,<3` package range;
- Python 3.12 pins Qiskit 2.4.2 as the supported lower bound; and
- Python 3.13 upgrades eagerly within `qiskit>=2.4,<3`, records the resolved
  Qiskit/CUDD versions, runs `pip check`, and treats warnings as errors.

The 2.5.1 and 2.5.2 results are direct compatibility evidence. Future Qiskit
2.x releases are admitted by metadata and checked continuously; they are not
claimed as pre-validated. No Qiskit 3 build, prerelease, or development version
was tested.
