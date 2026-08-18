# Qiskit integration

QSeqSim provides three Qiskit-facing execution layers over one symbolic engine:

```text
QuantumCircuit
  -> QuantumCircuitParser
  -> GateOp / CQC / DQC / SQC
  -> BDD-backed symbolic execution
  -> native state/path results, BackendV2 Result, or SamplerV2 PrimitiveResult
```

The direct parser does not serialize through OpenQASM. `OpenQASM3Parser` remains
available as a secondary interchange frontend, and `QiskitParser` is its
compatibility alias. Both frontends feed the same internal IR.

## Direct `QuantumCircuit` frontend

Every parser recursion carries a mapping from the bit objects in the current
Qiskit circuit to global QSeqSim integer indices. At a `ControlFlowOp`, the
outer instruction operands are mapped through the current frame and paired
positionally with each inner block's ordered qubits and classical bits. A
block-local index is therefore never assumed to equal an outer index.

The direct frontend lowers supported control flow as follows:

- `IfElseOp` becomes a `DQC` case and optional default block.
- `WhileLoopOp` becomes `SQC`, retaining the loop-body validation and the
  1000-iteration safety limit.
- finite `ForLoopOp` is unrolled because the current IR has no counted-loop
  node. Its loop parameter is bound independently for each body copy.
- `SwitchCaseOp`, `BreakLoopOp`, `ContinueLoopOp`, classical-expression
  conditions, dynamic variables, `Store`, and unknown operations raise
  `UnsupportedQiskitFeatureError`.
- a nonzero or symbolic circuit `global_phase` is rejected because discarding
  it would change the public amplitude state.

The shared `mark_final_measurements` pass distinguishes readout measurements
from measurements that collapse state during execution. The complete operation
matrix is maintained in [USER_GUIDE.md](USER_GUIDE.md).

Recommended entry points are:

```python
QSeqSimulator(qc).run()
QSeqSimulator().run(qc)
QSeqSimulator.from_circuit(qc).run()
QuantumCircuitParser(qc).parse()
```

Existing parsed-block and OpenQASM forms remain supported:

```python
QSeqSimulator(parsed_blocks).run()
QiskitParser(qc).parse()
OpenQASM3Parser(qasm_str=qasm_text).parse()
```

Direct and OpenQASM paths have differential coverage for ordinary operations,
mid-circuit measurement, conditional branches, measurement-driven loops,
nested supported control flow, and cross-iteration state retention. Direct
finite-loop expansion may preserve adjacent `CQC` blocks that the OpenQASM
parser combines; this representation difference does not change execution.

## BackendV2

`QSeqSimBackend` is an ideal all-to-all `BackendV2` simulator target. It does
not claim physical durations, error rates, calibrations, pulse data, or qubit
properties. The default target contains 256 qubits and can be configured with
`QSeqSimBackend(num_qubits=...)`.

Advertised fixed-domain operations are:

```text
x y z h s sdg t tdg cx cz swap ccx cswap measure
```

`MCXGate` is declared as the variable-width `mcx` operation. `IfElseOp`,
`WhileLoopOp`, and `ForLoopOp` are declared by class. The direct frontend's
discrete rotation subset is intentionally not advertised as unrestricted
parameterized target instructions.

Backend execution computes the complete symbolic classical distribution once
per input circuit. At each measurement it forks independent CUDD-backed states,
collapses every nonzero branch, continues dynamic control flow, and aggregates
equal final classical stores. This preserves correlations such as Bell `00/11`.
Shot count does not change the number of symbolic circuit executions.

One seeded RNG samples the resulting probability map. Counts and optional
memory use Qiskit's hexadecimal raw schema; `Result.get_counts()` and
`Result.get_memory()` apply Qiskit's classical-register formatting. Supported
runtime options are:

- `shots=1024`, which must be a positive integer;
- `memory=False`, which must be a boolean; and
- `seed_simulator=None`, which accepts an integer or `None`.

The returned `QSeqSimJob` is synchronous and already complete. Parser,
unsupported-feature, loop-limit, and symbolic-evaluation errors propagate from
`run()` instead of being encoded as successful results.

## SamplerV2

`QSeqSamplerV2` implements `BaseSamplerV2`; `QSeqPrimitiveJob` implements the
corresponding primitive job interface. `QSeqSampler` is a compatibility alias
for the same V2 class, not a SamplerV1 implementation.

`run()` delegates PUB normalization to Qiskit's `SamplerPub.coerce()` and
supports bare circuits, `(circuit, parameter_values)`, and
`(circuit, parameter_values, pub_shots)` tuples. `BindingsArray.bind_all()`
preserves the parameter-array shape. Every bound circuit is parsed and
symbolically executed exactly once, independently of its shot count.

PUB shots override run-level shots; run-level shots override `default_shots`.
`shots=None` selects the default and does not request exact probabilities. A
single seeded RNG stream advances in PUB order and then NumPy parameter-index
order, so identical jobs with the same integer seed are reproducible without
restarting the stream for each PUB.

The symbolic outcome uses global classical-bit index 0 as the least-significant
bit. Sampled integers are projected onto each `ClassicalRegister`, again with
register bit 0 least significant. `DataBin` fields follow `circuit.cregs` order
and contain real Qiskit `BitArray` values with the PUB shape, shot count, and
register width.

Backend count strings display register groups in reverse order and separate
them with spaces, while primitive fields retain `circuit.cregs` order. Compare
the two interfaces semantically rather than by concatenating field strings.
Circuits without classical registers return an empty `DataBin` and a warning;
QSeqSim does not insert measurements.

The sampler and backend share the same distribution executor and ordered
shot-sampling adapter. The sampler does not call `backend.run()`, serialize
OpenQASM, or execute the simulator once per shot. Asynchronous primitive
failures appear from `job.result()` and set the job state to `ERROR`.

## Preserved semantic boundaries

The Qiskit-facing layers preserve the public binary64 probability contract,
the required `dd.cudd` backend, the 1000-iteration loop limit, and the
specialized sequential-lowering restrictions described in
[CORRECTNESS_NOTES.md](CORRECTNESS_NOTES.md). Expanded frontend syntax must not
be inferred to expand the BDD kernel or specialized lowering automatically.
