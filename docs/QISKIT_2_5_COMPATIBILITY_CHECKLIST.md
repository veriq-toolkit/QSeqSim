# Qiskit 2.5 compatibility report

Validated on 2026-08-18 against QSeqSim `main` at
`f8a90eb74038a37fec2caaa8280366595c1ce461`. The published QSeqSim 0.1.0 package
retains its original `qiskit>=2.4,<2.5` metadata. Following successful
validation, the source dependency contract is widened to `qiskit>=2.4,<3`.

## Version selection and installation method

The initial compatibility sweep selected **Qiskit 2.5.1**, then the latest-2.x
lane resolved **Qiskit 2.5.2** during follow-up verification. Both versions were
confirmed through the official [PyPI project](https://pypi.org/project/qiskit/)
and [Qiskit releases](https://github.com/Qiskit/qiskit/releases).

Testing used isolated virtual environments on macOS 26.5.2 arm64. QSeqSim was
installed from the unchanged source checkout as an editable package with
`--no-deps`, after explicitly installing Qiskit and the other dependencies.
This intentionally bypassed dependency resolution of the then-current `<2.5`
upper bound without editing `pyproject.toml` during the validation sweep:

```text
python -m pip install qiskit==2.5.1 ...
python -m pip install --no-deps -e .
```

The canonical CUDD backend was retained in every environment: `dd==0.6.0` with
`dd.cudd` reporting CUDD 3.0.0. On macOS arm64, `dd` was built from the vendored
`third_party/dd-0.6.0.tar.gz` with `DD_FETCH=1`, `DD_CUDD=1`, and
`DD_CUDD_ZDD=1`; the resulting interpreter-specific wheels were used in the
isolated environments.

| Purpose | Python | Qiskit | QSeqSim | `dd` / CUDD | NumPy | OpenQASM 3 | pytest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Latest 2.5, primary | 3.12.3 | 2.5.1 | 0.1.0 | 0.6.0 / 3.0.0 | 2.5.2 | 1.0.1 | 9.1.1 |
| Latest 2.5, second supported Python | 3.13.9 | 2.5.1 | 0.1.0 | 0.6.0 / 3.0.0 | 2.5.2 | 1.0.1 | 9.1.1 |
| Lower-bound regression | 3.12.3 | 2.4.2 | 0.1.0 | 0.6.0 / 3.0.0 | 2.5.2 | 1.0.1 | 9.1.1 |
| Latest-2.x CI rehearsal | 3.13.9 | 2.5.2 | 0.1.0 | 0.6.0 / 3.0.0 | 2.5.2 | 1.0.1 | 9.1.1 |

## Results

- Full pytest, Qiskit 2.5.1 / Python 3.12: **77 passed** in 1.83 seconds.
- Full pytest, Qiskit 2.5.1 / Python 3.13: **77 passed** in 2.30 seconds.
- Full pytest with `-W error`, Qiskit 2.5.1 / Python 3.12:
  **77 passed** in 1.80 seconds.
- Focused Qiskit 2.5.1 smoke selection: **12 passed** in 0.67 seconds.
- Lower-bound full pytest, Qiskit 2.4.2 / Python 3.12: **77 passed** in
  1.90 seconds.
- Latest-2.x full pytest with `-W error`, Qiskit 2.5.2 / Python 3.13:
  **77 passed** in 2.23 seconds.

The focused smoke and full suite together passed all requested high-risk
surfaces:

- `SamplerPub` remains importable from
  `qiskit.primitives.containers.sampler_pub`; `SamplerPub.coerce()` and
  `BindingsArray.bind_all()` work with bare PUBs and parameter sweeps.
- `BaseSamplerV2`, `BasePrimitiveJob`, `SamplerPubResult`, `DataBin`, and
  `BitArray` integration returns the expected Qiskit V2 types and result
  shapes.
- `ForLoopOp` bodies bind the loop parameter with correct scope and unroll to
  the expected operations, including the regression path that failed on older
  Qiskit 2.2/2.3 behavior.
- `QSeqSimBackend` remains a valid `BackendV2`; its `Target`, transpilation,
  Bell counts, deterministic counts, shot memory, and job/result types pass.
- Direct `QuantumCircuit` and `ControlFlowOp` parsing remains independent of
  OpenQASM serialization. Direct and OpenQASM 3 frontends remain semantically
  equivalent for supported ordinary and dynamic circuits.
- Measurement-driven `while`, `if` inside `while`, parameterized PUB sweeps,
  and multi-classical-register field and bit ordering all pass.
- The standalone deterministic `QSeqSimulator` path passes.

## Deprecation and API review

The official [Qiskit 2.5 release notes](https://quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/2.5)
were reviewed for upgrade notes and deprecations. The 2.5 deprecations listed
there concern unrelated circuit commutation-cache and synthesis APIs; none of
the QSeqSim public integration surfaces listed above is deprecated by 2.5.

The full suite also passes with warnings treated as errors. No Qiskit warning or
deprecation warning is emitted by QSeqSim's runtime or tests. The native `dd`
source build emits third-party build-system/compiler warnings, but those are not
Qiskit API warnings and do not occur during the QSeqSim test runs.

## Decision and continuous coverage

The tested evidence supports the maintenance change from `qiskit>=2.4,<2.5` to
`qiskit>=2.4,<3`. The lower bound remains 2.4; this range does **not** claim
support for Qiskit 2.0 through 2.3.

The `<3` upper bound would also admit future Qiskit 2.x minor releases that were
not available for this sweep. Semantic-versioning expectations make that a
reasonable contract, but the 2.5.1 result is not advance evidence for every
future 2.x release. CI therefore covers both boundaries continuously:

- a pinned minimum lane using Qiskit 2.4.2; and
- a latest-2.x lane that explicitly upgrades `qiskit>=2.4,<3`, records the
  resolved version, and runs the suite with warnings treated as errors.

The main test matrix also retains supported-interpreter coverage: Python 3.12
runs against the package dependency specification, the fixed lower-bound lane
also uses Python 3.12, and the latest-2.x lane uses Python 3.13. This keeps the
two supported Python versions visible without taking the Cartesian product of
every Python and Qiskit selection.

The 2.5.1 and 2.5.2 results above are direct compatibility evidence. Future 2.x
releases are admitted by the metadata but are monitored by latest-2.x CI rather
than claimed as pre-validated.

No Qiskit 3.0 build, prerelease, or development version was tested.
