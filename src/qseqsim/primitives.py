"""Native Qiskit Primitive V2 integration for QSeqSim."""

from __future__ import annotations

import random
import uuid
import warnings
from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from numbers import Integral
from typing import Callable

import numpy as np
from qiskit.primitives import BasePrimitiveJob, BaseSamplerV2
from qiskit.primitives.containers import (
    BitArray,
    DataBin,
    PrimitiveResult,
    SamplerPub,
    SamplerPubLike,
    SamplerPubResult,
)
from qiskit.providers import JobStatus

from ._sampling import run_symbolic_distribution, sample_distribution


@dataclass(frozen=True)
class _RegisterLayout:
    name: str
    size: int
    global_indices: tuple[int, ...]


class QSeqPrimitiveJob(BasePrimitiveJob[PrimitiveResult[SamplerPubResult], JobStatus]):
    """A lightweight local primitive job backed by one worker future."""

    def __init__(self, function: Callable[[], PrimitiveResult[SamplerPubResult]]):
        super().__init__(str(uuid.uuid4()))
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qseqsim-primitive")
        self._future: Future[PrimitiveResult[SamplerPubResult]] = executor.submit(function)
        executor.shutdown(wait=False)

    def result(self) -> PrimitiveResult[SamplerPubResult]:
        return self._future.result()

    def status(self) -> JobStatus:
        if self._future.cancelled():
            return JobStatus.CANCELLED
        if self._future.running():
            return JobStatus.RUNNING
        if not self._future.done():
            return JobStatus.INITIALIZING
        return JobStatus.ERROR if self._future.exception() is not None else JobStatus.DONE

    def done(self) -> bool:
        return self._future.done() and self._future.exception() is None

    def running(self) -> bool:
        return self._future.running()

    def cancelled(self) -> bool:
        return self._future.cancelled()

    def in_final_state(self) -> bool:
        return self._future.done()

    def cancel(self) -> bool:
        return self._future.cancel()


class QSeqSamplerV2(BaseSamplerV2):
    """Qiskit SamplerV2 adapter over QSeqSim's symbolic distribution executor.

    Every bound circuit is symbolically executed once. Its complete classical
    outcome distribution is then sampled for the requested number of shots.
    One RNG is advanced continuously across PUBs and parameter bindings in a
    job, so streams are deterministic without being restarted for each item.
    """

    def __init__(
        self, *, default_shots: int = 1024, seed: int | None = None, precision: int = 32
    ):
        self._validate_positive_integer(default_shots, "default_shots")
        self._validate_positive_integer(precision, "precision")
        if seed is not None and (not isinstance(seed, Integral) or isinstance(seed, bool)):
            raise TypeError("seed must be an integer or None.")
        self._default_shots = int(default_shots)
        self._seed = None if seed is None else int(seed)
        self._precision = int(precision)

    @property
    def default_shots(self) -> int:
        return self._default_shots

    @property
    def seed(self) -> int | None:
        return self._seed

    @property
    def precision(self) -> int:
        return self._precision

    def run(
        self, pubs: Iterable[SamplerPubLike], *, shots: int | None = None
    ) -> QSeqPrimitiveJob:
        effective_shots = self._default_shots if shots is None else shots
        coerced_pubs = [SamplerPub.coerce(pub, effective_shots) for pub in pubs]
        if any(not pub.circuit.cregs for pub in coerced_pubs):
            warnings.warn(
                "One of your circuits has no output classical registers and so the result "
                "will be empty. Did you mean to add measurement instructions?",
                UserWarning,
                stacklevel=2,
            )
        return QSeqPrimitiveJob(lambda: self._run(coerced_pubs))

    def _run(self, pubs: list[SamplerPub]) -> PrimitiveResult[SamplerPubResult]:
        rng = random.Random(self._seed)
        results = [self._run_pub(pub, rng) for pub in pubs]
        return PrimitiveResult(
            results,
            metadata={
                "version": 2,
                "simulator": "qseqsim",
                "execution_mode": "symbolic_distribution",
            },
        )

    def _run_pub(self, pub: SamplerPub, rng: random.Random) -> SamplerPubResult:
        bound_circuits = pub.parameter_values.bind_all(pub.circuit)
        layouts = [
            _RegisterLayout(
                register.name,
                register.size,
                tuple(pub.circuit.find_bit(bit).index for bit in register),
            )
            for register in pub.circuit.cregs
        ]
        arrays = {
            layout.name: np.zeros(
                pub.shape + (pub.shots, (layout.size + 7) // 8), dtype=np.uint8
            )
            for layout in layouts
        }

        for index, bound_circuit in np.ndenumerate(bound_circuits):
            distribution = run_symbolic_distribution(bound_circuit, precision=self._precision)
            samples = sample_distribution(distribution, shots=pub.shots, rng=rng)
            for layout in layouts:
                register_samples = [
                    self._extract_register(sample, layout.global_indices) for sample in samples
                ]
                arrays[layout.name][index] = BitArray.from_samples(
                    register_samples, num_bits=layout.size
                ).array

        data = {
            layout.name: BitArray(arrays[layout.name], layout.size) for layout in layouts
        }
        return SamplerPubResult(
            DataBin(**data, shape=pub.shape),
            metadata={
                "shots": pub.shots,
                "circuit_metadata": pub.circuit.metadata,
                "simulator": "qseqsim",
                "execution_mode": "symbolic_distribution",
            },
        )

    @staticmethod
    def _extract_register(outcome: int, global_indices: tuple[int, ...]) -> int:
        value = 0
        for register_index, global_index in enumerate(global_indices):
            value |= ((outcome >> global_index) & 1) << register_index
        return value

    @staticmethod
    def _validate_positive_integer(value, name: str) -> None:
        if not isinstance(value, Integral) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer.")
        if value <= 0:
            raise ValueError(f"{name} must be positive.")


QSeqSampler = QSeqSamplerV2


__all__ = ["QSeqPrimitiveJob", "QSeqSampler", "QSeqSamplerV2"]
