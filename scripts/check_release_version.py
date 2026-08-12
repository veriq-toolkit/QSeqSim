#!/usr/bin/env python3
"""Check that source versions agree and optionally match a final release tag."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_TAG = re.compile(r"v(?P<version>0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")


def _extract(path: Path, pattern: str, label: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find {label} in {path.relative_to(ROOT)}")
    return match.group(1)


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    versions = {
        "pyproject.toml": project["version"],
        "src/qseqsim/__init__.py": _extract(
            ROOT / "src/qseqsim/__init__.py", r'__version__\s*=\s*"([^"]+)"', "__version__"
        ),
        "src/qseqsim/qiskit_backend.py": _extract(
            ROOT / "src/qseqsim/qiskit_backend.py",
            r'backend_version\s*=\s*"([^"]+)"',
            "backend_version",
        ),
        "CITATION.cff": _extract(
            ROOT / "CITATION.cff", r"(?m)^version:\s*([^\s]+)\s*$", "software version"
        ),
    }
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{path}={version}" for path, version in versions.items())
        raise SystemExit(f"Source versions disagree: {details}")

    source_version = next(iter(versions.values()))
    if len(sys.argv) == 1:
        print(f"Source versions agree: {source_version}")
        return
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} [vX.Y.Z]")

    tag = sys.argv[1]
    match = FINAL_TAG.fullmatch(tag)
    if match is None:
        raise SystemExit(f"Release tag must have final-version form vX.Y.Z, got {tag!r}")
    tag_version = tag[1:]
    if source_version != tag_version:
        raise SystemExit(
            f"Release tag/source mismatch: tag={tag_version}, source={source_version}"
        )
    print(f"Release tag and source version agree: {tag}")


if __name__ == "__main__":
    main()
