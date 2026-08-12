# CP3 direct Qiskit frontend gate

## Architecture

CP3 adds a direct lowering path:

```text
QuantumCircuit.data
  -> QuantumCircuitParser
  -> GateOp / CQC / DQC / SQC
  -> QSeqSimulator / existing BDD kernel
```

`QuantumCircuitParser` imports neither the OpenQASM exporter nor the OpenQASM
parser. The compatibility path remains separate:

```text
QuantumCircuit or OpenQASM 3 text
  -> OpenQASM3Parser (compatibility name: QiskitParser)
  -> GateOp / CQC / DQC / SQC
```

The shared `mark_final_measurements` IR pass preserves the existing distinction
between readout and state-collapsing measurements.

## Bit mapping invariant

Every parser recursion has a bit frame from bit objects in the current Qiskit
circuit to global QSeqSim integer indices. At a `ControlFlowOp` instruction:

1. map the instruction's outer `qubits` and `clbits` through the current frame;
2. positionally pair those global indices with each inner block's ordered
   `qubits` and `clbits`;
3. parse block operations and tuple-condition targets through that new frame.

Consequently, a block-local index is never assumed to equal an outer/global
index. Regression coverage includes a two-qubit/two-clbit while body appended
to reordered outer operands `[q2, q0]` and `[c2, c1]`.

## Control-flow decisions

- `IfElseOp` lowers to one `DQC` case and a default block.
- `WhileLoopOp` lowers to `SQC` and retains the existing validation and
  1000-iteration execution guard.
- finite `ForLoopOp` is expanded by the frontend because the existing IR has no
  counted-loop node. Its loop parameter is bound independently for each body
  copy before parsing.
- `SwitchCaseOp`, `BreakLoopOp`, `ContinueLoopOp`, classical-expression
  conditions, dynamic variables/`Store`, and unknown operations raise the
  public `UnsupportedQiskitFeatureError`. No heuristic or partial execution is
  attempted.
- nonzero or symbolic circuit `global_phase` is also rejected because silently
  discarding it would change the public amplitude state even though measurement
  probabilities are invariant.

The complete operation table is maintained in [USER_GUIDE.md](USER_GUIDE.md).

## Public API and compatibility

Recommended forms:

```python
QSeqSimulator(qc).run()
QSeqSimulator().run(qc)
QSeqSimulator.from_circuit(qc).run()
QuantumCircuitParser(qc).parse()
```

The CP2 contract remains valid:

```python
QSeqSimulator(parsed_blocks).run()
QiskitParser(qc).parse()  # existing QASM-mediated behavior
```

Raw interchange input has the clearer spelling
`OpenQASM3Parser(qasm_str=text).parse()`.

## Differential coverage and known differences

Direct and QASM3 paths are compared structurally where stable and then executed
with identical presets. Coverage includes ordinary gates, mid-circuit
measurement, `if`, measurement-driven `while`, nested `if` inside `while`, and
cross-iteration state retention/composition. The FM QRW and Grover Qiskit
builders also enter through the direct parser and continue through the existing
specialized lowering.

No execution-semantic differences were observed in the shared tested subset.
Two intentional representation/frontend differences remain:

- direct finite `ForLoopOp` expansion can leave adjacent `CQC` blocks separate,
  while the QASM parser may combine the same gates into one buffer;
- direct parameter binding correctly resolves a loop parameter per iteration;
  the compatibility QASM parser should not be treated as a reference for
  parameterized loop-body expressions beyond its documented subset.

## Preserved CP2.5 boundaries

CP3 does not change `SymbolicEvaluationError`, the binary64 public probability
contract, the 1000-iteration guard, specialized lowering restrictions, or the
canonical `dd.cudd` backend. It adds no BackendV2, SamplerV2, or release code.

## Validation

Validated on Python 3.13.9 with Qiskit 2.4.1 and `dd.cudd` 0.6.0:

- full pytest suite: 39 passed;
- direct/QASM differential suite: identical stable IR and identical executed
  probabilities, classical stores, and normalized states for all shared cases;
- wheel and sdist: built successfully;
- `twine check`: passed for both distributions;
- fresh external wheel environment: import, direct constructor, deferred
  `run(qc)`, execution, and raw OpenQASM compatibility passed;
- AE smoke: Table 1, Table 2a, Table 2b, Table 3, Table 4, and Table 5 all
  completed successfully.
