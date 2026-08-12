"""Qiskit :class:`~qiskit.providers.BackendV2` compatibility layer."""

from __future__ import annotations

import random
import uuid
from collections import Counter
from collections.abc import Sequence
from numbers import Integral

from qiskit import QuantumCircuit
from qiskit.circuit import ForLoopOp, IfElseOp, Measure, WhileLoopOp
from qiskit.circuit.library import (
    CCXGate,
    CSwapGate,
    CXGate,
    CZGate,
    HGate,
    MCXGate,
    SGate,
    SdgGate,
    SwapGate,
    TGate,
    TdgGate,
    XGate,
    YGate,
    ZGate,
)
from qiskit.providers import BackendV2, JobStatus, JobV1, Options
from qiskit.result import Result
from qiskit.transpiler import Target

from .simulator import BDDSimulator


class QSeqSimJob(JobV1):
    """A completed synchronous local QSeqSim job."""

    def __init__(self, backend: "QSeqSimBackend", job_id: str, result: Result):
        super().__init__(backend, job_id)
        self._result = result

    def submit(self) -> None:
        """No-op because local symbolic execution completed in ``run``."""

    def result(self, timeout=None) -> Result:
        return self._result

    def status(self) -> JobStatus:
        return JobStatus.DONE

    def cancel(self) -> bool:
        return False


class QSeqSimBackend(BackendV2):
    """BackendV2 facade for QSeqSim's direct-circuit symbolic engine.

    The target is intentionally conservative: it advertises only operations
    whose complete parameter domains are accepted by the direct frontend.
    Discrete-angle rotations accepted by direct execution are therefore not
    advertised as general parameterized target operations.
    """

    def __init__(self, num_qubits: int = 256, precision: int = 32, **options):
        if not isinstance(num_qubits, int) or isinstance(num_qubits, bool) or num_qubits < 1:
            raise ValueError("num_qubits must be a positive integer.")
        if not isinstance(precision, int) or isinstance(precision, bool) or precision < 1:
            raise ValueError("precision must be a positive integer.")
        self._precision = precision
        self._target = self._build_target(num_qubits)
        super().__init__(
            name="qseqsim",
            description="QSeqSim symbolic dynamic-circuit simulator",
            backend_version="0.1.0.dev0",
            **options,
        )

    @staticmethod
    def _build_target(num_qubits: int) -> Target:
        target = Target(
            description="QSeqSim exact symbolic operations (ideal all-to-all simulator)",
            num_qubits=num_qubits,
        )
        for instruction in (
            XGate(),
            YGate(),
            ZGate(),
            HGate(),
            SGate(),
            SdgGate(),
            TGate(),
            TdgGate(),
            CXGate(),
            CZGate(),
            SwapGate(),
            CCXGate(),
            CSwapGate(),
            Measure(),
        ):
            target.add_instruction(instruction)

        # Variable-width and control-flow operations are represented by their
        # classes in Target, as prescribed by Qiskit's public Target API.
        target.add_instruction(MCXGate, name="mcx")
        target.add_instruction(IfElseOp, name="if_else")
        target.add_instruction(WhileLoopOp, name="while_loop")
        target.add_instruction(ForLoopOp, name="for_loop")
        return target

    @property
    def target(self) -> Target:
        return self._target

    @property
    def max_circuits(self) -> None:
        return None

    @classmethod
    def _default_options(cls) -> Options:
        return Options(shots=1024, memory=False, seed_simulator=None)

    def run(self, run_input, **options):
        unknown = set(options).difference(self.options)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise AttributeError(f"Unsupported QSeqSim backend option(s): {names}.")
        effective = {name: options.get(name, getattr(self.options, name)) for name in self.options}
        shots = effective["shots"]
        memory = effective["memory"]
        seed = effective["seed_simulator"]
        self._validate_run_options(shots, memory, seed)
        circuits = self._normalize_run_input(run_input)
        rng = random.Random(seed)
        job_id = str(uuid.uuid4())

        experiment_results = [
            self._run_circuit(circuit, shots=shots, memory=memory, rng=rng)
            for circuit in circuits
        ]
        result = Result.from_dict(
            {
                "backend_name": self.name,
                "backend_version": self.backend_version,
                "job_id": job_id,
                "qobj_id": None,
                "success": True,
                "status": "COMPLETED",
                "results": experiment_results,
            }
        )
        return QSeqSimJob(self, job_id, result)

    @staticmethod
    def _validate_run_options(shots, memory, seed) -> None:
        if not isinstance(shots, Integral) or isinstance(shots, bool) or shots < 1:
            raise ValueError("shots must be a positive integer.")
        if not isinstance(memory, bool):
            raise TypeError("memory must be a bool.")
        if seed is not None and (not isinstance(seed, Integral) or isinstance(seed, bool)):
            raise TypeError("seed_simulator must be an integer or None.")

    def _normalize_run_input(self, run_input) -> list[QuantumCircuit]:
        if isinstance(run_input, QuantumCircuit):
            circuits = [run_input]
        elif isinstance(run_input, Sequence) and not isinstance(run_input, (str, bytes)):
            circuits = list(run_input)
        else:
            raise TypeError("run_input must be a QuantumCircuit or a circuit sequence.")
        if not circuits:
            raise ValueError("run_input circuit sequence must not be empty.")
        for circuit in circuits:
            if not isinstance(circuit, QuantumCircuit):
                raise TypeError(
                    "run_input contains a non-QuantumCircuit value: "
                    f"{type(circuit).__name__}."
                )
            if circuit.num_qubits > self.num_qubits:
                raise ValueError(
                    f"Circuit '{circuit.name}' has {circuit.num_qubits} qubits, exceeding "
                    f"this backend's {self.num_qubits}-qubit Target."
                )
        return circuits

    def _run_circuit(
        self, circuit: QuantumCircuit, *, shots: int, memory: bool, rng: random.Random
    ) -> dict:
        # Constructing directly from the CP3 parser is deliberate: there is no
        # OpenQASM serialization or reparsing in the BackendV2 path.
        simulator = BDDSimulator(
            self._parse_direct(circuit), precision=self._precision
        )
        distribution = simulator.run_distribution(num_clbits=circuit.num_clbits)
        outcomes = list(distribution)
        sampled = rng.choices(
            outcomes,
            weights=[distribution[outcome] for outcome in outcomes],
            k=int(shots),
        )
        counts = {hex(outcome): count for outcome, count in Counter(sampled).items()}
        data = {"counts": counts}
        if memory:
            data["memory"] = [hex(outcome) for outcome in sampled]
        return {
            "shots": int(shots),
            "success": True,
            "status": "DONE",
            "meas_level": 2,
            "data": data,
            "header": {
                "name": circuit.name,
                "memory_slots": circuit.num_clbits,
                "creg_sizes": [[register.name, register.size] for register in circuit.cregs],
            },
        }

    @staticmethod
    def _parse_direct(circuit: QuantumCircuit) -> list:
        # Local import avoids an import cycle through qseqsim.__init__.
        from .qiskit_frontend import QuantumCircuitParser

        return QuantumCircuitParser(circuit).parse()


__all__ = ["QSeqSimBackend", "QSeqSimJob"]
