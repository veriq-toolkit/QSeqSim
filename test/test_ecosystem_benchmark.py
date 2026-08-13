import importlib.util
import sys
from pathlib import Path

import pytest


BENCHMARK_PATH = Path(__file__).parents[1] / "benchmarks" / "ecosystem_benchmark.py"
SPEC = importlib.util.spec_from_file_location("ecosystem_benchmark", BENCHMARK_PATH)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark)

LARGE_BENCHMARK_PATH = (
    Path(__file__).parents[1] / "benchmarks" / "ecosystem_large_scale_benchmark.py"
)
LARGE_SPEC = importlib.util.spec_from_file_location(
    "ecosystem_large_scale_benchmark", LARGE_BENCHMARK_PATH
)
large_benchmark = importlib.util.module_from_spec(LARGE_SPEC)
assert LARGE_SPEC.loader is not None
sys.path.insert(0, str(LARGE_BENCHMARK_PATH.parent))
try:
    LARGE_SPEC.loader.exec_module(large_benchmark)
finally:
    sys.path.pop(0)


def test_q1_retains_all_nine_compatibility_cases():
    assert tuple(benchmark.Q1_CASES) == (
        "bell",
        "measurement_while",
        "if_in_while",
        "qrw_q4_i1",
        "qrw_q8_i2",
        "qrw_q12_i4",
        "grover_q4_i1",
        "grover_q6_i2",
        "grover_q8_i4",
    )
    assert benchmark.Q2_CASES == (
        "measurement_while",
        "qrw_q8_i2",
        "grover_q6_i2",
    )


def test_dynamic_guard_workaround_and_structured_scaling_cases():
    while_circuit, while_ops = benchmark.build_case("measurement_while")
    assert while_ops == 5
    assert while_circuit.data[-1].operation.name == "measure"
    assert while_circuit.data[-2].operation.name == "while_loop"

    qrw, qrw_ops = benchmark.build_case("qrw_q10_i2")
    grover, grover_ops = benchmark.build_case("grover_q10_i2")
    assert (qrw.num_qubits, len(qrw.data), qrw_ops) == (
        10,
        11,
        2 * len(benchmark.qrw_iteration_ops(10)) + 10,
    )
    assert (grover.num_qubits, len(grover.data), grover_ops) == (
        10,
        11,
        2 * len(benchmark.grover_iteration_ops(10)) + 10,
    )

    projected, projected_ops = benchmark.build_case("qrw_projected_q128_i2")
    assert projected.num_qubits == 128
    assert projected.num_clbits == 1
    assert projected.data[-1].qubits == (projected.qubits[0],)
    assert projected.data[-1].clbits == (projected.clbits[0],)
    assert projected_ops == 2 * len(benchmark.qrw_iteration_ops(128)) + 1


def test_strong_aer_baseline_configuration_is_explicit():
    assert benchmark.AER_METHODS["aer_statevector"] == {
        "method": "statevector",
        "shot_branching_enable": False,
    }
    assert benchmark.AER_METHODS["aer_statevector_shot_branching"] == {
        "method": "statevector",
        "shot_branching_enable": True,
    }
    assert benchmark.AER_METHODS["aer_mps"]["method"] == "matrix_product_state"


def test_total_variation_and_summary_decomposition():
    assert benchmark.total_variation(
        {"0": 50, "1": 50}, {"0": 60, "1": 40}
    ) == pytest.approx(0.1)
    rows = [
        {
            "suite": "q2_shots",
            "case": "measurement_while",
            "engine": "qseqsim",
            "shots": 100,
            "status": "ok",
            "wall_seconds": wall,
            "symbolic_build_seconds": build,
            "sampling_seconds": sample,
            "peak_rss_mib": rss,
            "branch_outcomes": 2,
        }
        for wall, build, sample, rss in (
            (1.0, 0.8, 0.1, 100.0),
            (3.0, 2.4, 0.3, 120.0),
            (2.0, 1.6, 0.2, 110.0),
        )
    ]
    summary = benchmark.summarize(rows)[0]
    assert summary["successful_repeats"] == 3
    assert summary["median_wall_seconds"] == 2.0
    assert summary["median_symbolic_build_seconds"] == 1.6
    assert summary["median_sampling_seconds"] == 0.2
    assert summary["median_peak_rss_mib"] == 110.0
    assert summary["branch_outcomes"] == 2


def test_large_scale_benchmark_separates_fair_and_capability_tracks():
    assert large_benchmark.DEFAULT_QRW_WIDTHS[-3:] == (256, 512, 1024)
    assert ("qrw", 1024, 1) in large_benchmark.DEFAULT_CAPABILITY_CASES
    assert large_benchmark.statevector_minimum_gib(30) == 16.0
    assert large_benchmark.statevector_preflight_skip(30, 2.0)
    assert not large_benchmark.statevector_preflight_skip(27, 2.0)

    row = large_benchmark._not_run_row(
        "qrw", "aer_statevector", 1024, 2, 1024, "preflight_skip", "test"
    )
    assert row["track"] == "same_circuit_q0_projection"
    assert row["task"] == "q0_projection"
    assert row["statevector_minimum_gib"] == "2^998"
