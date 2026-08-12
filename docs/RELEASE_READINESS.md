# v0.1.0 release-readiness decisions

This record was prepared on **2026-08-12**. It is a staging document, not a
claim that a release, tag, or upload exists.

## Distribution and display names

Direct queries to the canonical PyPI JSON endpoints returned HTTP 404 for both
`qseqsim` and `veriq-qseqsim` on 2026-08-12. No project page existed under
either normalized name at query time. A 404 is evidence of no published PyPI
project, not a reservation guarantee; availability must be checked again
immediately before first upload.

The recommended distribution name and Python import remain `qseqsim`.
Ecosystem display-name candidates are `QSeqSim` and `Veri-Q QSeqSim`. The
choice does not change the Python namespace. No team website or logo is assumed
by the release metadata; repository URLs remain the only project URLs until a
maintainer supplies and verifies another destination.

## Version strategy

CP6 keeps source metadata at `0.1.0.dev0`. This accurately states that no
release candidate or final artifact has been published. After remote backup and
staging approval, one small release commit should change every version source
to `0.1.0`, update the changelog date, build and inspect artifacts, and only
then create the matching annotated `v0.1.0` tag. There is no `0.1.0` or
`0.1.0rc1` tag in CP6.

## Dependency contract

- Python: `>=3.12,<3.14`; CI covers 3.12 and 3.13.
- Qiskit: `>=2.2,<2.5`; Qiskit 2.4.x is the release-gate target.
- `dd`: `>=0.6,<0.7`, with `dd.cudd` required at import time.
- OpenQASM 3: `>=1.0,<1.1`, used as a secondary compatibility frontend.

The ranges are deliberately not expanded beyond tested compatibility during a
release gate.

## Pre-release actions requiring explicit authorization

1. Push the CP6 commits to a remote backup branch.
2. Configure protected GitHub environments and pending PyPI/TestPyPI Trusted
   Publishers for the in-repository workflow.
3. Recheck PyPI name availability.
4. Make the final version/changelog commit and matching tag.
5. Upload to TestPyPI or PyPI and submit Qiskit Ecosystem metadata.

None of these actions is performed by CP6.
