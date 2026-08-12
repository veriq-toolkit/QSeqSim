"""Public exceptions raised by QSeqSim."""


class SymbolicEvaluationError(RuntimeError):
    """Raised when symbolic branch/model-count evaluation cannot complete."""


class UnsupportedQiskitFeatureError(ValueError):
    """Raised when the direct frontend encounters unsupported Qiskit semantics."""
