"""Stable public API for the QSeqSim library."""

from ._backend import cudd as _cudd
from .exceptions import SymbolicEvaluationError
from .parser import CQC, DQC, SQC, GateOp, QiskitParser
from .simulator import BDDSimulator

__version__ = "0.1.0.dev0"


class QSeqSimulator(BDDSimulator):
    """Public simulator name backed by the existing symbolic kernel.

    The constructor intentionally retains ``BDDSimulator`` semantics in CP2:
    callers pass the blocks produced by :class:`QiskitParser`. A future direct
    ``QuantumCircuit`` frontend is outside this compatibility wrapper's scope.
    """


__all__ = [
    "BDDSimulator",
    "CQC",
    "DQC",
    "GateOp",
    "QSeqSimulator",
    "QiskitParser",
    "SQC",
    "SymbolicEvaluationError",
    "__version__",
]
