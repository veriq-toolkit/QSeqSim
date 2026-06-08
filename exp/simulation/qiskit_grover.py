import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.benchmark_circuits import build_grover_loop_circuit


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _preset_env(name: str, default: str) -> list[int]:
    value = os.environ.get(name, default)
    return [int(part.strip()) for part in value.split(",") if part.strip()]


circ = build_grover_loop_circuit(_int_env("QSEQSIM_QISKIT_GROVER_N", 4))
sim_mode = "preset"
preset_values = {0: _preset_env("QSEQSIM_QISKIT_GROVER_PRESET", "1")}
sim_backend = "bddseqsim_lowering"
