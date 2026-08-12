# CP5 native SamplerV2 integration gate

## Architecture

CP5 adds a native Qiskit Primitive V2 layer without wrapping the backend or
copying the symbolic executor:

```text
SamplerPub.coerce
  -> BindingsArray.bind_all
  -> one bound QuantumCircuit
  -> shared CP3 direct frontend
  -> shared CP4 symbolic branch distribution
  -> shared seeded shot sampler
  -> per-register BitArray fields in DataBin
  -> SamplerPubResult / PrimitiveResult / QSeqPrimitiveJob
```

`QSeqSamplerV2` is a `BaseSamplerV2`, and `QSeqPrimitiveJob` is a
`BasePrimitiveJob[PrimitiveResult[SamplerPubResult], JobStatus]` backed by one
local worker future. Failures are raised by `job.result()` and produce
`JobStatus.ERROR`. The compatibility alias `QSeqSampler` names the same V2
class; it is not a SamplerV1 implementation.

## PUBs, parameters, shots, and RNG

`run()` delegates all bare-circuit, tuple, and pre-built PUB normalization to
Qiskit 2.4.2's public `SamplerPub.coerce()`. This supports:

```python
sampler.run([circuit])
sampler.run([(circuit, parameter_values)])
sampler.run([(circuit, parameter_values, pub_shots)])
```

`BindingsArray.bind_all()` preserves the official parameter-array shape. Every
bound circuit is parsed and symbolically executed exactly once, independent of
its shot count. Parameters must bind into the direct frontend's supported
discrete gate domain. For-loop-local parameters remain scoped to
`ForLoopOp` and are bound during CP3 finite unrolling; they are not mistaken
for PUB parameters. Unsupported bound angles raise
`UnsupportedQiskitFeatureError`; Qiskit binding/coercion errors propagate.

PUB shots override run-level shots, run-level shots override
`default_shots`, and `shots=None` selects `default_shots` (1024 by default), as
required by `BaseSamplerV2`. It never requests exact probabilities. A job uses
one `random.Random` stream, initialized from the sampler's `seed`, and advances
it continuously in PUB order and then NumPy parameter-index order. Repeating a
job with the same integer seed and identical PUBs reproduces all shot arrays,
while separate PUBs do not restart the stream.

## Result and register semantics

The complete symbolic result uses global Qiskit classical-bit indices, with
global `clbit[0]` as the least-significant bit. CP5 projects every sampled
integer onto each `ClassicalRegister`; within a register, `creg[0]` is again the
least-significant bit. `DataBin` fields follow `circuit.cregs` order and each
field is a real Qiskit `BitArray` with the PUB parameter shape, requested shot
count, and register width.

This is deliberately different from the legacy `Result.get_counts()` display:
BackendV2 formats register groups in reverse display order and separates them
with spaces. For registers created as `low` then `high`, the primitive exposes
`data.low` then `data.high`, while Backend counts display `high low`. Tests lock
both views and compare the primitive's `join_data()` behavior directly with
Qiskit 2.4.2 `StatevectorSampler`.

A circuit with no classical registers emits the same warning style as Qiskit's
reference sampler and returns an empty `DataBin`. Existing but unmeasured
register bits are zero; QSeqSim does not insert measurements.

## Relationship to BackendV2 and failure semantics

`QSeqSimBackend` and `QSeqSamplerV2` both call the same two internal adapters:
one direct symbolic distribution execution and one ordered distribution-to-shot
sampler. The primitive does not call `backend.run()`, does not serialize QASM,
does not invoke native single-path `QSeqSimulator.run()`, and does not execute
once per shot.

Unsupported frontend features, exact symbolic evaluation failures, loop guards,
and parameter-binding failures are not converted into successful result
objects. `UnsupportedQiskitFeatureError`, `SymbolicEvaluationError`, and the
original Qiskit binding exceptions remain visible from `job.result()`.

## Scope

CP5 adds no EstimatorV2, PyPI upload, ecosystem submission, release automation,
or release metadata changes. The FM tag and branches remain at `67ae057`.

## Validation

Validated on Python 3.12.3 with Qiskit 2.4.2 and canonical `dd.cudd` 0.6.0:

- full test suite: 69 passed;
- 30 focused BackendV2/SamplerV2 tests passed, including PUB coercion,
  parameter arrays, loop-parameter scope, dynamic circuits, multi-register
  `BitArray` fields, failures, seeding, and one-distribution-call guarantees;
- deterministic and fixed-seed Bell counts matched `QSeqSimBackend` exactly;
- multi-register fields and `join_data()` matched Qiskit 2.4.2's reference
  `StatevectorSampler` on a compatible deterministic circuit;
- wheel and sdist built successfully and both passed `twine check`;
- a fresh repository-external wheel environment passed SamplerV2 parameter and
  Bell execution, BackendV2 transpile/counts, and raw OpenQASM compatibility
  smoke tests after installing the required CUDD-enabled `dd` build;
- AE smoke Table 1, Table 2a, Table 2b, Table 3, Table 4, and Table 5 all
  completed successfully.
