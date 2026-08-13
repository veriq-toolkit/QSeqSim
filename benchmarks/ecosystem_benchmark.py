#!/usr/bin/env python3
"""Reproducible regime comparison between QSeqSim and Qiskit Aer.

Q1 preserves the original nine-case compatibility/sanity suite. Q2 varies
shots for three representative circuits. Q3 varies structured circuit size at
a fixed shot count. Every measured run uses a fresh worker process.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit, transpile

from qseqsim.benchmark_circuits import (
    apply_grover_iteration,
    apply_qrw_iteration,
    grover_iteration_ops,
    qrw_iteration_ops,
)


SEED = 20260812
DEFAULT_SHOTS_GRID = (1, 10, 100, 1_000, 10_000, 100_000)
DEFAULT_Q3_QUBITS = (4, 6, 8, 10, 12)

Q1_CASES: dict[str, dict[str, Any]] = {
    "bell": {"family": "ordinary", "qubits": 2, "iterations": 0},
    "measurement_while": {"family": "dynamic", "qubits": 2, "iterations": 1},
    "if_in_while": {"family": "dynamic", "qubits": 3, "iterations": 1},
    "qrw_q4_i1": {"family": "qrw", "qubits": 4, "iterations": 1},
    "qrw_q8_i2": {"family": "qrw", "qubits": 8, "iterations": 2},
    "qrw_q12_i4": {"family": "qrw", "qubits": 12, "iterations": 4},
    "grover_q4_i1": {"family": "grover", "qubits": 4, "iterations": 1},
    "grover_q6_i2": {"family": "grover", "qubits": 6, "iterations": 2},
    "grover_q8_i4": {"family": "grover", "qubits": 8, "iterations": 4},
}

Q2_CASES = ("measurement_while", "qrw_q8_i2", "grover_q6_i2")
EXPECTED_OUTCOMES = {
    "bell": {"00", "11"},
    "measurement_while": {"01", "11"},
    "if_in_while": {"01", "11"},
}

AER_METHODS = {
    "aer_statevector": {"method": "statevector", "shot_branching_enable": False},
    "aer_statevector_shot_branching": {
        "method": "statevector",
        "shot_branching_enable": True,
    },
    "aer_mps": {"method": "matrix_product_state", "shot_branching_enable": False},
}


def parse_int_list(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values or any(item < 1 for item in values):
        raise argparse.ArgumentTypeError("expected comma-separated positive integers")
    return values


def case_spec(name: str) -> dict[str, Any]:
    if name in Q1_CASES:
        return {**Q1_CASES[name], "task": "full_counts"}
    match = re.fullmatch(
        r"(?P<family>qrw|grover)(?P<projected>_projected)?_q"
        r"(?P<qubits>\d+)_i(?P<iterations>\d+)",
        name,
    )
    if match is None:
        raise ValueError(f"unknown benchmark case: {name}")
    return {
        "family": match.group("family"),
        "qubits": int(match.group("qubits")),
        "iterations": int(match.group("iterations")),
        "task": "q0_projection" if match.group("projected") else "full_counts",
    }


def build_case(name: str) -> tuple[QuantumCircuit, int]:
    spec = case_spec(name)
    family = spec["family"]
    n = spec["qubits"]
    iterations = spec["iterations"]

    if family == "ordinary":
        circuit = QuantumCircuit(2, 2, name=name)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])
        return circuit, 3

    if name == "measurement_while":
        circuit = QuantumCircuit(2, 2, name=name)
        with circuit.while_loop((circuit.clbits[0], 0)):
            circuit.h(0)
            circuit.measure(0, 1)
            circuit.x(1)
            circuit.measure(1, 0)
        # Aer 0.17.2 otherwise reports "Invalid jump destination" for this
        # while-last-instruction shape. This repeats its deterministic guard.
        circuit.measure(1, 0)
        return circuit, 5

    if name == "if_in_while":
        circuit = QuantumCircuit(3, 2, name=name)
        with circuit.while_loop((circuit.clbits[0], 0)):
            circuit.h(0)
            circuit.measure(0, 1)
            with circuit.if_test((circuit.clbits[1], 1)):
                circuit.x(1)
            circuit.x(2)
            circuit.measure(2, 0)
        circuit.measure(1, 1)
        return circuit, 6

    if family not in {"qrw", "grover"}:
        raise ValueError(f"unsupported benchmark family: {family}")
    projected = spec["task"] == "q0_projection"
    circuit = QuantumCircuit(n, 1 if projected else n, name=name)
    body = apply_qrw_iteration if family == "qrw" else apply_grover_iteration
    body_ops = qrw_iteration_ops(n) if family == "qrw" else grover_iteration_ops(n)
    with circuit.for_loop(range(iterations)):
        body(circuit, circuit.qubits)
    if projected:
        circuit.measure(0, 0)
    else:
        circuit.measure(range(n), range(n))
    return circuit, iterations * len(body_ops) + (1 if projected else n)


def peak_rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def _qseqsim_backend_run(
    circuit: QuantumCircuit, shots: int
) -> tuple[Any, dict[str, Any]]:
    import qseqsim.qiskit_backend as backend_module
    from qseqsim import QSeqSimBackend

    timings: dict[str, Any] = {
        "symbolic_build_seconds": 0.0,
        "sampling_seconds": 0.0,
        "branch_outcomes": None,
        "bdd_peak_nodes": None,
    }
    original_build = backend_module.run_symbolic_distribution
    original_sample = backend_module.sample_distribution

    def timed_build(*args, **kwargs):
        started = time.perf_counter()
        distribution = original_build(*args, **kwargs)
        timings["symbolic_build_seconds"] += time.perf_counter() - started
        timings["branch_outcomes"] = len(distribution)
        return distribution

    def timed_sample(*args, **kwargs):
        started = time.perf_counter()
        sampled = original_sample(*args, **kwargs)
        timings["sampling_seconds"] += time.perf_counter() - started
        return sampled

    backend_module.run_symbolic_distribution = timed_build
    backend_module.sample_distribution = timed_sample
    try:
        backend = QSeqSimBackend(num_qubits=circuit.num_qubits)
        compile_started = time.perf_counter()
        compiled = transpile(circuit, backend, optimization_level=0)
        timings["compile_seconds"] = time.perf_counter() - compile_started
        started = time.perf_counter()
        result = backend.run(compiled, shots=shots, seed_simulator=SEED).result()
        timings["wall_seconds"] = time.perf_counter() - started
    finally:
        backend_module.run_symbolic_distribution = original_build
        backend_module.sample_distribution = original_sample
    return result, timings


def _aer_backend_run(
    engine: str, circuit: QuantumCircuit, shots: int
) -> tuple[Any, dict[str, Any]]:
    from qiskit_aer import AerSimulator

    config = AER_METHODS[engine]
    backend = AerSimulator(**config)
    compile_started = time.perf_counter()
    compiled = transpile(circuit, backend, optimization_level=0)
    compile_seconds = time.perf_counter() - compile_started
    started = time.perf_counter()
    result = backend.run(compiled, shots=shots, seed_simulator=SEED).result()
    return result, {
        "compile_seconds": compile_seconds,
        "wall_seconds": time.perf_counter() - started,
        "symbolic_build_seconds": None,
        "sampling_seconds": None,
        "branch_outcomes": None,
        "bdd_peak_nodes": None,
    }


def worker(engine: str, case: str, shots: int) -> None:
    circuit, structure_ops = build_case(case)
    if engine == "qseqsim":
        result, timings = _qseqsim_backend_run(circuit, shots)
        method = "symbolic_distribution"
        shot_branching = False
    elif engine in AER_METHODS:
        result, timings = _aer_backend_run(engine, circuit, shots)
        method = AER_METHODS[engine]["method"]
        shot_branching = AER_METHODS[engine]["shot_branching_enable"]
    else:
        raise ValueError(f"unknown engine: {engine}")
    if not result.success:
        raise RuntimeError(str(result.status))
    counts = dict(result.get_counts())
    spec = case_spec(case)
    print(
        json.dumps(
            {
                "engine": engine,
                "method": method,
                "shot_branching_enable": shot_branching,
                "case": case,
                **spec,
                "structure_ops": structure_ops,
                "shots": shots,
                "seed": SEED,
                **timings,
                "peak_rss_mib": peak_rss_mib(),
                "observed_outcomes": len(counts),
                "counts": counts,
                "status": "ok",
            },
            sort_keys=True,
        )
    )


def run_worker(engine: str, case: str, shots: int, timeout: float) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        engine,
        case,
        str(shots),
    ]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired:
        return {
            "engine": engine,
            "case": case,
            **case_spec(case),
            "shots": shots,
            "status": "timeout",
            "wall_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0:
        return {
            "engine": engine,
            "case": case,
            **case_spec(case),
            "shots": shots,
            "status": "error",
            "error": completed.stderr.strip()[-2000:],
            "wall_seconds": time.perf_counter() - started,
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def total_variation(left: dict[str, int], right: dict[str, int]) -> float:
    left_total = sum(left.values())
    right_total = sum(right.values())
    outcomes = set(left) | set(right)
    return 0.5 * sum(
        abs(left.get(key, 0) / left_total - right.get(key, 0) / right_total)
        for key in outcomes
    )


def _system_value(command: list[str]) -> str | None:
    try:
        return subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=5
        ).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def environment() -> dict[str, Any]:
    import dd
    import numpy
    import qiskit
    import qiskit_aer

    if sys.platform == "darwin":
        cpu = _system_value(["sysctl", "-n", "machdep.cpu.brand_string"])
        ram_bytes = _system_value(["sysctl", "-n", "hw.memsize"])
    else:
        cpu = platform.processor()
        if not cpu:
            try:
                cpu = next(
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.startswith("model name")
                )
            except (OSError, StopIteration):
                cpu = None
        ram_bytes = str(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    machine = platform.machine()
    return {
        "date": time.strftime("%Y-%m-%d"),
        "python": platform.python_version(),
        "os": platform.platform(),
        "arch": machine,
        "cpu": cpu or platform.processor() or machine,
        "ram_gib": round(int(ram_bytes) / 2**30, 2) if ram_bytes else None,
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "dd": dd.__version__,
        "dd_backend": "dd.cudd",
        "numpy": numpy.__version__,
        "seed": SEED,
        "formal_shot_branching_platform": sys.platform.startswith("linux")
        and machine in {"x86_64", "amd64"},
    }


CSV_FIELDS = [
    "suite",
    "case",
    "family",
    "engine",
    "method",
    "shot_branching_enable",
    "repeat",
    "status",
    "qubits",
    "iterations",
    "structure_ops",
    "shots",
    "seed",
    "compile_seconds",
    "wall_seconds",
    "symbolic_build_seconds",
    "sampling_seconds",
    "branch_outcomes",
    "bdd_peak_nodes",
    "peak_rss_mib",
    "observed_outcomes",
    "error",
]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["suite"], row["case"], row["engine"], row["shots"])
        groups.setdefault(key, []).append(row)
    summaries = []
    for (suite, case, engine, shots), group in groups.items():
        successful = [row for row in group if row["status"] == "ok"]
        item: dict[str, Any] = {
            "suite": suite,
            "case": case,
            "engine": engine,
            "shots": shots,
            "successful_repeats": len(successful),
        }
        for field in (
            "wall_seconds", "symbolic_build_seconds", "sampling_seconds", "peak_rss_mib"
        ):
            values = [row[field] for row in successful if row.get(field) is not None]
            item[f"median_{field}"] = statistics.median(values) if values else None
        item["statuses"] = sorted({row["status"] for row in group})
        if successful:
            item["branch_outcomes"] = successful[0].get("branch_outcomes")
        summaries.append(item)
    return summaries


def run_q1(correctness_shots: int, timeout: float) -> list[dict[str, Any]]:
    correctness = []
    for case in Q1_CASES:
        results = {
            engine: run_worker(engine, case, correctness_shots, timeout)
            for engine in ("aer_statevector", "qseqsim")
        }
        if all(result["status"] == "ok" for result in results.values()):
            distance = total_variation(
                results["aer_statevector"]["counts"], results["qseqsim"]["counts"]
            )
            observed = {engine: set(result["counts"]) for engine, result in results.items()}
            expected = EXPECTED_OUTCOMES.get(case)
            support_pass = expected is None or all(value == expected for value in observed.values())
            status = "pass" if distance <= 0.10 and support_pass else "fail"
            correctness.append(
                {
                    "case": case,
                    "status": status,
                    "total_variation": distance,
                    "analytical_support_reference": sorted(expected) if expected else None,
                    "analytical_support_pass": support_pass if expected else None,
                    "shots_per_engine": correctness_shots,
                    "aer_outcomes": sorted(results["aer_statevector"]["counts"]),
                    "qseqsim_outcomes": sorted(results["qseqsim"]["counts"]),
                }
            )
        else:
            correctness.append(
                {"case": case, "status": "unsupported-or-error", "details": results}
            )
    return correctness


def measured_rows(
    suite: str,
    cases: list[tuple[str, int]],
    engines: tuple[str, ...],
    repeats: int,
    timeout: float,
) -> list[dict[str, Any]]:
    rows = []
    for case, shots in cases:
        for engine in engines:
            for repeat in range(1, repeats + 1):
                row = run_worker(engine, case, shots, timeout)
                row.update({"suite": suite, "repeat": repeat})
                rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--suite", choices=("all", "q1", "q2", "q3"), default="all")
    parser.add_argument("--repeats", type=int, choices=range(3, 6), default=3)
    parser.add_argument("--shots-grid", type=parse_int_list, default=DEFAULT_SHOTS_GRID)
    parser.add_argument("--q3-shots", type=int, default=1024)
    parser.add_argument("--q3-qubits", type=parse_int_list, default=DEFAULT_Q3_QUBITS)
    parser.add_argument("--q3-iterations", type=int, default=2)
    parser.add_argument("--correctness-shots", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--cpu-label", default=None, help="override CPU metadata when sandboxed"
    )
    parser.add_argument(
        "--ram-gib", type=float, default=None, help="override RAM metadata when sandboxed"
    )
    parser.add_argument(
        "--enable-macos-shot-branching",
        action="store_true",
        help="probe only; macOS shot-branching timings are excluded from formal conclusions",
    )
    parser.add_argument("--stem", default=None)
    parser.add_argument("--worker", nargs=3, metavar=("ENGINE", "CASE", "SHOTS"))
    args = parser.parse_args()

    if args.worker:
        engine, case, shots = args.worker
        worker(engine, case, int(shots))
        return
    if args.q3_iterations < 1 or args.q3_shots < 1 or args.timeout <= 0:
        parser.error("Q3 iterations, Q3 shots, and timeout must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = environment()
    if args.cpu_label:
        env["cpu"] = args.cpu_label
    if args.ram_gib is not None:
        env["ram_gib"] = args.ram_gib
    correctness = run_q1(args.correctness_shots, args.timeout)
    payload: dict[str, Any] = {
        "environment": env,
        "configuration": {
            "suite": args.suite,
            "shots_grid": args.shots_grid,
            "q3_shots": args.q3_shots,
            "q3_qubits": args.q3_qubits,
            "q3_iterations": args.q3_iterations,
            "correctness_shots": args.correctness_shots,
            "repeats": args.repeats,
            "timeout_seconds_per_worker": args.timeout,
            "macos_shot_branching_probe_requested": args.enable_macos_shot_branching,
            "timed_scope": "backend.run(...).result(); circuit construction and transpile excluded",
            "memory_scope": "absolute per-worker process peak RSS",
            "bdd_metric": "NA: no stable public peak-node metric is exposed by the distribution adapter",
            "simulation": "ideal/no-noise",
        },
        "q1_correctness": correctness,
    }
    stem = args.stem or f"ecosystem_extended_{platform.system().lower()}_{platform.machine().lower()}_{env['date']}"
    json_path = args.output_dir / f"{stem}.json"
    csv_path = args.output_dir / f"{stem}.csv"
    if any(item["status"] != "pass" for item in correctness):
        payload["aborted_after_q1"] = True
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise SystemExit("Q1 correctness failed; performance suites were not run")

    rows: list[dict[str, Any]] = []
    if args.suite in {"all", "q2"}:
        q2_engines = ["aer_statevector"]
        if env["formal_shot_branching_platform"] or args.enable_macos_shot_branching:
            q2_engines.append("aer_statevector_shot_branching")
        q2_engines.append("qseqsim")
        q2_cases = [
            (case, shots) for case in Q2_CASES for shots in args.shots_grid
        ]
        rows.extend(
            measured_rows(
                "q2_shots", q2_cases, tuple(q2_engines), args.repeats, args.timeout
            )
        )
    if args.suite in {"all", "q3"}:
        q3_cases = [
            (f"{family}_q{qubits}_i{args.q3_iterations}", args.q3_shots)
            for family in ("qrw", "grover")
            for qubits in args.q3_qubits
        ]
        rows.extend(
            measured_rows(
                "q3_structured",
                q3_cases,
                ("aer_statevector", "aer_mps", "qseqsim"),
                args.repeats,
                args.timeout,
            )
        )

    payload["summaries"] = summarize(rows)
    if env["formal_shot_branching_platform"]:
        payload["shot_branching_interpretation"] = "formal Linux x86_64 baseline"
    elif args.enable_macos_shot_branching:
        payload["shot_branching_interpretation"] = (
            "diagnostic probe only; macOS arm64 is excluded from formal "
            "shot-branching conclusions"
        )
    else:
        payload["shot_branching_interpretation"] = (
            "not run by default; macOS arm64 is excluded from formal "
            "shot-branching conclusions"
        )
    write_csv(csv_path, rows)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
