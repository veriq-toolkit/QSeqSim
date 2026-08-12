"""Canonical decision-diagram backend for QSeqSim."""

try:
    from dd import cudd
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "QSeqSim requires the CUDD-backed 'dd.cudd' module. Install a compatible "
        "dd release with CUDD enabled; QSeqSim does not fall back to dd.autoref. "
        "See docs/ENVIRONMENT.md for build instructions."
    ) from exc

__all__ = ["cudd"]
