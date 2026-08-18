# Packaging and migration

CP2 changes the installable library layout without changing the FM simulation
semantics.

## Supported package imports

New code should use the stable top-level API:

```python
from qseqsim import QSeqSimulator, QuantumCircuitParser, OpenQASM3Parser
```

Advanced modules are available under `qseqsim.kernel`, `qseqsim.parser`,
`qseqsim.seqsim_lowering`, and `qseqsim.simulator`, but the top-level names are
the preferred compatibility surface.

`QSeqSimulator` accepts a `QuantumCircuit` directly, parsed blocks exactly as
`BDDSimulator` does, or no initial program followed by `run(qc)`. Direct inputs
use `QuantumCircuitParser` and never call `qiskit.qasm3.dumps`.

`OpenQASM3Parser` is the secondary interchange frontend. `QiskitParser` remains
an alias for that existing implementation so CP2 callers keep identical input
semantics. It has not been silently repurposed as the direct parser.

Migration examples:

```python
# Recommended CP3 path
result = QSeqSimulator(qc).run()

# CP2-compatible path (still OpenQASM-mediated)
result = QSeqSimulator(QiskitParser(qc).parse()).run()

# Raw OpenQASM 3 interchange
blocks = OpenQASM3Parser(qasm_str=qasm_text).parse()
```

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
- Qiskit: `>=2.4,<3` (Qiskit 2.x from 2.4 onward; Qiskit 3 is not supported)
- OpenQASM 3 parser: `>=1.0,<1.1`

The `dd` version constraint alone cannot guarantee that its native CUDD
extension was built. Importing QSeqSim therefore verifies `dd.cudd` immediately
and raises a clear error instead of falling back to `dd.autoref`.
