# Qiskit Ecosystem submission readiness

This is an internal draft prepared on **2026-08-12**. It does not submit an
issue or pull request. Criteria and fields were checked against the official
Qiskit Ecosystem repository at commit
`1f0ccd4ed4f8aed1f8369c7be99bb62c88f317e5` (2026-08-12).

## Current criteria checklist

| Official criterion | Status | Evidence / remaining action |
| --- | --- | --- |
| Meaningfully builds on, interfaces with, or extends Qiskit | Ready | Direct `QuantumCircuit`/`ControlFlowOp` frontend, `BackendV2`, `Target`, `JobV1`, Qiskit `Result`, and native SamplerV2 types |
| Compatible with Qiskit SDK 2.0 or newer | Ready | Package range is `qiskit>=2.4,<2.5`; release gate covers Qiskit 2.4.x |
| OSI-approved license | Ready | Apache-2.0 `LICENSE` and package metadata |
| Adheres to Qiskit Code of Conduct | Ready | Repository `CODE_OF_CONDUCT.md` adopts and links the Qiskit Code of Conduct |
| Maintainer activity within the last six months | Ready locally | CP6 has current commits; they must be pushed before submission so the public repository shows the activity |
| New projects compatible with V2 primitives | Ready | `QSeqSamplerV2` is a native `BaseSamplerV2` returning Qiskit `PrimitiveResult`, `SamplerPubResult`, `DataBin`, and `BitArray`; EstimatorV2 is outside simulator scope and is not claimed |

The official issue form does not require a published package URL, but QSeqSim's
planned submission should wait until `qseqsim` v0.1.0 is published so the
optional package field is useful and verifiable.

## Submission metadata draft

| Field | Draft value |
| --- | --- |
| Project name | `QSeqSim` (default) or `Veri-Q QSeqSim` after maintainer decision |
| Description (97 characters) | `BDD/WMC simulator for dynamic and sequential Qiskit circuits with BackendV2 and native SamplerV2.` |
| Contact email | `lizh@ios.ac.cn` |
| Category | `Circuit simulator` |
| Labels | `quantum information`, `research`, `openqasm`, `benchmarking` |
| Interface/API | `Python` |
| Maturity | `experimental` |
| GitHub repository | `https://github.com/veriq-toolkit/QSeqSim` |
| Home page | Leave empty until the team supplies and verifies a dedicated URL |
| Documentation | `https://github.com/veriq-toolkit/QSeqSim/tree/main/docs` after release commits reach the default branch |
| Package | `https://pypi.org/project/qseqsim/` after publication |
| Reference paper | `https://doi.org/10.1007/978-3-032-26204-2_30` |
| Code of Conduct | Agree to follow the Qiskit Code of Conduct |

Alternate description (97 characters):

> Structure-aware BDD simulator for measurement-driven Qiskit control flow and sequential circuits.

Both descriptions are below the form's 135-character limit. The default name is
the established software name; `Veri-Q QSeqSim` is a display-only alternative
and would not change the `qseqsim` distribution or import namespace.

## Maintenance commitment draft

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

## Submission blockers

1. Push/merge the CP6 release-readiness commits so CI and maintainer activity
   are public.
2. Complete the authorized release staging, change versions to `0.1.0`, and
   publish the package before filling the package URL.
3. Choose `QSeqSim` or `Veri-Q QSeqSim` as the display name.
4. Confirm whether the GitHub docs path is sufficient or supply a verified
   project documentation/homepage URL.
5. Submit the official issue form only after explicit maintainer authorization.

No Ecosystem issue or pull request is created by CP6.
