# v0.1.0 release-readiness decisions

This record was prepared on **2026-08-12**. It is a staging document, not a
claim that a release, tag, or upload exists.

> **Historical note:** v0.1.0 has since been published and Veri-Q QSeqSim has
> been accepted into the Qiskit Ecosystem. The staging decisions below are kept
> as a release record rather than as current outstanding work.

## Distribution and display names

Direct queries to the canonical PyPI JSON endpoints returned HTTP 404 for both
`qseqsim` and `veriq-qseqsim` on 2026-08-12. No project page existed under
either normalized name at query time. A 404 is evidence of no published PyPI
project, not a reservation guarantee; availability must be checked again
immediately before first upload.

The distribution name and Python import remain `qseqsim`; the project display
name is `Veri-Q QSeqSim`. The display name does not change the Python namespace.
The project homepage is `https://www.veri-q.com/`, while source, issue,
documentation, and changelog URLs remain under `veriq-toolkit/QSeqSim`.

## Version strategy

The first TestPyPI staging consumed `0.1.0.dev0` and exposed a published-install
documentation blocker: macOS arm64 can otherwise receive the pure-Python `dd`
wheel, which has no `dd.cudd`, and the package description relied on repository-
relative links and a checkout-only helper. CP7-C.1 therefore advances every
version source to `0.1.0.dev1` while leaving the planned final release at
`0.1.0`. The dev1 staging fix documents independently usable install commands;
it does not create a tag or final release.

## Dependency contract

- Python: `>=3.12,<3.14`; CI covers 3.12 and 3.13.
- Qiskit: `>=2.4,<2.5`; Qiskit 2.4.x is the release-gate target. Qiskit
  2.2.3 and 2.3.1 were tested and excluded because their public circuit
  parameter model exposes a `for_loop` index as a PUB parameter, causing
  `SamplerPub.coerce()` to reject a supported parameter-free loop.
- `dd`: `>=0.6,<0.7`, with `dd.cudd` required at import time.
- OpenQASM 3: `>=1.0,<1.1`, used as a secondary compatibility frontend.

The ranges are deliberately not expanded beyond tested compatibility during a
release gate.

## Historical pre-release actions requiring explicit authorization

1. Push the CP6 commits to a remote backup branch.
2. Configure protected GitHub environments and pending PyPI/TestPyPI Trusted
   Publishers for the in-repository workflow.
3. Recheck PyPI name availability.
4. Make the final version/changelog commit and matching tag.
5. Upload to TestPyPI or PyPI and submit Qiskit Ecosystem metadata.

None of these actions is performed by CP6.
