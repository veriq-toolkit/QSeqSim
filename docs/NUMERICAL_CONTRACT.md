# Public numerical contract

QSeqSim v0.1.0 uses Python `float` (IEEE 754 binary64) for every public
probability result. This includes `BDDCombSim.get_prob()`,
`QSeqSimulator.global_probability`, sequential probability traces, specialized
lowering results, and the probability maps used internally by the Qiskit
sampling adapters.

The symbolic calculation before that boundary is stronger than the result
type:

- model counts are accumulated as arbitrary-size Python integers;
- algebraic terms are combined using a 150-digit `Decimal` context;
- algebraic zero is detected with integer arithmetic before conversion; and
- branch and model-count semantics are preserved symbolically before the final
  numerical conversion.

These implementation properties do **not** make the public API arbitrary
precision. The final `Decimal` value is converted to binary64, so users should
expect about 16 significant decimal digits. `2**-1074` is the smallest positive
public result (`5e-324` as printed by Python), while `2**-1075` rounds to zero.
Repeated multiplication into `global_probability` has the same underflow
boundary and the usual binary64 rounding behavior.

This boundary does not alter BackendV2 or SamplerV2 shot semantics. Those APIs
first execute the complete symbolic branch distribution, then draw seeded
samples from the resulting binary64-normalized distribution. Counts and memory
remain sampled observations rather than public arbitrary-precision probability
objects.

No separate `Decimal` probability API is part of v0.1.0. Adding one safely
would require an end-to-end contract for normalization, path accumulation,
distribution aggregation, serialization, and compatibility with existing
callers; exposing only one intermediate value would create two inconsistent
public result models.

