# Releasing QSeqSim

QSeqSim publishes distributions through GitHub Actions and PyPI Trusted
Publishing. Maintainers should prepare a version update on `main`, verify the
source and built distributions locally, and create a GitHub release only after
the corresponding commit has passed CI.

## Version sources

The release version must match in:

- `pyproject.toml`;
- `qseqsim.__version__`;
- `QSeqSimBackend.backend_version`;
- `CITATION.cff`; and
- the exact `vX.Y.Z` Git tag.

The changelog entry and `CITATION.cff` release date must describe the same
release. Paper metadata in `CITATION.cff` is independent of the software
version and should not be rewritten during routine package releases.

## Local verification

Before tagging, maintainers should run the complete tests across the supported
Qiskit boundary, build both wheel and sdist, run `twine check --strict`, install
the wheel into a fresh supported Python environment, and run `pip check` plus
the BackendV2, SamplerV2, dynamic-loop, and OpenQASM smoke tests.

## GitHub workflows

`.github/workflows/release.yml` runs only for a non-draft, non-prerelease
GitHub release. Before publication it validates the tag/version relationship,
installs CUDD, runs the complete tests, builds wheel and sdist, checks both
distributions, installs and tests the wheel, and uploads the distributions as a
GitHub Actions artifact.

The publish job uses `pypa/gh-action-pypi-publish@release/v1`, job-scoped
`id-token: write`, and the protected `pypi` environment. No long-lived PyPI
token is stored in the repository. The repository, workflow, and environment
must match the PyPI Trusted Publisher registration.

`.github/workflows/testpypi.yml` is a separate manually confirmed staging path
using the protected `testpypi` environment and its own Trusted Publisher
registration. It repeats tests, builds, and distribution checks before upload.

## Publication sequence

1. Fast-forward `main` with the reviewed commits and wait for CI.
2. Create the matching annotated tag from the release commit and push the tag.
3. Create a non-draft, non-prerelease GitHub release for that tag.
4. Review the workflow artifact and approve the protected PyPI environment.
5. Confirm the published PyPI metadata and install the release in a fresh
   environment.
