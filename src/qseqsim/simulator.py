import random
import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from .exceptions import SymbolicEvaluationError
from .kernel import BDDCombSim
from .parser import CQC, DQC, SQC, GateOp


@dataclass
class _DistributionState:
    kernel: BDDCombSim
    clbits: Dict[int, int]
    probability: float
    break_requested: bool = False

class BDDSimulator:
    def __init__(self, parsed_blocks: list, precision: int = 32):
        self.blocks = parsed_blocks
        self.precision = precision
        if not self.blocks:
            self.num_qubits = 0
        else:
            self.num_qubits = self.blocks[0].global_num_qubits

        self.kernel = BDDCombSim(self.num_qubits, precision)
        if hasattr(self.kernel, 'init_basis_state'):
            self.kernel.init_basis_state(0)

        self.clbit_store: Dict[int, int] = {}
        self.mode = 'sample'
        self.presets: Dict[int, List[int]] = {}

        # Global cumulative probability (for normalization)
        self.global_probability = 1.0

        self.GATE_METHOD_MAP = {
            'x': 'X', 'y': 'Y', 'z': 'Z', 'h': 'H', 's': 'S', 't': 'T',
            'sdg': 'SDG', 'tdg': 'TDG', 'x2p': 'X2P', 'y2p': 'Y2P',
            'cx': 'CNOT', 'cz': 'CZ', 'swap': 'SWAP', 'ccx': 'Toffoli', 'cswap': 'Fredkin'
        }

    def run(self, mode: str = 'sample', presets: Optional[Dict[int, List[int]]] = None):
        self.mode = mode
        self.presets = {
            clbit: list(outcomes) for clbit, outcomes in (presets or {}).items()
        }
        self.clbit_store.clear()
        self.global_probability = 1.0 # Reset probability
        self.kernel = BDDCombSim(self.num_qubits, self.precision)
        if hasattr(self.kernel, 'init_basis_state'):
            self.kernel.init_basis_state(0)

        print(f"\n[Sim] Starting Simulation (Mode: {self.mode}, Qubits: {self.num_qubits})...")
        try:
            self._execute_blocks(self.blocks)
            print("[Sim] Simulation Finished Successfully.")
        except Exception as e:
            print(f"[Sim] Simulation Failed: {e}")
            raise e
        return self.clbit_store

    def run_distribution(self, num_clbits: Optional[int] = None) -> Dict[int, float]:
        """Compute the complete final classical-outcome distribution once.

        Unlike :meth:`run`, this method does not choose a single random path.
        It branches the symbolic BDD state at every measurement, continues
        each branch through dynamic control flow, and aggregates equal final
        classical stores.  It is the native source used by the BackendV2
        compatibility layer before shot sampling.
        """
        if num_clbits is not None:
            if not isinstance(num_clbits, int) or isinstance(num_clbits, bool) or num_clbits < 0:
                raise ValueError("num_clbits must be a non-negative integer or None.")

        kernel = BDDCombSim(self.num_qubits, self.precision)
        if hasattr(kernel, 'init_basis_state'):
            kernel.init_basis_state(0)
        states = self._distribution_execute_blocks(
            [_DistributionState(kernel=kernel, clbits={}, probability=1.0)], self.blocks
        )

        outcomes: Dict[int, float] = {}
        for state in states:
            if state.break_requested:
                raise RuntimeError("Encountered 'break' outside a sequential loop.")
            outcome = 0
            for index, value in state.clbits.items():
                if num_clbits is not None and index >= num_clbits:
                    raise ValueError(f"Classical bit index {index} exceeds result width {num_clbits}.")
                outcome |= int(value) << index
            outcomes[outcome] = outcomes.get(outcome, 0.0) + state.probability

        total = sum(outcomes.values())
        if total <= 0.0:
            raise ValueError("Symbolic execution produced an empty classical distribution.")
        return {outcome: probability / total for outcome, probability in outcomes.items()}

    def _distribution_execute_blocks(
        self, states: List[_DistributionState], blocks: list
    ) -> List[_DistributionState]:
        current = states
        for block in blocks:
            next_states: List[_DistributionState] = []
            for state in current:
                if state.break_requested:
                    next_states.append(state)
                elif isinstance(block, CQC):
                    next_states.extend(self._distribution_run_cqc(state, block))
                elif isinstance(block, DQC):
                    value = self._distribution_read_clbits(state, block.target_clbits)
                    selected = block.cases.get(value, block.default_block)
                    next_states.extend(self._distribution_execute_blocks([state], selected))
                elif isinstance(block, SQC):
                    next_states.extend(self._distribution_run_sqc(state, block))
                else:
                    raise TypeError(f"Unknown QSeqSim block type: {type(block).__name__}.")
            current = next_states
        return current

    def _distribution_run_cqc(
        self, state: _DistributionState, cqc: CQC
    ) -> List[_DistributionState]:
        states = [state]
        for op in cqc.ops:
            next_states: List[_DistributionState] = []
            for branch in states:
                if branch.break_requested:
                    next_states.append(branch)
                elif op.name == 'break':
                    branch.break_requested = True
                    next_states.append(branch)
                elif op.name == 'measure':
                    next_states.extend(self._distribution_measure(branch, op))
                else:
                    self._distribution_apply_gate(branch, op)
                    next_states.append(branch)
            states = next_states
        return states

    def _distribution_run_sqc(
        self, state: _DistributionState, sqc: SQC
    ) -> List[_DistributionState]:
        active = [state]
        completed: List[_DistributionState] = []
        iteration = 0
        max_iter = 1000
        while active:
            body_inputs: List[_DistributionState] = []
            for branch in active:
                value = self._distribution_read_clbits(
                    branch, sqc.loop_condition['indices']
                )
                if value == sqc.loop_condition['value']:
                    body_inputs.append(branch)
                else:
                    completed.append(branch)
            if not body_inputs:
                break
            if iteration >= max_iter:
                raise RuntimeError(f"Max iterations (= {max_iter}) reached in SQC.")
            body_outputs = self._distribution_execute_blocks(body_inputs, sqc.body_block)
            active = []
            for branch in body_outputs:
                if branch.break_requested:
                    branch.break_requested = False
                    completed.append(branch)
                else:
                    active.append(branch)
            iteration += 1
        return completed

    def _distribution_measure(
        self, state: _DistributionState, op: GateOp
    ) -> List[_DistributionState]:
        states = [state]
        for q_idx, c_idx in zip(op.qubits, op.c_targets):
            branches: List[_DistributionState] = []
            for parent in states:
                try:
                    joint = [
                        parent.kernel.get_prob([q_idx], [0]),
                        parent.kernel.get_prob([q_idx], [1]),
                    ]
                except RecursionError as exc:
                    raise SymbolicEvaluationError(
                        "Exact symbolic evaluation failed because the recursion limit "
                        f"was reached while computing distribution probabilities for q[{q_idx}]."
                    ) from exc
                norm = joint[0] + joint[1]
                if norm <= 0.0:
                    raise ValueError("State has zero probability during distribution measurement.")
                for measured_value, joint_probability in enumerate(joint):
                    if joint_probability <= 0.0:
                        continue
                    child_kernel = parent.kernel.clone()
                    child_kernel.mid_measure([q_idx], [measured_value])
                    child_clbits = dict(parent.clbits)
                    child_clbits[c_idx] = measured_value
                    branches.append(
                        _DistributionState(
                            kernel=child_kernel,
                            clbits=child_clbits,
                            probability=parent.probability * (joint_probability / norm),
                        )
                    )
            states = branches
        return states

    def _distribution_apply_gate(self, state: _DistributionState, op: GateOp) -> None:
        if op.name == 'mcx':
            if not op.qubits:
                raise ValueError("mcx requires at least one target qubit.")
            state.kernel.multi_controlled_X(op.qubits[:-1], op.qubits[-1])
            return
        method_name = self.GATE_METHOD_MAP.get(op.name)
        if not method_name:
            raise ValueError(f"Unknown gate '{op.name}'")
        method = getattr(state.kernel, method_name, None)
        if method is not None:
            method(*op.qubits)
            return
        apply_gate = getattr(state.kernel, 'apply_gate', None)
        if apply_gate is not None:
            apply_gate(method_name, op.qubits)
            return
        raise AttributeError(f"Kernel object has no method '{method_name}'")

    @staticmethod
    def _distribution_read_clbits(state: _DistributionState, indices: List[int]) -> int:
        value = 0
        for offset, index in enumerate(indices):
            value |= state.clbits.get(index, 0) << offset
        return value

    def print_state_vec(self):
        """
        Print the normalized quantum state vector.
        Automatically handles probability collapse caused by intermediate measurements.
        """
        print(f"\n--- Final Quantum State Vector (Normalized) ---")
        print(f"Global Probability Factor: {self.global_probability:.6f}")

        if self.global_probability <= 0:
            print("State has collapsed to 0 probability (Impossible path).")
            return

        norm_factor = math.sqrt(self.global_probability)

        # For large number of qubits, do not attempt to iterate over all states!
        if self.num_qubits > 20:
            print(f"Num qubits ({self.num_qubits}) is too large to print full state vector.")
            return

        for i in range(1 << self.num_qubits):
            # Get raw amplitude
            raw_amp = self.kernel.get_amplitude(i)
            # Normalize
            norm_amp = raw_amp / norm_factor

            # Only print non-zero terms (optional)
            if abs(norm_amp) > 1e-10:
                print(f"|{bin(i)[2:].zfill(self.num_qubits)}>: {norm_amp:.6f}")

    def _execute_blocks(self, blocks: list):
        for block in blocks:
            if isinstance(block, CQC):
                self._run_cqc(block)
            elif isinstance(block, DQC):
                self._run_dqc(block)
            elif isinstance(block, SQC):
                self._run_sqc(block)

    def _run_cqc(self, cqc: CQC):
        for op in cqc.ops:
            self._dispatch_op(op)

    def _run_dqc(self, dqc: DQC):
        current_val = self._read_clbit_register(dqc.target_clbits)
        if current_val in dqc.cases:
            self._execute_blocks(dqc.cases[current_val])
        else:
            self._execute_blocks(dqc.default_block)

    def _run_sqc(self, sqc: SQC):
        target_indices = sqc.loop_condition['indices']
        expected_val = sqc.loop_condition['value']
        iteration = 0
        MAX_ITER = 1000

        while True:
            current_val = self._read_clbit_register(target_indices)
            if current_val != expected_val:
                break
            if iteration >= MAX_ITER:
                raise RuntimeError(f"Max iterations (= {MAX_ITER}) reached in SQC.")

            try:
                self._execute_blocks(sqc.body_block)
            except StopIteration:
                break
            iteration += 1

    def _dispatch_op(self, op: GateOp):
        if op.name == 'break':
            raise StopIteration("break")
        elif op.name == 'measure':
            self._handle_measurement(op)
        elif op.name == 'mcx':
            if not op.qubits:
                raise ValueError("mcx requires at least one target qubit.")
            self.kernel.multi_controlled_X(op.qubits[:-1], op.qubits[-1])
        else:
            method_name = self.GATE_METHOD_MAP.get(op.name)
            if not method_name:
                raise ValueError(f"Unknown gate '{op.name}'")
            method = getattr(self.kernel, method_name, None)
            if method:
                method(*op.qubits)
            else:
                apply_gate = getattr(self.kernel, 'apply_gate', None)
                if apply_gate:
                    apply_gate(method_name, op.qubits)
                else:
                    raise AttributeError(f"Kernel object has no method '{method_name}'")

    def _handle_measurement(self, op: GateOp):
        """
        Unified measurement handling:
        - If mid-measure (op.is_final_measure == False):
          * Need to collapse quantum state + update global_probability.
        - If final-measure (op.is_final_measure == True):
          * Only generate classical result, do not collapse, do not affect global_probability,
            and do not require preset to be provided.
        """
        for q_idx, c_idx in zip(op.qubits, op.c_targets):
            # 1) Final measurement: Only decide classical result, do not collapse quantum state
            if getattr(op, "is_final_measure", False):
                measured_val = self._decide_final_measure_value(q_idx, c_idx)
                self.clbit_store[c_idx] = measured_val
                continue

            # 2) Mid-measure: Execute original flow
            prob_0_joint = 0.0
            prob_1_joint = 0.0

            if hasattr(self.kernel, 'get_prob'):
                try:
                    prob_0_joint = self.kernel.get_prob([q_idx], [0])
                    prob_1_joint = self.kernel.get_prob([q_idx], [1])
                except RecursionError as exc:
                    raise SymbolicEvaluationError(
                        "Exact symbolic evaluation failed because the recursion limit "
                        f"was reached while computing measurement probabilities for q[{q_idx}]."
                    ) from exc
            else:
                raise AttributeError("Kernel missing 'get_prob' method.")

            current_norm = prob_0_joint + prob_1_joint

            # [Key Modification]
            # Original: if current_norm <= 1e-15:
            # Modified: if current_norm == 0.0:
            # Reason: For 256+ qubits, valid probability can be as low as 1e-78.
            # Since Kernel now implements [Exact Zero Check], only returning 0.0 is truly impossible state.
            if current_norm == 0.0:
                raise ValueError("State collapsed to 0 probability.")

            real_prob_0 = prob_0_joint / current_norm

            # Decide result
            if self.mode == 'sample':
                measured_val = 0 if random.random() < real_prob_0 else 1
            elif self.mode == 'preset':
                if c_idx in self.presets and len(self.presets[c_idx]) > 0:
                    measured_val = self.presets[c_idx].pop(0)
                else:
                    raise ValueError(f"No preset value available for clbit {c_idx}.")
            else:
                measured_val = 0

            # Accumulate global probability (only needed for mid-measure)
            branch_prob = real_prob_0 if measured_val == 0 else (1.0 - real_prob_0)
            self.global_probability *= branch_prob

            # Collapse state
            if hasattr(self.kernel, 'mid_measure'):
                self.kernel.mid_measure([q_idx], [measured_val])
            else:
                raise AttributeError("Kernel missing 'mid_measure' method.")

            self.clbit_store[c_idx] = measured_val

    def _decide_final_measure_value(self, q_idx: int, c_idx: int) -> int:
        """
        Decide classical result for final measurement.
        - Do not collapse quantum state
        - Do not update global_probability
        - sample mode: Sample once based on current state's real distribution (if get_prob available)
        - preset mode: Use preset if available; otherwise sample based on real distribution (no error)
        """
        # 1) preset mode: if preset exists, use it first
        if self.mode == 'preset' and c_idx in self.presets and self.presets[c_idx]:
            return self.presets[c_idx].pop(0)

        # 2) Other cases (sample / preset without preset): Sample once based on real distribution, but do not collapse
        if hasattr(self.kernel, 'get_prob'):
            try:
                p0 = self.kernel.get_prob([q_idx], [0])
                p1 = self.kernel.get_prob([q_idx], [1])
                norm = p0 + p1

                # [Key Modification]
                # Original: if norm > 1e-15:
                # Modified: if norm > 0.0:
                # As long as probability is not absolute 0, normalization sampling can be performed
                if norm <= 0.0:
                    raise ValueError("State has zero probability during final measurement.")
                real_p0 = p0 / norm
            except RecursionError as exc:
                raise SymbolicEvaluationError(
                    "Exact symbolic evaluation failed because the recursion limit "
                    f"was reached while computing final-readout probabilities for q[{q_idx}]."
                ) from exc
        else:
            raise AttributeError("Kernel missing 'get_prob' method.")

        return 0 if random.random() < real_p0 else 1

    def _read_clbit_register(self, indices: List[int]) -> int:
        val = 0
        for i, idx in enumerate(indices):
            bit_val = self.clbit_store.get(idx, 0)
            val += bit_val * (1 << i)
        return val
