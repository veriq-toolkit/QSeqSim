"""Shared direct-circuit distribution and shot-sampling helpers."""

from __future__ import annotations

import random
from collections.abc import Mapping

from qiskit import QuantumCircuit

from .simulator import BDDSimulator


def run_symbolic_distribution(circuit: QuantumCircuit, *, precision: int) -> dict[int, float]:
    """Execute one complete symbolic distribution for ``circuit``."""
    # Local import avoids an import cycle through qseqsim.__init__ and makes the
    # direct (non-QASM) frontend choice explicit for both Qiskit adapters.
    from .qiskit_frontend import QuantumCircuitParser

    simulator = BDDSimulator(QuantumCircuitParser(circuit).parse(), precision=precision)
    return simulator.run_distribution(num_clbits=circuit.num_clbits)


def sample_distribution(
    distribution: Mapping[int, float], *, shots: int, rng: random.Random
) -> list[int]:
    """Draw ordered integer outcomes from a complete symbolic distribution."""
    outcomes = list(distribution)
    return rng.choices(
        outcomes,
        weights=[distribution[outcome] for outcome in outcomes],
        k=shots,
    )


__all__ = ["run_symbolic_distribution", "sample_distribution"]
