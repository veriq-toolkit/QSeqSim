import math
import re
import openqasm3
import openqasm3.ast as ast
import qiskit.qasm3
from qiskit import QuantumCircuit
from typing import Any, List, Set, Dict, Tuple, Optional

COMPACT_QASM_METADATA_KEY = "qseqsim_compact_qasm"

# ==========================================
# 0. Version Compatibility and Type Definitions (Pylance Safe)
# ==========================================

QubitDeclType = getattr(ast, 'QubitDeclaration', getattr(ast, 'QuantumDeclaration', type(None)))
DesignatorType = getattr(ast, 'Designator', type(None))
IndexExprType = getattr(ast, 'IndexExpression', type(None))

# ==========================================
# 1. Data Structure Definitions (Rich IR)
# ==========================================

class GateOp:
    """Atomic Operation: Gate or Measurement"""
    def __init__(
        self,
        name: str,
        qubits: List[int],
        params: List[float] | None = None,
        c_targets: List[int] | None = None,
        is_final_measure: bool = False,  # Whether marked as final measurement
    ):
        self.name = name
        self.qubits = qubits  # [Global Integer Indices]
        self.params = params if params is not None else []
        self.c_targets = c_targets if c_targets is not None else []
        self.is_final_measure = is_final_measure

    def __repr__(self):
        params_str = f", params={self.params}" if self.params else ""
        c_str = f", -> c{self.c_targets}" if self.c_targets else ""
        flag = ", FINAL" if self.name == "measure" and self.is_final_measure else ""
        return f"Op({self.name}{flag}, q={self.qubits}{params_str}{c_str})"

class CQC:
    """Combinational Quantum Circuit"""
    def __init__(self, ops: List[GateOp], global_num_qubits: int):
        self.type = 'CQC'
        self.ops = ops
        self.global_num_qubits = global_num_qubits
        self.involved_qubits: Set[int] = set()
        for op in self.ops:
            self.involved_qubits.update(op.qubits)
            
    def __repr__(self):
        return f"[CQC] Global: {self.global_num_qubits} | Active: {sorted(list(self.involved_qubits))}"

class DQC:
    """Decision Quantum Circuit (Switch-like Structure)"""
    def __init__(self, target_clbits: List[int], cases: Dict[int, List[Any]], default_block: List[Any] | None, global_num_qubits: int):
        self.type = 'DQC'
        self.target_clbits = target_clbits # List of indices (Supports multi-bit register)
        self.cases = cases
        self.default_block = default_block if default_block is not None else []
        self.global_num_qubits = global_num_qubits
        
        self.involved_qubits: Set[int] = set()
        for block_list in self.cases.values():
            for block in block_list:
                self.involved_qubits.update(block.involved_qubits)
        for block in self.default_block:
            self.involved_qubits.update(block.involved_qubits)

    def __repr__(self):
        case_str = ", ".join([f"{v}->{len(b)}blks" for v, b in self.cases.items()])
        def_str = f"Default->{len(self.default_block)}blks"
        return (f"[DQC] Global: {self.global_num_qubits} | "
                f"Targets: c{self.target_clbits} | "
                f"Cases: {{{case_str}}} | {def_str}")

class SQC:
    """
    Sequential Quantum Circuit (Strict Validation)
    """
    def __init__(self, loop_condition: Dict, body_block: List[Any], global_num_qubits: int):
        self.type = 'SQC'
        self.loop_condition = loop_condition # {'indices': [int], 'value': int}
        self.body_block = body_block
        self.global_num_qubits = global_num_qubits
        self.external_qubits: Set[int] = set()
        self.internal_qubits: Set[int] = set()
        
        self._validate_and_extract()
        
        all_qubits = set(range(global_num_qubits))
        self.internal_qubits = all_qubits - self.external_qubits

    def _validate_and_extract(self):
        # Get all classical bit indices involved in the loop condition
        flag_indices = set(self.loop_condition.get('indices', []))
        measured_qubits_trace = set()

        def scan_blocks(blocks: List[Any]):
            for block in blocks:
                # 1. Block-level timing check
                overlap = block.involved_qubits.intersection(measured_qubits_trace)
                if overlap:
                    raise ValueError(
                        f"[SQC Error] Gate operation detected AFTER measurement on qubit(s) {overlap}.\n"
                        f"Hint: In a While-Loop, measurement of the trigger qubit must be the FINAL operation."
                    )

                if isinstance(block, CQC):
                    for op in block.ops:
                        # 2. Op-level timing check
                        op_qubits_set = set(op.qubits)
                        overlap_op = op_qubits_set.intersection(measured_qubits_trace)
                        if overlap_op:
                             raise ValueError(
                                 f"[SQC Error] Gate '{op.name}' detected on qubit(s) {overlap_op} AFTER measurement.\n"
                                 f"Hint: Move the measurement to the end of the loop body."
                             )

                        if op.name == 'measure':
                            # 3. Flag consistency check
                            targets_set = set(op.c_targets)
                            
                            if not targets_set.isdisjoint(flag_indices):
                                measured_qubits_trace.update(op.qubits)
                                self.external_qubits.update(op.qubits)
                
                elif isinstance(block, DQC):
                    for sub_blocks in block.cases.values():
                        scan_blocks(sub_blocks)
                    scan_blocks(block.default_block)
                
                elif isinstance(block, SQC):
                    scan_blocks(block.body_block)

        scan_blocks(self.body_block)
        
        if not self.external_qubits:
             raise ValueError("[SQC Error] No measurements detected updating the loop flag. Infinite loop.")

    def __repr__(self):
        cond_str = f"c{self.loop_condition.get('indices')} == {self.loop_condition.get('value')}"
        return (f"[SQC] Global: {self.global_num_qubits} | "
                f"Flag: {cond_str}\n"
                f"      External (Trigger): {sorted(list(self.external_qubits))}\n"
                f"      Internal (Rest):    {sorted(list(self.internal_qubits))}\n"
                f"      Body: {len(self.body_block)} sub-blocks")

# ==========================================
# 2. Core Parser Class
# ==========================================

class QiskitParser:
    def __init__(self, circuit: QuantumCircuit | None = None):
        self.circuit = circuit
        self.qasm_str = ""
        self.symbol_table = {} 
        self.global_num_qubits = 0
        self.register_offsets = {} 
        self.clbit_offsets = {} 
        self.clbit_widths = {} # Record classical register width
        
        # === Strict Gate Set Validation (Clifford+T) ===
        self.SUPPORTED_GATES = {
            'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 
            'x2p', 'y2p', 
            'cx', 'cz', 'ccx', 'mcx', 'cswap', 'swap',
            'measure', 'break'
        }

    def to_qasm3(self):
        try:
            if self.circuit:
                metadata = getattr(self.circuit, "metadata", None)
                if isinstance(metadata, dict):
                    compact_qasm = metadata.get(COMPACT_QASM_METADATA_KEY)
                    if isinstance(compact_qasm, str) and compact_qasm.strip():
                        self.qasm_str = compact_qasm
                        return
                self.qasm_str = qiskit.qasm3.dumps(self.circuit)
        except Exception as e:
            raise RuntimeError(f"Qiskit to QASM3 conversion failed: {e}")

    def parse(self) -> list:
        if not self.qasm_str:
            if self.circuit:
                self.to_qasm3()
            elif not hasattr(self, 'qasm_str') or not self.qasm_str:
                raise ValueError("No circuit or QASM string provided.")
        
        pattern = r'for\s+(?!(?:int|uint|float|angle|bool)\s+)([a-zA-Z_][a-zA-Z0-9_]*)\s+in'
        fixed_qasm = re.sub(pattern, r'for int \1 in', self.qasm_str)
        
        try:
            # Parse OpenQASM 3 program using a version-tolerant entry point.
            if hasattr(openqasm3, "parse"):
                program = openqasm3.parse(fixed_qasm)
            else:
                from openqasm3 import parser as _parser
                program = _parser.parse(fixed_qasm)
            self._scan_global_topology(program)
        except Exception as e:
            print(f"Error parsing QASM string: {e}")
            print("--- Failed QASM Content ---")
            print(fixed_qasm)
            raise
            
        blocks = self._process_statements(program.statements)
        # IR pass: Mark final measurements
        self._mark_final_measurements(blocks)
        return blocks

    def _get_int_from_node(self, node: Any) -> int:
        if node is None: return 1
        if isinstance(node, ast.IntegerLiteral): return node.value
        if isinstance(node, DesignatorType):
            expr = getattr(node, 'expression', None)
            if isinstance(expr, ast.IntegerLiteral): return expr.value
        return 1

    def _scan_global_topology(self, program: openqasm3.ast.Program):
        q_count = 0
        c_count = 0
        self.register_offsets.clear()
        self.clbit_offsets.clear()
        self.clbit_widths.clear()
        
        for stmt in program.statements:
            if isinstance(stmt, QubitDeclType):
                ident_node = getattr(stmt, 'qubit', getattr(stmt, 'name', None))
                reg_name = ident_node.name if ident_node else "unknown_qreg"
                size_node = getattr(stmt, 'size', getattr(stmt, 'designator', None))
                size = self._get_int_from_node(size_node)
                self.register_offsets[reg_name] = q_count
                q_count += size
            
            elif isinstance(stmt, ast.ClassicalDeclaration):
                ident_node = getattr(stmt, 'identifier', getattr(stmt, 'name', None))
                reg_name = ident_node.name if ident_node else "unknown_creg"
                stmt_type = getattr(stmt, 'type', None)
                size = 1
                if isinstance(stmt_type, ast.BitType):
                    size_node = getattr(stmt_type, 'size', getattr(stmt_type, 'designator', None))
                    size = self._get_int_from_node(size_node)
                self.clbit_offsets[reg_name] = c_count
                self.clbit_widths[reg_name] = size
                c_count += size
        
        self.global_num_qubits = q_count

    def _resolve_q_index(self, name: str, local_index: int) -> int:
        return self.register_offsets.get(name, 0) + local_index

    def _resolve_c_index(self, name: str, local_index: int) -> int:
        return self.clbit_offsets.get(name, 0) + local_index

    def _extract_name_and_index(self, node: Any) -> Tuple[str, int]:
        name = ""
        index = 0
        
        if isinstance(node, ast.IndexedIdentifier):
            name = node.name.name
            idx_node = node.indices[0]
            if isinstance(idx_node, list): idx_node = idx_node[0]
            if isinstance(idx_node, ast.IntegerLiteral):
                index = idx_node.value
            elif isinstance(idx_node, ast.Identifier):
                index = self.symbol_table.get(idx_node.name, 0)

        elif isinstance(node, IndexExprType) or type(node).__name__ == 'IndexExpression':
            collection = getattr(node, 'collection', None)
            if isinstance(collection, ast.Identifier):
                name = collection.name
            
            idx_node = getattr(node, 'index', None)
            if isinstance(idx_node, list): idx_node = idx_node[0]
            
            if isinstance(idx_node, ast.IntegerLiteral):
                index = idx_node.value
            elif isinstance(idx_node, ast.Identifier):
                index = self.symbol_table.get(idx_node.name, 0)

        elif isinstance(node, ast.Identifier):
            name = node.name
            index = 0

        return name, index

    def _process_statements(self, statements: list) -> list:
        blocks = []
        current_gate_buffer: List[GateOp] = [] 

        def flush_buffer():
            if current_gate_buffer:
                blocks.append(CQC(list(current_gate_buffer), self.global_num_qubits))
                current_gate_buffer.clear()

        for stmt in statements:
            if isinstance(stmt, ast.QuantumGate):
                current_gate_buffer.extend(self._parse_gate(stmt))
            elif isinstance(stmt, ast.QuantumMeasurementStatement):
                current_gate_buffer.append(self._parse_measure(stmt))
            elif isinstance(stmt, ast.BreakStatement):
                current_gate_buffer.append(GateOp("break", []))
            elif isinstance(stmt, ast.ForInLoop):
                current_gate_buffer.extend(self._unroll_for_loop(stmt))
            
            elif isinstance(stmt, ast.BranchingStatement):
                flush_buffer()
                
                cond_info = self._parse_condition_expr(stmt.condition)
                target_indices = cond_info['indices']
                trigger_val = cond_info['value']
                
                true_block = getattr(stmt, 'block', getattr(stmt, 'if_block', None))
                true_stmts = self._process_statements(self._extract_statements(true_block))
                
                cases = {trigger_val: true_stmts}
                default_stmts = []
                
                if stmt.else_block:
                    default_stmts = self._process_statements(self._extract_statements(stmt.else_block))
                
                blocks.append(DQC(target_indices, cases, default_stmts, self.global_num_qubits))

            elif isinstance(stmt, ast.SwitchStatement):
                flush_buffer()
                
                target_info = self._parse_condition_expr(stmt.target)
                target_indices = target_info['indices']
                
                cases: Dict[int, List[Any]] = {}
                default_stmts: List[Any] = []
                
                for case in stmt.cases:
                    case_values = getattr(case, 'values', None)
                    case_body = getattr(case, 'body', None)
                    if case_values is None and case_body is None:
                        case_values = case[0]; case_body = case[1]

                    if not case_values: 
                        default_stmts = self._process_statements(self._extract_statements(case_body))
                        continue
                    
                    val = self._eval_expr(case_values[0])
                    body = self._process_statements(self._extract_statements(case_body))
                    cases[int(val)] = body
                
                blocks.append(DQC(target_indices, cases, default_stmts, self.global_num_qubits))

            elif isinstance(stmt, ast.WhileLoop):
                flush_buffer()
                body_blocks = self._process_statements(self._extract_statements(stmt.block))
                cond_node = getattr(stmt, 'while_condition', getattr(stmt, 'condition', None))
                blocks.append(SQC(self._parse_condition_expr(cond_node), body_blocks, self.global_num_qubits))

        flush_buffer()
        return blocks

    def _parse_gate(self, gate_node: ast.QuantumGate) -> List[GateOp]:
        raw_name = gate_node.name.name.lower()
        if raw_name == 'id': return [] 
        
        params = [self._eval_expr(arg) for arg in gate_node.arguments]
        qubits: List[int] = []
        for q in gate_node.qubits:
            reg_name, local_idx = self._extract_name_and_index(q)
            if reg_name:
                qubits.append(self._resolve_q_index(reg_name, local_idx))

        ops_buffer: List[GateOp] = []

        # --- 1. Rx Gate 处理 ---
        if raw_name == 'rx':
            theta = params[0]
            # 归一化到 (-pi, pi]
            theta = (theta + math.pi) % (2 * math.pi) - math.pi
            
            if math.isclose(theta, math.pi/2): 
                # Rx(pi/2) -> X2P
                ops_buffer.append(GateOp('x2p', qubits))
            elif math.isclose(theta, -math.pi/2):
                # Rx(-pi/2) -> Z + X2P + Z
                # 利用恒等式: Rx(-theta) = Z * Rx(theta) * Z
                ops_buffer.append(GateOp('z', qubits))
                ops_buffer.append(GateOp('x2p', qubits))
                ops_buffer.append(GateOp('z', qubits))
            else: 
                raise ValueError(f"Unsupported Rx angle: {theta}. Only +/- pi/2 supported.")

        # --- 2. Ry Gate 处理 ---
        elif raw_name == 'ry':
            theta = params[0]
            theta = (theta + math.pi) % (2 * math.pi) - math.pi
            
            if math.isclose(theta, math.pi/2): 
                # Ry(pi/2) -> Y2P
                ops_buffer.append(GateOp('y2p', qubits))
            elif math.isclose(theta, -math.pi/2):
                # Ry(-pi/2) -> X + Y2P + X
                # 利用恒等式: Ry(-theta) = X * Ry(theta) * X
                ops_buffer.append(GateOp('x', qubits))
                ops_buffer.append(GateOp('y2p', qubits))
                ops_buffer.append(GateOp('x', qubits))
            else: 
                raise ValueError(f"Unsupported Ry angle: {theta}. Only +/- pi/2 supported.")

        # --- 3. Rz / Phase Gate 处理 ---
        elif raw_name in ['rz', 'p']:
            theta = params[0] % (2 * math.pi)
            
            # 标准化角度检查
            if math.isclose(theta, math.pi/2) or math.isclose(theta, -3*math.pi/2): 
                ops_buffer.append(GateOp('s', qubits))
            elif math.isclose(theta, 3*math.pi/2) or math.isclose(theta, -math.pi/2): 
                ops_buffer.append(GateOp('sdg', qubits))
            elif math.isclose(theta, math.pi/4) or math.isclose(theta, -7*math.pi/4): 
                ops_buffer.append(GateOp('t', qubits))
            elif math.isclose(theta, 7*math.pi/4) or math.isclose(theta, -math.pi/4): 
                ops_buffer.append(GateOp('tdg', qubits))
            elif math.isclose(theta, math.pi) or math.isclose(theta, -math.pi): 
                ops_buffer.append(GateOp('z', qubits))
            elif math.isclose(theta, 0):
                pass # Identity
            else: 
                raise ValueError(f"Unsupported Rz/Phase angle: {theta}. Only pi/2, pi/4 multiples supported.")

        # --- 4. 基础门处理 ---
        else:
            mapped_name = raw_name
            mapped_params: List[float] = []

            if mapped_name == 'cnot': mapped_name = 'cx'
            elif mapped_name == 'toffoli': mapped_name = 'ccx'
            elif mapped_name == 'fredkin': mapped_name = 'cswap'

            if mapped_name not in self.SUPPORTED_GATES:
                raise ValueError(f"Unsupported Gate: '{raw_name}' (mapped to '{mapped_name}'). Kernel only supports Clifford+T.")
            
            ops_buffer.append(GateOp(mapped_name, qubits, mapped_params))

        return ops_buffer

    def _parse_measure(self, stmt: ast.QuantumMeasurementStatement) -> GateOp:
        meas_obj = stmt.measure 
        reg_name, local_idx = self._extract_name_and_index(meas_obj.qubit)
        qubits: List[int] = []
        if reg_name:
            qubits.append(self._resolve_q_index(reg_name, local_idx))
        
        c_targets: List[int] = []
        if stmt.target:
            c_name, c_idx = self._extract_name_and_index(stmt.target)
            if c_name:
                c_targets.append(self._resolve_c_index(c_name, c_idx))
            
        return GateOp("measure", qubits, c_targets=c_targets, is_final_measure=False)

    def _parse_condition_expr(self, node: Any) -> Dict:
        info = {'indices': [], 'value': 1} 
        
        def get_indices(n):
            if isinstance(n, ast.IndexedIdentifier):
                name = n.name.name
                idx_node = n.indices[0]
                if isinstance(idx_node, list): idx_node = idx_node[0]
                if isinstance(idx_node, ast.IntegerLiteral): idx = idx_node.value
                elif isinstance(idx_node, ast.Identifier): idx = self.symbol_table.get(idx_node.name, 0)
                else: idx = 0
                return [self._resolve_c_index(name, idx)]
            
            elif isinstance(n, ast.Identifier):
                name = n.name
                start = self._resolve_c_index(name, 0)
                width = self.clbit_widths.get(name, 1)
                return list(range(start, start + width))
            
            elif isinstance(n, IndexExprType) or type(n).__name__ == 'IndexExpression':
                collection = getattr(n, 'collection', None)
                name = collection.name if collection else ""
                idx_node = getattr(n, 'index', None)
                if isinstance(idx_node, list): idx_node = idx_node[0]
                if isinstance(idx_node, ast.IntegerLiteral): idx = idx_node.value
                elif isinstance(idx_node, ast.Identifier): idx = self.symbol_table.get(idx_node.name, 0)
                else: idx = 0
                return [self._resolve_c_index(name, idx)]
            
            return []

        if isinstance(node, ast.BinaryExpression):
            info['indices'] = get_indices(node.lhs)
            if isinstance(node.rhs, ast.IntegerLiteral): info['value'] = node.rhs.value
            elif isinstance(node.rhs, ast.BooleanLiteral): info['value'] = 1 if node.rhs.value else 0
        
        elif isinstance(node, ast.UnaryExpression):
             info['indices'] = get_indices(node.expression)
             info['value'] = 0
        
        else:
             info['indices'] = get_indices(node)
             
        return info

    def _unroll_for_loop(self, loop_node: ast.ForInLoop) -> list:
        loop_var_node = getattr(loop_node, 'loop_variable', None)
        ident_node = getattr(loop_node, 'identifier', None)
        loop_var_name = "unknown_i"
        if loop_var_node is not None: loop_var_name = loop_var_node.name
        elif ident_node is not None:
            loop_var_name = ident_node.name if hasattr(ident_node, 'name') else str(ident_node)

        collection = getattr(loop_node, 'collection', getattr(loop_node, 'set_declaration', None))
        start, stop, step = 0, 0, 1
        if isinstance(collection, ast.RangeDefinition):
            start = self._eval_expr(collection.start)
            if collection.end: stop = self._eval_expr(collection.end)
            if collection.step: step = self._eval_expr(collection.step)
        else: return []

        unrolled_gates: List[GateOp] = []
        
        try:
            start_val = int(start)
            stop_val = int(stop)
            step_val = int(step)
            
            if step_val > 0:
                loop_range = range(start_val, stop_val + 1, step_val)
            elif step_val < 0:
                loop_range = range(start_val, stop_val - 1, step_val)
            else:
                loop_range = []
        except ValueError:
            loop_range = []

        for i in loop_range:
            self.symbol_table[loop_var_name] = i
            body_stmts = self._extract_statements(loop_node.block)
            for stmt in body_stmts:
                if isinstance(stmt, ast.QuantumGate):
                    ops = self._parse_gate(stmt)
                    unrolled_gates.extend(ops) 
                elif isinstance(stmt, ast.QuantumMeasurementStatement):
                    op = self._parse_measure(stmt)
                    unrolled_gates.append(op)
        
        if loop_var_name in self.symbol_table: del self.symbol_table[loop_var_name]
        return unrolled_gates

    def _eval_expr(self, node) -> float:
        if isinstance(node, ast.FloatLiteral): return node.value
        if isinstance(node, ast.IntegerLiteral): return float(node.value)
        if isinstance(node, ast.Identifier):
            if node.name == 'pi': return math.pi
            return 0.0
        if isinstance(node, ast.UnaryExpression):
             val = self._eval_expr(node.expression)
             op_name = getattr(node.op, 'name', str(node.op))
             if op_name in ('Minus', 'Sub', '-'): return -val
             return val
        if isinstance(node, ast.BinaryExpression):
             left = self._eval_expr(node.lhs)
             right = self._eval_expr(node.rhs)
             op_name = getattr(node.op, 'name', str(node.op))
             if op_name in ('Div', 'Slash', '/'): return left / right
             if op_name in ('Mul', 'Asterisk', '*'): return left * right
             if op_name in ('Add', 'Plus', '+'): return left + right
             if op_name in ('Sub', 'Minus', '-'): return left - right
        return 0.0

    def _extract_statements(self, block_node: Any | None) -> list:
        if block_node is None: return []
        if isinstance(block_node, list): return block_node
        return getattr(block_node, 'statements', [])

    # ==========================================
    # 3. IR-level "Final Measurement" Global Marking Pass
    # ==========================================

    def _mark_final_measurements(self, blocks: list):
        """
        Perform a global mark on all GateOp("measure") at the IR level:
        - For each qubit, look at its "last operation" in the entire program sequence;
          If the last operation is a measurement, and the classical bit written by this measurement
          is NOT involved in any control flow condition, then is_final_measure=True.
        - Otherwise, it is a mid-measure.
        """

        # 1. Collect all classical bits involved in "control flow conditions"
        control_flag_clbits: set[int] = set()

        def collect_flags(blks: list):
            for blk in blks:
                if isinstance(blk, DQC):
                    control_flag_clbits.update(blk.target_clbits)
                    for sub_blks in blk.cases.values():
                        collect_flags(sub_blks)
                    collect_flags(blk.default_block)
                elif isinstance(blk, SQC):
                    control_flag_clbits.update(blk.loop_condition.get('indices', []))
                    collect_flags(blk.body_block)

        collect_flags(blocks)

        # 2. Global Timeline: Assign a global op_id for each GateOp, collect (qubit, op_id, op_ref)
        #    Note: Even inside branches/loops, we simply linearize in DFS order.
        qubit_usages: Dict[int, List[Tuple[int, GateOp]]] = {}  # q -> [(op_id, op_ref), ...]
        op_counter = 0

        def dfs_collect(blks: list):
            nonlocal op_counter
            for blk in blks:
                if isinstance(blk, CQC):
                    for op in blk.ops:
                        # Skip break
                        if op.name == "break":
                            continue
                        current_id = op_counter
                        op_counter += 1
                        for q in op.qubits:
                            qubit_usages.setdefault(q, []).append((current_id, op))
                elif isinstance(blk, DQC):
                    # Branches/Default are also included in the timeline (conservative approach)
                    for sub_blks in blk.cases.values():
                        dfs_collect(sub_blks)
                    dfs_collect(blk.default_block)
                elif isinstance(blk, SQC):
                    dfs_collect(blk.body_block)

        dfs_collect(blocks)

        # 3. Find "last op" for each qubit. If it's a measurement and not involved in control flow, mark as final
        for q, usage_list in qubit_usages.items():
            if not usage_list:
                continue
            # Sort by op_id ascending
            usage_list.sort(key=lambda x: x[0])
            last_id, last_op = usage_list[-1]

            # If the last operation is not a measurement, skip directly
            if last_op.name != "measure":
                continue

            # If this measurement writes to a control flow classical bit, force mid-measure
            is_control_flow_measure = any(c in control_flag_clbits for c in last_op.c_targets)
            if is_control_flow_measure:
                continue

            # Otherwise, this is the final measurement for qubit q
            last_op.is_final_measure = True
