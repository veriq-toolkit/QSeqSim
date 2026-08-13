#!/usr/bin/env python3
"""Large-width structured benchmark complementing ecosystem_benchmark.py.

Q4-A compares identical finite circuits that measure only q[0].  Q4-B records
the Qiskit-to-BDDSeqSim preset-path capability used by the FM artifact.  Q4-B
is deliberately not reported as an Aer speed comparison because it computes a
conditioned symbolic path rather than a shot sample or complete distribution.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import ecosystem_benchmark as base


DEFAULT_QRW_WIDTHS = (12, 14, 16, 18, 20, 24, 32, 64, 128, 256, 512, 1024)
DEFAULT_GROVER_WIDTHS = (12, 14, 16, 18, 20, 24, 32, 64, 128, 256)
DEFAULT_CAPABILITY_CASES = (
    ("qrw", 16, 1),
    ("qrw", 128, 1),
    ("qrw", 1024, 1),
    ("qrw", 16, 3),
    ("qrw", 128, 3),
    ("grover", 16, 1),
    ("grover", 128, 1),
    ("grover", 256, 1),
)


def statevector_minimum_gib(qubits: int) -> float | str:
    """Lower bound for a complex128 dense state, excluding simulator overhead."""
    exponent = qubits - 26
    if exponent <= 50:
        return float(2**exponent)
    return f"2^{exponent}"


def statevector_preflight_skip(qubits: int, limit_gib: float) -> bool:
    return qubits - 26 > math.log2(limit_gib)


def progress(message: str) -> None:
    print(f"[q4] {message}", flush=True)


def _capability_case_name(family: str, qubits: int, iterations: int) -> str:
    return f"{family}_preset_path_q{qubits}_i{iterations}"


def capability_worker(family: str, qubits: int, iterations: int) -> None:
    from qseqsim import QuantumCircuitParser
    from qseqsim.benchmark_circuits import (
        build_grover_loop_circuit,
        build_qrw_loop_circuit,
        grover_iteration_ops,
        qrw_iteration_ops,
    )
    from qseqsim.seqsim_lowering import run_bddseqsim_lowered

    if family == "qrw":
        circuit = build_qrw_loop_circuit(qubits)
        structure_ops = len(qrw_iteration_ops(qubits))
    elif family == "grover":
        circuit = build_grover_loop_circuit(qubits)
        structure_ops = len(grover_iteration_ops(qubits))
    else:
        raise ValueError(f"unknown capability family: {family}")

    parse_started = time.perf_counter()
    blocks = QuantumCircuitParser(circuit).parse()
    parse_seconds = time.perf_counter() - parse_started
    preset_path = [0] * (iterations - 1) + [1]
    result = run_bddseqsim_lowered(blocks, preset_path)
    print(
        json.dumps(
            {
                "suite": "q4_capability",
                "track": "preset_path_capability",
                "task": "conditioned_preset_measurement_path",
                "case": _capability_case_name(family, qubits, iterations),
                "family": family,
                "engine": "qseqsim_bddseqsim_lowering",
                "method": "symbolic_preset_path",
                "qubits": qubits,
                "iterations": iterations,
                "structure_ops": structure_ops,
                "preset_path": preset_path,
                "parse_seconds": parse_seconds,
                "setup_seconds": result.setup_s,
                "simulation_seconds": result.sim_s,
                "wall_seconds": parse_seconds + result.total_s,
                "probability": result.probability,
                "probability_trace": result.probability_trace,
                "peak_rss_mib": base.peak_rss_mib(),
                "status": "ok",
            },
            sort_keys=True,
        )
    )


def run_capability_worker(
    family: str, qubits: int, iterations: int, timeout: float
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--capability-worker",
        family,
        str(qubits),
        str(iterations),
    ]
    started = time.perf_counter()
    common = {
        "suite": "q4_capability",
        "track": "preset_path_capability",
        "task": "conditioned_preset_measurement_path",
        "case": _capability_case_name(family, qubits, iterations),
        "family": family,
        "engine": "qseqsim_bddseqsim_lowering",
        "method": "symbolic_preset_path",
        "qubits": qubits,
        "iterations": iterations,
    }
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
        return {**common, "status": "timeout", "wall_seconds": time.perf_counter() - started}
    if completed.returncode != 0:
        return {
            **common,
            "status": "error",
            "error": completed.stderr.strip()[-2000:],
            "wall_seconds": time.perf_counter() - started,
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def _not_run_row(
    family: str,
    engine: str,
    qubits: int,
    iterations: int,
    shots: int,
    status: str,
    reason: str,
) -> dict[str, Any]:
    case = f"{family}_projected_q{qubits}_i{iterations}"
    method = base.AER_METHODS.get(engine, {}).get("method", "symbolic_distribution")
    return {
        "suite": "q4_projected",
        "track": "same_circuit_q0_projection",
        "task": "q0_projection",
        "case": case,
        "family": family,
        "engine": engine,
        "method": method,
        "qubits": qubits,
        "iterations": iterations,
        "shots": shots,
        "repeat": 0,
        "statevector_minimum_gib": statevector_minimum_gib(qubits),
        "status": status,
        "error": reason,
    }


def run_correctness_bridge(
    family: str, qubits: int, iterations: int, shots: int, timeout: float
) -> dict[str, Any]:
    case = f"{family}_projected_q{qubits}_i{iterations}"
    results = {
        engine: base.run_worker(engine, case, shots, timeout)
        for engine in ("aer_statevector", "aer_mps", "qseqsim")
    }
    if not all(row["status"] == "ok" for row in results.values()):
        return {"case": case, "status": "unsupported-or-error", "details": results}
    statevector_counts = results["aer_statevector"]["counts"]
    distances = {
        engine: base.total_variation(statevector_counts, row["counts"])
        for engine, row in results.items()
        if engine != "aer_statevector"
    }
    supports = {engine: sorted(row["counts"]) for engine, row in results.items()}
    passed = max(distances.values(), default=0.0) <= 0.10 and len(set(map(tuple, supports.values()))) == 1
    return {
        "case": case,
        "status": "pass" if passed else "fail",
        "shots_per_engine": shots,
        "total_variation_from_statevector": distances,
        "supports": supports,
    }


def run_projected_family(
    family: str,
    widths: tuple[int, ...],
    iterations: int,
    shots: int,
    repeats: int,
    timeout: float,
    statevector_max_gib: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for engine in ("aer_statevector", "aer_mps", "qseqsim"):
        boundary: str | None = None
        for qubits in widths:
            if boundary is not None:
                progress(f"{family} {engine} q{qubits}: not run after {boundary}")
                rows.append(
                    _not_run_row(
                        family,
                        engine,
                        qubits,
                        iterations,
                        shots,
                        "not_run_after_boundary",
                        boundary,
                    )
                )
                continue
            if engine == "aer_statevector" and statevector_preflight_skip(
                qubits, statevector_max_gib
            ):
                boundary = (
                    f"dense complex128 lower bound exceeds {statevector_max_gib:g} GiB "
                    "preflight limit"
                )
                rows.append(
                    _not_run_row(
                        family,
                        engine,
                        qubits,
                        iterations,
                        shots,
                        "preflight_skip",
                        boundary,
                    )
                )
                progress(f"{family} {engine} q{qubits}: {boundary}")
                continue

            case = f"{family}_projected_q{qubits}_i{iterations}"
            width_rows = []
            for repeat in range(1, repeats + 1):
                progress(
                    f"{family} {engine} q{qubits}: repeat {repeat}/{repeats}"
                )
                row = base.run_worker(engine, case, shots, timeout)
                row.update(
                    {
                        "suite": "q4_projected",
                        "track": "same_circuit_q0_projection",
                        "repeat": repeat,
                        "statevector_minimum_gib": statevector_minimum_gib(qubits),
                    }
                )
                rows.append(row)
                width_rows.append(row)
                if row["status"] != "ok":
                    break
            if any(row["status"] != "ok" for row in width_rows):
                failure = next(row for row in width_rows if row["status"] != "ok")
                boundary = f"{failure['status']} at {qubits} qubits"
                progress(f"{family} {engine}: stopping after {boundary}")
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["suite"], row["case"], row["engine"])
        groups.setdefault(key, []).append(row)
    output = []
    for (suite, case, engine), group in groups.items():
        successful = [row for row in group if row["status"] == "ok"]
        item: dict[str, Any] = {
            "suite": suite,
            "case": case,
            "engine": engine,
            "statuses": sorted({row["status"] for row in group}),
            "successful_repeats": len(successful),
        }
        for field in (
            "wall_seconds",
            "symbolic_build_seconds",
            "sampling_seconds",
            "parse_seconds",
            "simulation_seconds",
            "peak_rss_mib",
        ):
            values = [row[field] for row in successful if row.get(field) is not None]
            item[f"median_{field}"] = statistics.median(values) if values else None
        if successful:
            for field in ("qubits", "iterations", "shots", "branch_outcomes", "probability"):
                item[field] = successful[0].get(field)
        output.append(item)
    return output


CSV_FIELDS = [
    "suite",
    "track",
    "task",
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
    "statevector_minimum_gib",
    "compile_seconds",
    "parse_seconds",
    "wall_seconds",
    "setup_seconds",
    "simulation_seconds",
    "symbolic_build_seconds",
    "sampling_seconds",
    "branch_outcomes",
    "bdd_peak_nodes",
    "peak_rss_mib",
    "observed_outcomes",
    "probability",
    "preset_path",
    "probability_trace",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    parser.add_argument("--repeats", type=int, choices=range(3, 6), default=3)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--correctness-shots", type=int, default=4096)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--qrw-widths", type=base.parse_int_list, default=DEFAULT_QRW_WIDTHS)
    parser.add_argument(
        "--grover-widths", type=base.parse_int_list, default=DEFAULT_GROVER_WIDTHS
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--capability-timeout", type=float, default=600.0)
    parser.add_argument("--statevector-max-gib", type=float, default=2.0)
    parser.add_argument(
        "--cpu-label", default=None, help="override CPU metadata when sandboxed"
    )
    parser.add_argument(
        "--ram-gib", type=float, default=None, help="override RAM metadata when sandboxed"
    )
    parser.add_argument("--skip-capability", action="store_true")
    parser.add_argument("--stem", default=None)
    parser.add_argument(
        "--capability-worker", nargs=3, metavar=("FAMILY", "QUBITS", "ITERATIONS")
    )
    args = parser.parse_args()

    if args.capability_worker:
        family, qubits, iterations = args.capability_worker
        capability_worker(family, int(qubits), int(iterations))
        return
    if min(
        args.shots,
        args.correctness_shots,
        args.iterations,
        args.timeout,
        args.capability_timeout,
        args.statevector_max_gib,
    ) <= 0:
        parser.error("shots, iterations, timeouts, and memory limit must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = base.environment()
    if args.cpu_label:
        env["cpu"] = args.cpu_label
    if args.ram_gib is not None:
        env["ram_gib"] = args.ram_gib
    progress("running q12 correctness bridges")
    bridges = [
        run_correctness_bridge(family, 12, args.iterations, args.correctness_shots, args.timeout)
        for family in ("qrw", "grover")
    ]
    payload: dict[str, Any] = {
        "environment": env,
        "configuration": {
            "qrw_widths": args.qrw_widths,
            "grover_widths": args.grover_widths,
            "iterations": args.iterations,
            "shots": args.shots,
            "correctness_shots": args.correctness_shots,
            "repeats": args.repeats,
            "timeout_seconds_per_projected_worker": args.timeout,
            "timeout_seconds_per_capability_worker": args.capability_timeout,
            "statevector_preflight_limit_gib": args.statevector_max_gib,
            "timed_scope": "backend.run(...).result(); circuit construction and transpile excluded",
            "memory_scope": "absolute per-worker process peak RSS",
            "simulation": "ideal/no-noise",
            "q4_projected_semantics": "same finite circuit and q[0] measurement for every backend",
            "q4_capability_semantics": (
                "conditioned preset measurement path; capability evidence only, not an Aer ratio"
            ),
        },
        "correctness_bridges": bridges,
    }
    stem = args.stem or (
        f"ecosystem_large_scale_{platform.system().lower()}_"
        f"{platform.machine().lower()}_{env['date']}"
    )
    json_path = args.output_dir / f"{stem}.json"
    csv_path = args.output_dir / f"{stem}.csv"
    if any(item["status"] != "pass" for item in bridges):
        payload["aborted_after_correctness_bridge"] = True
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise SystemExit("Q4 correctness bridge failed; performance runs were not started")

    rows = run_projected_family(
        "qrw",
        args.qrw_widths,
        args.iterations,
        args.shots,
        args.repeats,
        args.timeout,
        args.statevector_max_gib,
    )
    rows.extend(
        run_projected_family(
            "grover",
            args.grover_widths,
            args.iterations,
            args.shots,
            args.repeats,
            args.timeout,
            args.statevector_max_gib,
        )
    )
    if not args.skip_capability:
        for family, qubits, iterations in DEFAULT_CAPABILITY_CASES:
            progress(f"capability {family} q{qubits} i{iterations}")
            row = run_capability_worker(
                family, qubits, iterations, args.capability_timeout
            )
            row["repeat"] = 1
            rows.append(row)

    payload["summaries"] = summarize(rows)
    write_csv(csv_path, rows)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    progress(f"wrote {csv_path} and {json_path}")


if __name__ == "__main__":
    main()
