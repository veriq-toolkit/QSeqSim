# Packaging and migration

CP2 changes the installable library layout without changing the FM simulation
semantics.

## Supported package imports

New code should use the stable top-level API:

```python
from qseqsim import QSeqSimulator, QiskitParser
```

Advanced modules are available under `qseqsim.kernel`, `qseqsim.parser`,
`qseqsim.seqsim_lowering`, and `qseqsim.simulator`, but the top-level names are
the preferred compatibility surface.

`QSeqSimulator` currently accepts parsed blocks, exactly as `BDDSimulator` does.
It does not implement the planned direct Qiskit frontend.

## FM research checkout compatibility

Existing examples, experiments, AE tools, and tests still import paths such as:

```python
from src.parser import QiskitParser
from src.simulator import BDDSimulator
```

Those repository-local modules remain as thin forwarding shims. They are kept
for running the FM artifact from a source checkout and are not part of the
installed wheel's public API. The immutable `fm-artifact-2026` tag remains the
authoritative original artifact.

## Dependency policy

- Python: `>=3.12,<3.14` (3.12 and 3.13 only)
- `dd`: `>=0.6,<0.7`
- Qiskit: `>=2.2,<2.5`
- OpenQASM 3 parser: `>=1.0,<1.1`

The `dd` version constraint alone cannot guarantee that its native CUDD
extension was built. Importing QSeqSim therefore verifies `dd.cudd` immediately
and raises a clear error instead of falling back to `dd.autoref`.
