import random
import math
from typing import List, Dict, Optional, Any
from .exceptions import SymbolicEvaluationError
from .kernel import BDDCombSim
from .parser import CQC, DQC, SQC, GateOp

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
