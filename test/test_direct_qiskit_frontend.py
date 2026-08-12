import math

import numpy as np
import pytest
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import WhileLoopOp
from qiskit.circuit.classical import expr

from qseqsim import (
    CQC,
    DQC,
    OpenQASM3Parser,
    SQC,
    QSeqSimulator,
    QiskitParser,
    QuantumCircuitParser,
    UnsupportedQiskitFeatureError,
)
from qseqsim.benchmark_circuits import build_grover_loop_circuit, build_qrw_loop_circuit
from qseqsim.seqsim_lowering import can_lower_to_bddseqsim, run_bddseqsim_lowered


def _canonical_ir(blocks):
    result = []
    for block in blocks:
        if isinstance(block, CQC):
            result.append(
                (
                    "CQC",
                    tuple(
                        (
                            op.name,
                            tuple(op.qubits),
                            tuple(op.params),
                            tuple(op.c_targets),
                            op.is_final_measure,
                        )
                        for op in block.ops
                    ),
                )
            )
        elif isinstance(block, DQC):
            result.append(
                (
                    "DQC",
                    tuple(block.target_clbits),
                    tuple((value, tuple(_canonical_ir(body))) for value, body in sorted(block.cases.items())),
                    tuple(_canonical_ir(block.default_block)),
                )
            )
        elif isinstance(block, SQC):
            result.append(
                (
                    "SQC",
                    tuple(block.loop_condition["indices"]),
                    block.loop_condition["value"],
                    tuple(_canonical_ir(block.body_block)),
                )
            )
        else:
            raise AssertionError(f"Unknown IR block {type(block).__name__}")
    return tuple(result)


def _normalized_state(simulator):
    raw = np.asarray(
        [simulator.kernel.get_amplitude(i) for i in range(1 << simulator.num_qubits)]
    )
    return raw / math.sqrt(simulator.global_probability)


def _run(blocks, presets):
    simulator = QSeqSimulator(blocks)
    result = simulator.run(
        mode="preset",
        presets={index: list(values) for index, values in presets.items()},
    )
    return simulator, result


def _ordinary_case():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.t(0)
    circuit.cx(0, 1)
    circuit.s(2)
    circuit.cz(1, 2)
    return circuit, {}


def _mid_measurement_case():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    circuit.cx(0, 1)
    return circuit, {0: [1]}


def _if_case():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)) as else_:
        circuit.x(1)
    with else_:
        circuit.z(1)
    return circuit, {0: [1]}


def _register_if_case():
    qreg = QuantumRegister(3, "q")
    creg = ClassicalRegister(2, "c")
    circuit = QuantumCircuit(qreg, creg)
    circuit.x(qreg[1])
    circuit.measure(qreg[0], creg[0])
    circuit.measure(qreg[1], creg[1])
    with circuit.if_test((creg, 2)):
        circuit.x(qreg[2])
    return circuit, {0: [0], 1: [1]}


def _while_case():
    circuit = QuantumCircuit(2, 1)
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.x(1)
        circuit.h(0)
        circuit.measure(0, 0)
    return circuit, {0: [0, 1]}


def _if_in_while_case():
    circuit = QuantumCircuit(3, 2)
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.h(0)
        circuit.measure(0, 1)
        with circuit.if_test((circuit.clbits[1], 0)) as else_:
            circuit.x(1)
        with else_:
            circuit.z(1)
        circuit.h(2)
        circuit.measure(2, 0)
    return circuit, {1: [0], 0: [1]}


@pytest.mark.parametrize(
    "case_builder",
    [
        _ordinary_case,
        _mid_measurement_case,
        _if_case,
        _register_if_case,
        _while_case,
        _if_in_while_case,
    ],
    ids=[
        "ordinary",
        "mid-measurement",
        "if-clbit",
        "if-register",
        "measurement-while",
        "if-in-while",
    ],
)
def test_direct_and_qasm_frontends_are_semantically_equivalent(case_builder):
    circuit, presets = case_builder()
    direct_blocks = QuantumCircuitParser(circuit).parse()
    qasm_blocks = QiskitParser(circuit).parse()

    assert _canonical_ir(direct_blocks) == _canonical_ir(qasm_blocks)

    direct_simulator, direct_result = _run(direct_blocks, presets)
    qasm_simulator, qasm_result = _run(qasm_blocks, presets)
    assert direct_result == qasm_result
    assert direct_simulator.global_probability == pytest.approx(qasm_simulator.global_probability)
    assert np.allclose(_normalized_state(direct_simulator), _normalized_state(qasm_simulator), atol=1e-12)


def test_direct_path_never_calls_qasm_serialization_or_parser(monkeypatch):
    import openqasm3
    import qiskit.qasm3

    circuit = QuantumCircuit(1)
    circuit.x(0)

    def forbidden(*args, **kwargs):
        raise AssertionError("OpenQASM path was called")

    monkeypatch.setattr(qiskit.qasm3, "dumps", forbidden)
    monkeypatch.setattr(openqasm3, "parse", forbidden)

    assert _canonical_ir(QuantumCircuitParser(circuit).parse())
    simulator = QSeqSimulator(circuit)
    simulator.run()
    assert simulator.kernel.get_amplitude(1) == 1

    second = QSeqSimulator()
    second.run(circuit)
    assert second.kernel.get_amplitude(1) == 1


def test_control_flow_block_operands_map_positionally_to_outer_bits():
    body = QuantumCircuit(2, 2)
    body.x(0)
    body.cx(0, 1)
    body.measure(1, body.clbits[0])
    operation = WhileLoopOp((body.clbits[0], 0), body)

    circuit = QuantumCircuit(3, 3)
    circuit.append(
        operation,
        [circuit.qubits[2], circuit.qubits[0]],
        [circuit.clbits[2], circuit.clbits[1]],
    )

    blocks = QuantumCircuitParser(circuit).parse()
    loop = blocks[0]
    assert isinstance(loop, SQC)
    assert loop.loop_condition == {"indices": [2], "value": 0}
    assert loop.external_qubits == {0}
    assert _canonical_ir(loop.body_block) == (
        (
            "CQC",
            (
                ("x", (2,), (), (), False),
                ("cx", (2, 0), (), (), False),
                ("measure", (0,), (), (2,), False),
            ),
        ),
    )

    simulator, result = _run(blocks, {2: [1]})
    assert result == {2: 1}
    assert simulator.global_probability == 1.0
    assert np.argmax(np.abs(_normalized_state(simulator))) == 5


def test_for_loop_is_unrolled_and_binds_loop_parameter():
    circuit = QuantumCircuit(1)
    with circuit.for_loop([1, 2]) as index:
        circuit.rz(index * math.pi / 4, 0)

    blocks = QuantumCircuitParser(circuit).parse()

    assert _canonical_ir(blocks) == (
        ("CQC", (("t", (0,), (), (), False),)),
        ("CQC", (("s", (0,), (), (), False),)),
    )


def test_public_api_keeps_existing_ir_and_qasm_parser_compatibility():
    circuit = QuantumCircuit(1)
    circuit.x(0)
    legacy_blocks = QiskitParser(circuit).parse()

    direct = QSeqSimulator.from_circuit(circuit)
    legacy = QSeqSimulator(legacy_blocks)
    direct.run()
    legacy.run()

    assert direct.kernel.get_amplitude(1) == legacy.kernel.get_amplitude(1) == 1

    qasm_blocks = OpenQASM3Parser(
        qasm_str='OPENQASM 3.0; include "stdgates.inc"; qubit[1] q; x q[0];'
    ).parse()
    qasm_simulator = QSeqSimulator(qasm_blocks)
    qasm_simulator.run()
    assert qasm_simulator.kernel.get_amplitude(1) == 1


@pytest.mark.parametrize(
    ("circuit", "preset_path", "expected_trace"),
    [
        (build_qrw_loop_circuit(4), [0, 1], [0.5, 0.0]),
        (build_grover_loop_circuit(4), [0, 1], [0.5, 0.25]),
    ],
    ids=["fm-qrw", "fm-grover"],
)
def test_fm_qiskit_circuits_use_direct_frontend_and_existing_lowering(
    circuit, preset_path, expected_trace
):
    blocks = QuantumCircuitParser(circuit).parse()

    assert can_lower_to_bddseqsim(blocks)
    assert run_bddseqsim_lowered(blocks, preset_path).probability_trace == expected_trace


@pytest.mark.parametrize(
    ("circuit_builder", "message"),
    [
        (
            lambda: _switch_circuit(),
            r"SwitchCaseOp.*op 'switch_case'",
        ),
        (
            lambda: _break_circuit(),
            r"BreakLoopOp.*op 'break_loop'",
        ),
        (
            lambda: _continue_circuit(),
            r"ContinueLoopOp.*op 'continue_loop'",
        ),
        (
            lambda: _classical_expression_circuit(),
            r"classical expression condition.*IfElseOp",
        ),
        (
            lambda: _dynamic_variable_circuit(),
            r"dynamic variables.*QuantumCircuit",
        ),
        (
            lambda: _reset_circuit(),
            r"Reset.*op 'reset'",
        ),
        (
            lambda: _global_phase_circuit(),
            r"nonzero global_phase.*0\.25",
        ),
    ],
    ids=[
        "switch",
        "break",
        "continue",
        "classical-expression",
        "dynamic-variable-store",
        "unknown-op",
        "global-phase",
    ],
)
def test_unsupported_qiskit_features_fail_explicitly(circuit_builder, message):
    with pytest.raises(UnsupportedQiskitFeatureError, match=message):
        QuantumCircuitParser(circuit_builder()).parse()


def _switch_circuit():
    circuit = QuantumCircuit(1, 1)
    with circuit.switch(circuit.clbits[0]) as case:
        with case(0):
            circuit.x(0)
    return circuit


def _break_circuit():
    circuit = QuantumCircuit(1, 1)
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.break_loop()
    return circuit


def _continue_circuit():
    circuit = QuantumCircuit(1, 1)
    with circuit.while_loop((circuit.clbits[0], 0)):
        circuit.continue_loop()
    return circuit


def _classical_expression_circuit():
    circuit = QuantumCircuit(1, 1)
    with circuit.if_test(expr.equal(circuit.clbits[0], True)):
        circuit.x(0)
    return circuit


def _dynamic_variable_circuit():
    circuit = QuantumCircuit(1)
    variable = circuit.add_var("dynamic", False)
    circuit.store(variable, True)
    return circuit


def _reset_circuit():
    circuit = QuantumCircuit(1)
    circuit.reset(0)
    return circuit


def _global_phase_circuit():
    circuit = QuantumCircuit(1, global_phase=0.25)
    circuit.x(0)
    return circuit
