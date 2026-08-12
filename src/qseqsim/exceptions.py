"""Public exceptions raised by QSeqSim."""


class SymbolicEvaluationError(RuntimeError):
    """Raised when the symbolic kernel cannot complete an exact evaluation."""


class UnsupportedQiskitFeatureError(ValueError):
    """Raised when the direct frontend encounters unsupported Qiskit semantics."""
