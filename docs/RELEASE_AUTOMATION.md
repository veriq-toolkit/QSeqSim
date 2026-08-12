# Release automation and Trusted Publishing

The in-repository `.github/workflows/release.yml` workflow publishes only from
a non-draft, non-prerelease GitHub release. Before its publish job can start it:

1. accepts only an exact `vX.Y.Z` tag;
2. requires the tag version to match `pyproject.toml`, `qseqsim.__version__`,
   and the BackendV2 version;
3. installs the required CUDD backend and runs the complete test suite;
4. builds both sdist and wheel and runs `twine check`;
5. installs and smokes the newly built wheel; and
6. uploads the distributions as a GitHub artifact for inspection.

The publish job uses `pypa/gh-action-pypi-publish@release/v1`, job-scoped
`id-token: write`, and the `pypi` GitHub environment. No long-lived PyPI token
is referenced. The environment should be protected with required manual
approval, and the repository/workflow/environment tuple must be registered as
a pending Trusted Publisher on PyPI before the first release.

`.github/workflows/testpypi.yml` is a separate, manual, explicitly confirmed
staging path using the protected `testpypi` environment and its own pending
Trusted Publisher registration. It repeats the test/build/check gate and does
not use a reusable workflow as the OIDC publisher identity.

CP6 only commits these definitions. It does not invoke either workflow,
configure an external environment, create a release, or upload an artifact.
