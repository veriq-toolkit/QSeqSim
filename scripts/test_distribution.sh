#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

cd "${repo_root}"
python -c "import dd.cudd, openqasm3, qiskit"
python -m build --sdist --wheel --outdir "${tmp_dir}/dist"
python -m twine check "${tmp_dir}"/dist/*

# The caller has already built the canonical CUDD backend. Reuse those native
# runtime dependencies while installing only the newly built wheel into a clean
# environment; this prevents pip from replacing CUDD with a pure-Python dd wheel.
python -m venv --system-site-packages "${tmp_dir}/venv"
"${tmp_dir}/venv/bin/python" -m pip install --no-deps "${tmp_dir}"/dist/qseqsim-*.whl
cd "${tmp_dir}"
"${tmp_dir}/venv/bin/python" -c \
  "from qseqsim import QSeqSimulator; import dd.cudd; assert 'src' not in QSeqSimulator.__module__; print(QSeqSimulator)"
