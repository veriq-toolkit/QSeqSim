"""Canonical decision-diagram backend for QSeqSim."""

try:
    from dd import cudd
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        "QSeqSim requires the CUDD-backed 'dd.cudd' module. Install a compatible "
        "dd release with CUDD enabled; QSeqSim does not fall back to dd.autoref. "
        "See https://github.com/veriq-toolkit/QSeqSim#installation for "
        "platform-specific build instructions."
    ) from exc

__all__ = ["cudd"]
