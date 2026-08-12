#!/usr/bin/env python3
"""Reproducible QSeqSim/Aer ecosystem benchmark for CP6 release readiness."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

from qiskit import QuantumCircuit, transpile

from qseqsim.benchmark_circuits import (
    apply_grover_iteration,
    apply_qrw_iteration,
    grover_iteration_ops,
    qrw_iteration_ops,
)


SEED = 20260812


CASES = {
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

EXPECTED_OUTCOMES = {
    "bell": {"00", "11"},
    "measurement_while": {"01", "11"},
    "if_in_while": {"01", "11"},
}


def build_case(name: str) -> tuple[QuantumCircuit, int]:
    spec = CASES[name]
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
        # Aer 0.17.2 requires a terminal measurement after this control-flow
        # shape; this repeats the already deterministic guard measurement.
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

    circuit = QuantumCircuit(n, n, name=name)
    body = apply_qrw_iteration if family == "qrw" else apply_grover_iteration
    body_ops = qrw_iteration_ops(n) if family == "qrw" else grover_iteration_ops(n)
    with circuit.for_loop(range(iterations)):
        body(circuit, circuit.qubits)
    circuit.measure(range(n), range(n))
    return circuit, iterations * len(body_ops) + n


def peak_rss_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return value / (1024 * 1024)
    return value / 1024


def worker(engine: str, case: str, shots: int) -> None:
    circuit, structure_ops = build_case(case)
    if engine == "aer":
        from qiskit_aer import AerSimulator

        backend = AerSimulator(method="statevector")
        method = "statevector"
    else:
        from qseqsim import QSeqSimBackend

        backend = QSeqSimBackend(num_qubits=circuit.num_qubits)
        method = "symbolic_distribution"

    compile_start = time.perf_counter()
    compiled = transpile(circuit, backend, optimization_level=0)
    compile_seconds = time.perf_counter() - compile_start
    execution_start = time.perf_counter()
    result = backend.run(compiled, shots=shots, seed_simulator=SEED).result()
    wall_seconds = time.perf_counter() - execution_start
    if not result.success:
        raise RuntimeError(str(result.status))
    counts = dict(result.get_counts())
    print(
        json.dumps(
            {
                "engine": engine,
                "method": method,
                "case": case,
                "family": CASES[case]["family"],
                "qubits": circuit.num_qubits,
                "iterations": CASES[case]["iterations"],
                "structure_ops": structure_ops,
                "shots": shots,
                "seed": SEED,
                "compile_seconds": compile_seconds,
                "wall_seconds": wall_seconds,
                "peak_rss_mib": peak_rss_mib(),
                "counts": counts,
                "status": "ok",
            },
            sort_keys=True,
        )
    )


def run_worker(engine: str, case: str, shots: int, timeout: float) -> dict:
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
            **CASES[case],
            "shots": shots,
            "status": "timeout",
            "wall_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0:
        return {
            "engine": engine,
            "case": case,
            **CASES[case],
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
        abs(left.get(outcome, 0) / left_total - right.get(outcome, 0) / right_total)
        for outcome in outcomes
    )


def environment() -> dict:
    import dd
    import numpy
    import qiskit
    import qiskit_aer

    return {
        "date": "2026-08-12",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "qiskit": qiskit.__version__,
        "qiskit_aer": qiskit_aer.__version__,
        "dd": dd.__version__,
        "numpy": numpy.__version__,
        "seed": SEED,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "case",
        "family",
        "engine",
        "method",
        "repeat",
        "status",
        "qubits",
        "iterations",
        "structure_ops",
        "shots",
        "seed",
        "compile_seconds",
        "wall_seconds",
        "peak_rss_mib",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--shots", type=int, default=512)
    parser.add_argument("--correctness-shots", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--worker", nargs=3, metavar=("ENGINE", "CASE", "SHOTS"))
    args = parser.parse_args()

    if args.worker:
        engine, case, shots = args.worker
        worker(engine, case, int(shots))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    correctness = []
    rows = []
    summaries = []
    for case in CASES:
        sanity = {
            engine: run_worker(engine, case, args.correctness_shots, args.timeout)
            for engine in ("aer", "qseqsim")
        }
        if all(result["status"] == "ok" for result in sanity.values()):
            distance = total_variation(sanity["aer"]["counts"], sanity["qseqsim"]["counts"])
            observed = {
                engine: set(result["counts"]) for engine, result in sanity.items()
            }
            expected = EXPECTED_OUTCOMES.get(case)
            reference_pass = expected is None or all(
                outcomes == expected for outcomes in observed.values()
            )
            correctness.append(
                {
                    "case": case,
                    "status": "pass" if distance <= 0.10 and reference_pass else "fail",
                    "total_variation": distance,
                    "analytical_support_reference": sorted(expected) if expected else None,
                    "analytical_support_pass": reference_pass if expected else None,
                    "shots_per_engine": args.correctness_shots,
                    "aer_outcomes": sorted(sanity["aer"]["counts"]),
                    "qseqsim_outcomes": sorted(sanity["qseqsim"]["counts"]),
                }
            )
        else:
            correctness.append(
                {"case": case, "status": "unsupported-or-error", "details": sanity}
            )

        for engine in ("aer", "qseqsim"):
            engine_rows = []
            for repeat in range(1, args.repeats + 1):
                row = run_worker(engine, case, args.shots, args.timeout)
                row["repeat"] = repeat
                rows.append(row)
                engine_rows.append(row)
            successful = [row for row in engine_rows if row["status"] == "ok"]
            summaries.append(
                {
                    "case": case,
                    "engine": engine,
                    "successful_repeats": len(successful),
                    "median_wall_seconds": (
                        statistics.median(row["wall_seconds"] for row in successful)
                        if successful
                        else None
                    ),
                    "median_peak_rss_mib": (
                        statistics.median(row["peak_rss_mib"] for row in successful)
                        if successful
                        else None
                    ),
                }
            )

    payload = {
        "environment": environment(),
        "configuration": {
            "shots": args.shots,
            "correctness_shots": args.correctness_shots,
            "repeats": args.repeats,
            "timeout_seconds": args.timeout,
            "timed_scope": "backend.run(...).result(); circuit construction and transpile excluded",
            "memory_scope": "absolute per-worker process peak RSS",
        },
        "correctness": correctness,
        "summaries": summaries,
    }
    stem = "ecosystem_benchmark_2026-08-12"
    write_csv(args.output_dir / f"{stem}.csv", rows)
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if any(item["status"] != "pass" for item in correctness):
        raise SystemExit("At least one correctness comparison failed; inspect the JSON result")


if __name__ == "__main__":
    main()
