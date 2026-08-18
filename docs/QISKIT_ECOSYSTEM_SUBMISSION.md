# Qiskit Ecosystem membership record

This record was originally prepared on **2026-08-12** for the submission and
was updated after acceptance. **Veri-Q QSeqSim is now part of the Qiskit
Ecosystem.** The canonical membership page is
<https://qiskit.github.io/ecosystem/p/b7361201/>.

## Acceptance criteria record

| Official criterion | Status | Evidence / remaining action |
| --- | --- | --- |
| Meaningfully builds on, interfaces with, or extends Qiskit | Ready | Direct `QuantumCircuit`/`ControlFlowOp` frontend, `BackendV2`, `Target`, `JobV1`, Qiskit `Result`, and native SamplerV2 types |
| Compatible with Qiskit SDK 2.0 or newer | Ready | Package range is `qiskit>=2.4,<3`; CI pins the 2.4.2 lower bound and tracks the latest supported 2.x release |
| OSI-approved license | Ready | Apache-2.0 `LICENSE` and package metadata |
| Adheres to Qiskit Code of Conduct | Ready | Repository `CODE_OF_CONDUCT.md` adopts and links the Qiskit Code of Conduct |
| Maintainer activity within the last six months | Accepted | The public repository and v0.1.0 release show current maintainer activity |
| New projects compatible with V2 primitives | Ready | `QSeqSamplerV2` is a native `BaseSamplerV2` returning Qiskit `PrimitiveResult`, `SamplerPubResult`, `DataBin`, and `BitArray`; EstimatorV2 is outside simulator scope and is not claimed |

The official record links the published `qseqsim` v0.1.0 package and currently
reports that all membership checkups pass.

## Published registry metadata

| Field | Published value |
| --- | --- |
| Project name | `Veri-Q QSeqSim` |
| Description (97 characters) | `BDD/WMC simulator for dynamic and sequential Qiskit circuits with BackendV2 and native SamplerV2.` |
| Contact email | `lizh@ios.ac.cn` |
| Category | `Circuit simulator` |
| Labels | `quantum information`, `research`, `openqasm`, `benchmarking` |
| Interface/API | `Python` |
| Maturity | `experimental` |
| GitHub repository | `https://github.com/veriq-toolkit/QSeqSim` |
| Home page | `https://www.veri-q.com/` |
| Documentation | `https://github.com/veriq-toolkit/QSeqSim/blob/main/docs/USER_GUIDE.md` |
| Package | `https://pypi.org/project/qseqsim/` |
| Reference paper | `https://doi.org/10.1007/978-3-032-26204-2_30` |
| Code of Conduct | Agree to follow the Qiskit Code of Conduct |

Alternate description (97 characters):

> Structure-aware BDD simulator for measurement-driven Qiskit control flow and sequential circuits.

Both descriptions are below the form's 135-character limit. `Veri-Q QSeqSim`
is the display name and does not change the `qseqsim` distribution or import
namespace.

## Maintenance commitment

QSeqSim will be maintained as an experimental research simulator. Maintainers
will triage correctness and compatibility issues, keep supported Qiskit 2.x and
Python versions tested, review dependency/security updates, and label breaking
changes. Experimental maturity means APIs may still evolve; it does not mean
the repository is an unmaintained paper snapshot.

## Position relative to `symbolic-qiskit`

The comparison was checked against `symbolic-qiskit` commit
`8d8e9a801fbc35054350418ff6adcd273c082443` and its Ecosystem record. The
projects are complementary:

| Dimension | `symbolic-qiskit` | QSeqSim |
| --- | --- | --- |
| Primary representation | SymPy symbolic matrices and expressions | BDD-backed state with weighted model counting |
| Primary user workflow | `CircuitInspector` queries symbolic statevectors, unitaries, and measurement branches at barriers | Executable native simulator, BackendV2 jobs/results, and native SamplerV2 PUBs |
| Parameter emphasis | Symbolic gate parameters and expression inspection | Bound circuits in the supported discrete Clifford+T/angle domain |
| Measurement | Symbolic post-measurement branches and state inspection | Complete classical branch distribution followed by seeded shot sampling |
| Sequential control | No dynamic `ControlFlowOp` execution is documented in the audited version | Direct tested `if_test`, measurement-driven `while_loop`, finite `for_loop`, state retention, and feedback semantics |
| Evidence regime | Symbolic state/expression inspection | FM structured QRW/Grover artifact plus current Aer/Qiskit integration benchmark |

QSeqSim should therefore be described as a BDD/WMC simulator for
measurement-driven sequential execution and Qiskit execution interfaces, not
merely as another generic symbolic simulator. It should not claim superiority
for symbolic parameter algebra, broad gate coverage, or all circuit workloads.

## Post-acceptance status

- Membership is accepted and the official project page reports **All good**.
- The v0.1.0 package is published as `qseqsim` without changing the public
  project name, homepage, or repository ownership.
- Qiskit 2.5.1 compatibility has been validated and is recorded in
  [QISKIT_2_5_COMPATIBILITY_CHECKLIST.md](QISKIT_2_5_COMPATIBILITY_CHECKLIST.md).
  The source dependency range is `qiskit>=2.4,<3`; Qiskit 3 is not included.
