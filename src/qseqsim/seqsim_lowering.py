from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Iterable

from .kernel import BDDSeqSim
from .parser import CQC, DQC, SQC, GateOp


class LoweringError(ValueError):
    pass


@dataclass(frozen=True)
class BDDSeqSimPlan:
    num_qubits: int
    external_qubits: tuple[int, ...]
    measure_clbits: tuple[int, ...]
    qubit_map: dict[int, int]
    body_ops: tuple[GateOp, ...]


@dataclass
class BDDSeqSimRunResult:
    probability: float
    probability_trace: list[float]
    sim_s: float
    setup_s: float
    total_s: float


def lower_to_bddseqsim(blocks: list) -> BDDSeqSimPlan:
    if len(blocks) != 1 or not isinstance(blocks[0], SQC):
        raise LoweringError("Expected one top-level SQC block.")

    sqc = blocks[0]
    if not sqc.external_qubits:
        raise LoweringError("BDDSeqSim lowering requires at least one external qubit.")
    external_qubits = tuple(sorted(sqc.external_qubits))
    qubit_map = _build_qubit_map(sqc.global_num_qubits, external_qubits)

    ops = _flatten_cqc_ops(sqc.body_block)
    if not ops:
        raise LoweringError("SQC body is empty.")

    body_ops, measure_ops = _split_trailing_measurements(ops)
    if {op.qubits[0] for op in measure_ops} != set(external_qubits):
        raise LoweringError(
            "Trailing body measurements must cover exactly the SQC external qubits."
        )

    loop_flag_clbits = set(sqc.loop_condition.get("indices", []))
    measure_clbits_by_qubit = {}
    for op in measure_ops:
        if len(op.qubits) != 1 or len(op.c_targets) != 1:
            raise LoweringError("Each trailing measurement must be one qubit -> one clbit.")
        if op.c_targets[0] not in loop_flag_clbits:
            raise LoweringError("Trailing measurements must update the SQC loop flag.")
        measure_clbits_by_qubit[op.qubits[0]] = op.c_targets[0]

    for op in body_ops:
        if op.name == "measure":
            raise LoweringError("Mid-body measurements are not supported by BDDSeqSim lowering.")
        _validate_supported_op(op)

    return BDDSeqSimPlan(
        num_qubits=sqc.global_num_qubits,
        external_qubits=external_qubits,
        measure_clbits=tuple(measure_clbits_by_qubit[q] for q in external_qubits),
        qubit_map=qubit_map,
        body_ops=tuple(_remap_op(op, qubit_map) for op in body_ops),
    )


def can_lower_to_bddseqsim(blocks: list) -> bool:
    try:
        lower_to_bddseqsim(blocks)
        return True
    except LoweringError:
        return False


def run_bddseqsim_lowered(
    blocks: list, results: Iterable, precision: int = 3
) -> BDDSeqSimRunResult:
    plan = lower_to_bddseqsim(blocks)
    preset_results = _normalize_results(results, len(plan.external_qubits))
    if not preset_results:
        raise ValueError("At least one preset measurement result is required.")

    setup_start = time.perf_counter()
    num_inputs = len(plan.external_qubits)
    sim = BDDSeqSim(plan.num_qubits, plan.num_qubits - num_inputs, precision)
    sim.init_stored_state_by_basis(0)
    setup_s = time.perf_counter() - setup_start

    sim_start = time.perf_counter()
    for result in preset_results:
        sim.init_input_state_by_basis(0)
        sim.init_comb_bdd()
        for op in plan.body_ops:
            _dispatch_bddseqsim_op(sim, op)
        sim.measure(result)

    sim_s = time.perf_counter() - sim_start
    return BDDSeqSimRunResult(
        probability=sim.prob_list[-1],
        probability_trace=list(sim.prob_list),
        sim_s=sim_s,
        setup_s=setup_s,
        total_s=setup_s + sim_s,
    )


def _flatten_cqc_ops(blocks: list) -> list[GateOp]:
    ops: list[GateOp] = []
    for block in blocks:
        if isinstance(block, CQC):
            ops.extend(block.ops)
        elif isinstance(block, (DQC, SQC)):
            raise LoweringError("Nested control flow is not supported by BDDSeqSim lowering.")
        else:
            raise LoweringError(f"Unsupported IR block type: {type(block).__name__}")
    return ops


def _split_trailing_measurements(ops: list[GateOp]) -> tuple[list[GateOp], list[GateOp]]:
    split_at = len(ops)
    while split_at > 0 and ops[split_at - 1].name == "measure":
        split_at -= 1
    measure_ops = ops[split_at:]
    if not measure_ops:
        raise LoweringError("BDDSeqSim lowering requires trailing body measurements.")
    return ops[:split_at], measure_ops


def _build_qubit_map(num_qubits: int, external_qubits: Sequence[int]) -> dict[int, int]:
    mapping = {}
    for idx, qubit in enumerate(external_qubits):
        mapping[qubit] = idx
    next_idx = len(external_qubits)
    for qubit in range(num_qubits):
        if qubit in mapping:
            continue
        mapping[qubit] = next_idx
        next_idx += 1
    return mapping


def _normalize_results(results: Iterable, width: int) -> list[list[int]]:
    normalized = []
    for result in results:
        if width == 1 and isinstance(result, int):
            normalized.append([result])
        elif isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
            row = [int(bit) for bit in result]
            if len(row) != width:
                raise ValueError(
                    f"Preset result {row} has width {len(row)}, expected {width}."
                )
            normalized.append(row)
        else:
            raise ValueError(
                f"Preset result {result!r} is not valid for {width} external qubits."
            )
    return normalized


def _remap_op(op: GateOp, qubit_map: dict[int, int]) -> GateOp:
    return GateOp(
        op.name,
        [qubit_map[q] for q in op.qubits],
        params=list(op.params),
        c_targets=list(op.c_targets),
        is_final_measure=op.is_final_measure,
    )


def _validate_supported_op(op: GateOp) -> None:
    supported = {
        "x",
        "y",
        "z",
        "h",
        "s",
        "sdg",
        "t",
        "tdg",
        "x2p",
        "y2p",
        "cx",
        "cz",
        "ccx",
        "mcx",
        "cswap",
        "swap",
    }
    if op.name not in supported:
        raise LoweringError(f"Unsupported lowered operation: {op.name}")


def _dispatch_bddseqsim_op(sim: BDDSeqSim, op: GateOp) -> None:
    if op.name == "x":
        sim.X(op.qubits[0])
    elif op.name == "y":
        sim.Y(op.qubits[0])
    elif op.name == "z":
        sim.Z(op.qubits[0])
    elif op.name == "h":
        sim.H(op.qubits[0])
    elif op.name == "s":
        sim.S(op.qubits[0])
    elif op.name == "sdg":
        sim.Z(op.qubits[0])
        sim.S(op.qubits[0])
    elif op.name == "t":
        sim.T(op.qubits[0])
    elif op.name == "tdg":
        sim.Z(op.qubits[0])
        sim.S(op.qubits[0])
        sim.T(op.qubits[0])
    elif op.name == "x2p":
        sim.X2P(op.qubits[0])
    elif op.name == "y2p":
        sim.Y2P(op.qubits[0])
    elif op.name == "cx":
        sim.CNOT(op.qubits[0], op.qubits[1])
    elif op.name == "cz":
        sim.CZ(op.qubits[0], op.qubits[1])
    elif op.name == "ccx":
        sim.Toffoli(op.qubits[0], op.qubits[1], op.qubits[2])
    elif op.name == "mcx":
        sim.multi_controlled_X(op.qubits[:-1], op.qubits[-1])
    elif op.name == "cswap":
        sim.Fredkin(op.qubits[0], op.qubits[1], op.qubits[2])
    elif op.name == "swap":
        sim.SWAP(op.qubits[0], op.qubits[1])
    else:
        raise LoweringError(f"Unsupported lowered operation: {op.name}")
