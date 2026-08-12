from math import ceil, log2, sqrt, pi, isclose
import cmath as cm
from dd import cudd as _bdd
from fractions import Fraction
from decimal import Decimal, getcontext  # <--- Must import decimal

# Set the precision for Decimal.
# 256 qubits require approximately 77 decimal digits of precision.
# To safely handle intermediate calculations and cancellations, we set it to 150 digits.
getcontext().prec = 150

class BDDCombSim:
    def __init__(self, n, r):
        self.BDD = _bdd.BDD()
        self.BDD.configure(reordering=True)
        self.n = n
        self.r = r
        for i in range(self.n):
            self.BDD.add_var('q%d' % i)
        self.Fa = []
        self.Fb = []
        self.Fc = []
        self.Fd = []
        for i in range(self.r):
            self.Fa.append(self.BDD.false)
            self.Fb.append(self.BDD.false)
            self.Fc.append(self.BDD.false)
            self.Fd.append(self.BDD.false)
        self.k = 0

    def init_basis_state(self, basis):
        assert basis < (1 << self.n), "Basis state is out of range!"
        tmp = dict()
        for i in range(self.n):
            tmp['q%d' % i] = bool((basis >> (self.n - 1 - i)) & 1)
        self.Fd[0] = self.BDD.cube(tmp)

    def Car(self, A, B, C):
        return self.BDD.add_expr(r'({A} & {B}) | (({A} | {B}) & {C})'.format(A=A, B=B, C=C))

    def Sum(self, A, B, C):
        return self.BDD.add_expr(r'{A} ^ {B} ^ {C}'.format(A=A, B=B, C=C))

    def X(self, target):
        r = len(self.Fd)
        trans = lambda x: (self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.false}, x)) | (
                ~self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.true}, x))
        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])
        self.simplify_tail()

    def Y(self, target):
        r = len(self.Fd)
        g = lambda x: (self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.false}, x)) | (
                ~self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.true}, x))
        d1 = lambda x: (self.BDD.var('q%d' % target) & x) | (~self.BDD.var('q%d' % target) & ~x)
        d2 = lambda x: (self.BDD.var('q%d' % target) & ~x) | (~self.BDD.var('q%d' % target) & x)

        def trans1(x):
            Cx = []
            Cx.append(~self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Dx = d1(g(x[i]))
                Cx.append(self.Car(Dx, self.BDD.false, Cx[i]))
                tmpx.append(self.Sum(Dx, self.BDD.false, Cx[i]))
            tmpx.append(self.Sum(d1(g(x[r - 1])), self.BDD.false, Cx[r]))
            return tmpx.copy()

        def trans2(x):
            Cx = []
            Cx.append(self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Dx = d2(g(x[i]))
                Cx.append(self.Car(Dx, self.BDD.false, Cx[i]))
                tmpx.append(self.Sum(Dx, self.BDD.false, Cx[i]))
            tmpx.append(self.Sum(d2(g(x[r - 1])), self.BDD.false, Cx[r]))
            return tmpx.copy()

        tmpa = trans1(self.Fc)
        tmpb = trans1(self.Fd)
        tmpc = trans2(self.Fa)
        tmpd = trans2(self.Fb)
        self.Fa = tmpa.copy()
        self.Fb = tmpb.copy()
        self.Fc = tmpc.copy()
        self.Fd = tmpd.copy()
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def Z(self, target):
        r = len(self.Fd)
        g = lambda x: (~self.BDD.var('q%d' % target) & x) | (self.BDD.var('q%d' % target) & ~x)

        def trans(x):
            Cx = []
            Cx.append(self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Gx = g(x[i])
                Cx.append(self.Car(Gx, self.BDD.false, Cx[i]))
                tmpx.append(self.Sum(Gx, self.BDD.false, Cx[i]))
            tmpx.append(self.Sum(g(x[r - 1]), self.BDD.false, Cx[r]))
            return tmpx.copy()

        self.Fa = trans(self.Fa)
        self.Fb = trans(self.Fb)
        self.Fc = trans(self.Fc)
        self.Fd = trans(self.Fd)
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def H(self, target):
        r = len(self.Fd)
        g = lambda x: self.BDD.let({'q%d' % target: self.BDD.false}, x)
        d = lambda x: (~self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.true}, x)) | (
                self.BDD.var('q%d' % target) & ~x)

        def trans(x):
            Cx = []
            Cx.append(self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Gx = g(x[i])
                Dx = d(x[i])
                Cx.append(self.Car(Gx, Dx, Cx[i]))
                tmpx.append(self.Sum(Gx, Dx, Cx[i]))
            tmpx.append(self.Sum(g(x[r - 1]), d(x[r - 1]), Cx[r]))
            return tmpx.copy()

        self.Fa = trans(self.Fa)
        self.Fb = trans(self.Fb)
        self.Fc = trans(self.Fc)
        self.Fd = trans(self.Fd)
        self.k += 1
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def S(self, target):
        r = len(self.Fd)
        trans1 = lambda x, y: (~self.BDD.var('q%d' % target) & x) | (self.BDD.var('q%d' % target) & y)
        g = lambda x, y: (~self.BDD.var('q%d' % target) & x) | (self.BDD.var('q%d' % target) & ~y)
        tmpa = []
        tmpb = []
        for i in range(r):
            tmpa.append(trans1(self.Fa[i], self.Fc[i]))
            tmpb.append(trans1(self.Fb[i], self.Fd[i]))
        tmpa.append(tmpa[-1])
        tmpb.append(tmpb[-1])

        def trans2(x, y):
            Cx = []
            Cx.append(self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Gx = g(x[i], y[i])
                Cx.append(self.Car(Gx, self.BDD.false, Cx[i]))
                tmpx.append(self.Sum(Gx, self.BDD.false, Cx[i]))
            tmpx.append(self.Sum(g(x[r - 1], y[r - 1]), self.BDD.false, Cx[r]))
            return tmpx.copy()

        self.Fc = trans2(self.Fc, self.Fa)
        self.Fd = trans2(self.Fd, self.Fb)
        self.Fa = tmpa.copy()
        self.Fb = tmpb.copy()
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def T(self, target):
        r = len(self.Fd)
        trans1 = lambda x, y: (~self.BDD.var('q%d' % target) & x) | (self.BDD.var('q%d' % target) & y)
        g = lambda x, y: (~self.BDD.var('q%d' % target) & x) | (self.BDD.var('q%d' % target) & ~y)
        tmpa = []
        tmpb = []
        tmpc = []
        for i in range(r):
            tmpa.append(trans1(self.Fa[i], self.Fb[i]))
            tmpb.append(trans1(self.Fb[i], self.Fc[i]))
            tmpc.append(trans1(self.Fc[i], self.Fd[i]))
        tmpa.append(tmpa[-1])
        tmpb.append(tmpb[-1])
        tmpc.append(tmpc[-1])
        Cd = []
        Cd.append(self.BDD.var('q%d' % target))
        tmpd = []
        for i in range(r):
            Gd = g(self.Fd[i], self.Fa[i])
            Cd.append(self.Car(Gd, self.BDD.false, Cd[i]))
            tmpd.append(self.Sum(Gd, self.BDD.false, Cd[i]))
        tmpd.append(self.Sum(g(self.Fd[r - 1], self.Fa[r - 1]), self.BDD.false, Cd[r]))
        self.Fa = tmpa.copy()
        self.Fb = tmpb.copy()
        self.Fc = tmpc.copy()
        self.Fd = tmpd.copy()
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def TDG(self, target):
        self.Z(target)
        self.S(target)
        self.T(target)

    def SDG(self, target):
        self.Z(target)
        self.S(target)

    def X2P(self, target):
        # Rx(pi/2) gate
        r = len(self.Fd)
        d = lambda x: (self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.false}, x)) | (
                ~self.BDD.var('q%d' % target) & self.BDD.let({'q%d' % target: self.BDD.true}, x))

        def trans1(x, y):
            Cx = []
            Cx.append(self.BDD.true)
            tmpx = []
            for i in range(r):
                Dx = d(x[i])
                Cx.append(self.Car(y[i], ~Dx, Cx[i]))
                tmpx.append(self.Sum(y[i], ~Dx, Cx[i]))
            tmpx.append(self.Sum(y[r - 1], ~d(x[r - 1]), Cx[r]))
            return tmpx.copy()

        def trans2(x, y):
            Cx = []
            Cx.append(self.BDD.false)
            tmpx = []
            for i in range(r):
                Dx = d(x[i])
                Cx.append(self.Car(y[i], Dx, Cx[i]))
                tmpx.append(self.Sum(y[i], Dx, Cx[i]))
            tmpx.append(self.Sum(y[r - 1], d(x[r - 1]), Cx[r]))
            return tmpx.copy()

        tmpa = trans1(self.Fc, self.Fa)
        tmpb = trans1(self.Fd, self.Fb)
        tmpc = trans2(self.Fa, self.Fc)
        tmpd = trans2(self.Fb, self.Fd)
        self.Fa = tmpa.copy()
        self.Fb = tmpb.copy()
        self.Fc = tmpc.copy()
        self.Fd = tmpd.copy()
        self.k += 1
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def Y2P(self, target):
        # Ry(pi/2) gate
        r = len(self.Fd)
        g = lambda x: self.BDD.let({'q%d' % target: self.BDD.false}, x)
        d = lambda x: (self.BDD.var('q%d' % target) & x) | (
                ~self.BDD.var('q%d' % target) & ~self.BDD.let({'q%d' % target: self.BDD.true}, x))

        def trans(x):
            Cx = []
            Cx.append(~self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Gx = g(x[i])
                Dx = d(x[i])
                Cx.append(self.Car(Gx, Dx, Cx[i]))
                tmpx.append(self.Sum(Gx, Dx, Cx[i]))
            tmpx.append(self.Sum(g(x[r - 1]), d(x[r - 1]), Cx[r]))
            return tmpx.copy()

        self.Fa = trans(self.Fa)
        self.Fb = trans(self.Fb)
        self.Fc = trans(self.Fc)
        self.Fd = trans(self.Fd)
        self.k += 1
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def CNOT(self, control, target):
        r = len(self.Fd)

        def trans(x):
            return (~self.BDD.var('q%d' % control) & x) | (
                    self.BDD.var('q%d' % control) & self.BDD.var('q%d' % target) & self.BDD.let(
                {'q%d' % control: self.BDD.true, 'q%d' % target: self.BDD.false}, x)) | (
                    self.BDD.var('q%d' % control) & ~self.BDD.var('q%d' % target) & self.BDD.let(
                {'q%d' % control: self.BDD.true, 'q%d' % target: self.BDD.true}, x))

        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])
        self.simplify_tail()

    def SWAP(self, target1, target2):
        self.CNOT(target1, target2)
        self.CNOT(target2, target1)
        self.CNOT(target1, target2)

    def CZ(self, control, target):
        r = len(self.Fd)
        g = lambda x: (~(self.BDD.var('q%d' % control) & self.BDD.var('q%d' % target)) & x) | (
                self.BDD.var('q%d' % control) & self.BDD.var('q%d' % target) & ~x)

        def trans(x):
            Cx = []
            Cx.append(self.BDD.var('q%d' % control) & self.BDD.var('q%d' % target))
            tmpx = []
            for i in range(r):
                Gx = g(x[i])
                Cx.append(self.Car(Gx, self.BDD.false, Cx[i]))
                tmpx.append(self.Sum(Gx, self.BDD.false, Cx[i]))
            tmpx.append(self.Sum(g(x[r - 1]), self.BDD.false, Cx[r]))
            return tmpx.copy()

        self.Fa = trans(self.Fa)
        self.Fb = trans(self.Fb)
        self.Fc = trans(self.Fc)
        self.Fd = trans(self.Fd)
        self.simplify_overflow()  # Overflow
        self.simplify_tail()

    def Toffoli(self, control1, control2, target):
        # CCNOT gate
        r = len(self.Fd)

        def trans(x):
            return (~(self.BDD.var('q%d' % control1) & self.BDD.var('q%d' % control2)) & x) | (
                    self.BDD.var('q%d' % control1) & self.BDD.var('q%d' % control2) & self.BDD.var(
                'q%d' % target) & self.BDD.let(
                {'q%d' % control1: self.BDD.true, 'q%d' % control2: self.BDD.true, 'q%d' % target: self.BDD.false},
                x)) | (self.BDD.var('q%d' % control1) & self.BDD.var('q%d' % control2) & ~self.BDD.var(
                'q%d' % target) & self.BDD.let(
                {'q%d' % control1: self.BDD.true, 'q%d' % control2: self.BDD.true, 'q%d' % target: self.BDD.true}, x))

        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])
        self.simplify_tail()

    def Fredkin(self, control, target1, target2):
        # CSWAP gate
        r = len(self.Fd)

        def trans(x):
            return (~(self.BDD.var('q%d' % control) & self.BDD.apply('^', self.BDD.var('q%d' % target1),
                                                                     self.BDD.var('q%d' % target2))) & x) | (
                    self.BDD.var('q%d' % control) & self.BDD.var('q%d' % target1) & ~self.BDD.var(
                'q%d' % target2) & self.BDD.let(
                {'q%d' % control: self.BDD.true, 'q%d' % target1: self.BDD.false, 'q%d' % target2: self.BDD.true},
                x)) | (
                    self.BDD.var('q%d' % control) & ~self.BDD.var('q%d' % target1) & self.BDD.var(
                'q%d' % target2) & self.BDD.let(
                {'q%d' % control: self.BDD.true, 'q%d' % target1: self.BDD.true, 'q%d' % target2: self.BDD.false}, x))

        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])
        self.simplify_tail()

    def cwalk(self, control, targets):
        self.X(control)
        for i in range(len(targets)):
            self.multi_controlled_X([control]+targets[i+1:], targets[i])
        self.X(control)
        for i in range(len(targets)-1, -1, -1):
            self.multi_controlled_X([control]+targets[i+1:], targets[i])

    def multi_controlled_X(self, controls, target):
        """
        Implements the C^nX gate: applies X flip to the target qubit when all control qubits are 1.
        controls: list or tuple, containing control qubit indices, e.g., [c1, c2, ..., cn]
        target: int, target qubit index
        """
        r = len(self.Fd)

        def trans(x):
            # 1) Construct "all_controls" representing the AND of all control qubits
            all_ctrl_expr = self.BDD.true
            for c in controls:
                all_ctrl_expr &= self.BDD.var('q%d' % c)

            # 2) If all control qubits are 1, execute flip logic; otherwise, keep unchanged.
            #    The flip logic is similar to X, distinguishing whether the target bit is 0 or 1 before substitution.
            return (
                    (~all_ctrl_expr & x) |
                    (all_ctrl_expr & self.BDD.var('q%d' % target) &
                     self.BDD.let(
                         {**{'q%d' % c: self.BDD.true for c in controls},
                          'q%d' % target: self.BDD.false},
                         x
                     )) |
                    (all_ctrl_expr & ~self.BDD.var('q%d' % target) &
                     self.BDD.let(
                         {**{'q%d' % c: self.BDD.true for c in controls},
                          'q%d' % target: self.BDD.true},
                         x
                     ))
            )

        # 3) Iterate to update self.Fa / self.Fb / self.Fc / self.Fd
        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])

        self.simplify_tail()

    # def get_total_bdd(self):
    #     m = ceil(log2(self.r)) + 2  # The number of index Boolean variables
    #     for i in range(m):
    #         self.BDD.add_var('x%d' % i)
    #     g = []
    #     for i in range(self.r):
    #         tmp = dict()
    #         for j in range(2, m):
    #             tmp['x%d' % j] = bool((i >> (j - 2)) & 1)
    #         g.append(self.BDD.cube(tmp))
    #     FA = self.BDD.false
    #     FB = self.BDD.false
    #     FC = self.BDD.false
    #     FD = self.BDD.false
    #     for i in range(self.r):
    #         FA = self.BDD.apply('|', FA, g[i] & self.Fa[i])
    #         FB = self.BDD.apply('|', FB, g[i] & self.Fb[i])
    #         FC = self.BDD.apply('|', FC, g[i] & self.Fc[i])
    #         FD = self.BDD.apply('|', FD, g[i] & self.Fd[i])
    #     x0 = self.BDD.var('x0')
    #     x1 = self.BDD.var('x1')
    #     return (x0 & x1 & FA) | (x0 & ~x1 & FB) | (~x0 & x1 & FC) | (~x0 & ~x1 & FD)

    # def get_prob(self, target_list, result_list):
    #     """
    #     target_list: the list of target qubits. NOTICE: Elements in a list cannot be the same!
    #     result_list: the list of measurement results.
    #     """
    #     if len(target_list) > len(result_list):
    #         target_list = target_list[:len(result_list)]
    #     if len(target_list) < self.n:
    #         next_list = self.get_next_list(target_list)
    #         return self.get_prob(next_list, result_list + [0]) + self.get_prob(next_list, result_list + [1])
    #
    #     F = self.get_total_bdd()
    #     bool_list = [self.BDD.false, self.BDD.true]
    #     for i in range(len(target_list)):
    #         F = self.BDD.let({'q%d' % target_list[i]: bool_list[result_list[i]]}, F)
    #     FA = self.BDD.let({'x0': self.BDD.true, 'x1': self.BDD.true}, F)
    #     FB = self.BDD.let({'x0': self.BDD.true, 'x1': self.BDD.false}, F)
    #     FC = self.BDD.let({'x0': self.BDD.false, 'x1': self.BDD.true}, F)
    #     FD = self.BDD.let({'x0': self.BDD.false, 'x1': self.BDD.false}, F)
    #     a = self.get_value(FA)
    #     b = self.get_value(FB)
    #     c = self.get_value(FC)
    #     d = self.get_value(FD)
    #     w = cm.exp(1j * pi / 4)
    #     amplitude = (a * w ** 3 + b * w ** 2 + c * w + d) / pow(sqrt(2), self.k)
    #     return abs(amplitude) ** 2

    # def get_amplitude(self, cpt_basis):
    #     F = self.get_total_bdd()
    #     bool_list = [self.BDD.false, self.BDD.true]
    #     tmp = dict()
    #     for i in range(self.n):
    #         tmp['q%d' % i] = bool_list[(cpt_basis >> (self.n - 1 - i)) & 1]
    #     F = self.BDD.let(tmp, F)
    #     FA = self.BDD.let({'x0': self.BDD.true, 'x1': self.BDD.true}, F)
    #     FB = self.BDD.let({'x0': self.BDD.true, 'x1': self.BDD.false}, F)
    #     FC = self.BDD.let({'x0': self.BDD.false, 'x1': self.BDD.true}, F)
    #     FD = self.BDD.let({'x0': self.BDD.false, 'x1': self.BDD.false}, F)
    #     a = self.get_value(FA)
    #     b = self.get_value(FB)
    #     c = self.get_value(FC)
    #     d = self.get_value(FD)
    #     w = cm.exp(1j * pi / 4)
    #     amplitude = (a * w ** 3 + b * w ** 2 + c * w + d) / pow(sqrt(2), self.k)
    #     return amplitude

    def get_amplitude(self, cpt_basis):
        """
        [Optimized get_amplitude]
        Directly constraints Fa/Fb/Fc/Fd based on the basis state, without constructing the huge get_total_bdd.
        Solves the memory explosion problem.
        """
        # 1. Convert integer basis state (e.g., 5 -> 101) to BDD constraint dictionary
        # Example: {'q0': True, 'q1': False, 'q2': True}
        bool_list = [self.BDD.false, self.BDD.true]
        constraint_dict = dict()
        for i in range(self.n):
            # Note: Preserving the logic where higher bits are at the front
            bit_val = (cpt_basis >> (self.n - 1 - i)) & 1
            constraint_dict['q%d' % i] = bool_list[bit_val]

        # 2. Key step: Apply constraints directly to the four component lists.
        # Since cpt_basis includes all qubits, applying let will turn
        # every BDD node in the list into a constant True or False node.
        restricted_Fa = [self.BDD.let(constraint_dict, f) for f in self.Fa]
        restricted_Fb = [self.BDD.let(constraint_dict, f) for f in self.Fb]
        restricted_Fc = [self.BDD.let(constraint_dict, f) for f in self.Fc]
        restricted_Fd = [self.BDD.let(constraint_dict, f) for f in self.Fd]

        # 3. Directly calculate integer values
        val_a = self._get_value_from_list(restricted_Fa)
        val_b = self._get_value_from_list(restricted_Fb)
        val_c = self._get_value_from_list(restricted_Fc)
        val_d = self._get_value_from_list(restricted_Fd)

        # 4. Combine complex amplitudes
        w = cm.exp(1j * pi / 4)
        amplitude = (val_a * w ** 3 + val_b * w ** 2 + val_c * w + val_d) / pow(sqrt(2), self.k)

        return amplitude


    def mid_measure(self, target_list, result_list):
        l = len(result_list)
        d = {'q%d' % target_list[j]: bool(result_list[j]) for j in range(l)}
        constraint = self.BDD.true
        for j in range(l):
            var = self.BDD.var('q%d' % target_list[j])
            if result_list[j]:
                constraint &= var
            else:
                constraint &= ~var
        for i in range(self.r):
            # Apply substitution using let
            self.Fa[i] = self.BDD.let(d, self.Fa[i]) & constraint
            self.Fb[i] = self.BDD.let(d, self.Fb[i]) & constraint
            self.Fc[i] = self.BDD.let(d, self.Fc[i]) & constraint
            self.Fd[i] = self.BDD.let(d, self.Fd[i]) & constraint
        self.simplify_tail()

    def reset(self, target):
        r = len(self.Fd)
        trans = lambda x: (~self.BDD.var('q%d' % target)) & (self.BDD.let({'q%d' % target: self.BDD.false}, x) |
                                                             self.BDD.let({'q%d' % target: self.BDD.true}, x))
        for i in range(r):
            self.Fa[i] = trans(self.Fa[i])
            self.Fb[i] = trans(self.Fb[i])
            self.Fc[i] = trans(self.Fc[i])
            self.Fd[i] = trans(self.Fd[i])
        self.simplify_tail()

    def measure(self, target_list, result_list):
        tmp = target_list.copy()
        print("The probability of measuring qubits %s and getting results %s is %f." % (
            target_list, result_list, self.get_prob(tmp, result_list)))

    def get_next_list(self, target_list):
        for i in range(self.n):
            if i not in target_list:
                target_list.append(i)
                break
        return target_list

    def _get_value_from_assignment(self, bdd_list, assignment):
        """
        Helper function: Given a specific variable assignment, calculate the integer value represented by bdd_list.
        """
        # Calculate sign bit
        is_negative = (self.BDD.let(assignment, bdd_list[-1]) == self.BDD.true)
        
        final_val = 0
        limit = self.r - 1
        
        if not is_negative:
            for i in range(limit):
                # Apply assignment to each BDD bit to check if result is True or False
                if self.BDD.let(assignment, bdd_list[i]) == self.BDD.true:
                    final_val += (1 << i)
            return final_val
        else:
            for i in range(limit):
                if self.BDD.let(assignment, bdd_list[i]) == self.BDD.false:
                    final_val += (1 << i)
            return -final_val - 1
    
    def get_prob(self, target_list, result_list):
        """
        Flagship Probability Calculation: Supports 256+ qubits.
        1. Uses Integer Square Discrimination for [Exact Zero Check] to eliminate noise.
        2. Uses Decimal for [High Precision Calculation] to preserve tiny probabilities around 10^-78.
        """
        # 1. Construct constraints & 2. Apply constraints (unchanged)
        bool_list = [self.BDD.false, self.BDD.true]
        constraint_dict = {}
        for t, r in zip(target_list, result_list):
            constraint_dict['q%d' % t] = bool_list[r]

        res_Fa = [self.BDD.let(constraint_dict, f) for f in self.Fa]
        res_Fb = [self.BDD.let(constraint_dict, f) for f in self.Fb]
        res_Fc = [self.BDD.let(constraint_dict, f) for f in self.Fc]
        res_Fd = [self.BDD.let(constraint_dict, f) for f in self.Fd]

        # 3. Determine unmeasured variables (unchanged)
        all_qubits = set(range(self.n))
        measured_qubits = set(target_list)
        unmeasured_indices = list(all_qubits - measured_qubits)
        n_vars = len(unmeasured_indices) 
        
        # 4. Symbolically calculate terms for modulus squared (unchanged)
        # Returns Python large integers, infinite precision, no overflow
        aa = self._symbolic_inner_product(res_Fa, res_Fa, n_vars)
        bb = self._symbolic_inner_product(res_Fb, res_Fb, n_vars)
        cc = self._symbolic_inner_product(res_Fc, res_Fc, n_vars)
        dd = self._symbolic_inner_product(res_Fd, res_Fd, n_vars)
        
        ab = self._symbolic_inner_product(res_Fa, res_Fb, n_vars)
        bc = self._symbolic_inner_product(res_Fb, res_Fc, n_vars)
        cd = self._symbolic_inner_product(res_Fc, res_Fd, n_vars)
        ad = self._symbolic_inner_product(res_Fa, res_Fd, n_vars)

        # 5. Combine results
        # Total = (term_int + sqrt(2) * term_sqrt) / 2^k
        term_int = aa + bb + cc + dd
        term_sqrt = ab + bc + cd - ad
        
        # =========================================================
        # Core Improvement A: Exact Zero Check
        # =========================================================
        # We want to know if term_int + sqrt(2)*term_sqrt is strictly 0.
        # i.e., check if term_int equals -sqrt(2)*term_sqrt
        # Square both sides: term_int^2 == 2 * term_sqrt^2
        # This is a pure integer comparison, zero error!
        
        is_zero = False
        if term_int == 0 and term_sqrt == 0:
            is_zero = True
        elif (term_int * term_sqrt < 0) and (term_int**2 == 2 * (term_sqrt**2)):
            # If signs are opposite and square satisfies 2x relationship, it's exact cancellation
            is_zero = True
            
        if is_zero:
            return 0.0

        # =========================================================
        # Core Improvement B: High Precision Calculation (Decimal)
        # =========================================================
        # If not 0, we need to calculate its value.
        # For 256 qubits, result is around 1e-78.
        # Standard float precision is insufficient when term_int and term_sqrt are large.
        
        # Use Decimal to calculate sqrt(2)
        sqrt2_dec = Decimal(2).sqrt()
        
        # Numerator
        numerator = Decimal(term_int) + sqrt2_dec * Decimal(term_sqrt)
        
        # Denominator 2^k
        # Note: self.k can be large for 256 qubits, use 1<<self.k for large integer
        divisor = Decimal(1 << self.k)
        
        # High precision division
        total_prob_dec = numerator / divisor
        
        # Convert back to float for user
        # Python float can represent 1e-308, so 1e-78 is safe
        # As long as calculation uses Decimal for precision, result is accurate
        return abs(float(total_prob_dec))

    def _symbolic_inner_product(self, list1, list2, n_vars):
        """
        Calculates inner product of two integer vector BDDs.

        Model counts are accumulated as Python integers.  ``dd.cudd.count``
        returns a C ``double`` and silently rounds counts above 2**53, so it
        cannot be used on the large supports targeted by QSeqSim.
        """
        total = 0
        r = self.r
        
        # Pre-compute weights
        weights = []
        for i in range(r - 1):
            weights.append(1 << i)
        weights.append(-(1 << (r - 1))) 

        for i in range(r):
            for j in range(r):
                and_node = list1[i] & list2[j]
                
                # If intersection is empty, skip
                if and_node == self.BDD.false:
                    continue
                
                # Count over the node's support exactly.  The CUDD wrapper's
                # public count API returns float and loses integer precision
                # for sufficiently large model sets.
                raw_count = self._exact_model_count(and_node)

                supp = self.BDD.support(and_node)
                len_supp = len(supp)

                # Manually calculate the scaling factor.
                # n_vars is the logical number of remaining free qubits
                # diff is the number of free qubits existing but not used in BDD, each contributes 2x paths
                diff = n_vars - len_supp

                if diff < 0:
                    raise ValueError(
                        "BDD support contains more variables than the logical "
                        f"free-qubit count ({len_supp} > {n_vars})."
                    )

                # Bit shift equivalent to multiplying by 2^shift
                real_count = raw_count << diff
                
                # Accumulate
                total += weights[i] * weights[j] * real_count
                    
        return total

    def _exact_model_count(self, node):
        """Return the exact number of models over ``node``'s support.

        CUDD stores complemented edges and may skip variable levels.  This
        iterative post-order traversal accounts for both while keeping every
        count as a Python integer.  Automatic reordering is temporarily
        disabled so levels remain stable for the duration of the traversal,
        then the manager's original configuration is restored.
        """
        support_size = len(self.BDD.support(node))
        if support_size == 0:
            return 0 if node == self.BDD.false else 1

        variable_count = len(self.BDD.vars)
        reordering_was_enabled = self.BDD.configure(reordering=False)["reordering"]
        try:
            memo = {self.BDD.false: 0, self.BDD.true: 1}
            stack = [(node, False)]

            while stack:
                current, expanded = stack.pop()
                if current in memo:
                    continue

                level, low, high = self.BDD.succ(current)
                if current.negated:
                    low = ~low
                    high = ~high

                if not expanded:
                    stack.append((current, True))
                    if low not in memo:
                        stack.append((low, False))
                    if high not in memo:
                        stack.append((high, False))
                    continue

                low_level = min(low.level, variable_count)
                high_level = min(high.level, variable_count)
                low_gap = low_level - level - 1
                high_gap = high_level - level - 1
                memo[current] = (memo[low] << low_gap) + (memo[high] << high_gap)

            root_count = memo[node] << node.level
            unused_variable_count = variable_count - support_size
            return root_count >> unused_variable_count
        finally:
            self.BDD.configure(reordering=reordering_was_enabled)
  
    def _get_value_from_list(self, bdd_list):
        """
        [New Helper Function]
        Calculates integer value directly from collapsed (let-constrained) BDD list.
        Replaces original get_value function, no need to introduce x variables, extremely fast.
        """
        # 1. Determine sign bit (highest bit)
        # In logic, last bit is sign: True for negative, False for positive
        is_negative = (bdd_list[-1] == self.BDD.true)

        final_val = 0
        
        # 2. Restore value based on sign logic
        if not is_negative:
            # Positive number: accumulate bits that are True
            for i in range(self.r - 1):
                if bdd_list[i] == self.BDD.true:
                    final_val += (1 << i)
            return final_val
        else:
            # Negative number: accumulate bits that are False (0), then invert and subtract 1
            # Corresponds to: -sum([(1 << i) if binary_list[i] == 0 ...]) - 1
            for i in range(self.r - 1):
                if bdd_list[i] == self.BDD.false: 
                    final_val += (1 << i)
            return -final_val - 1

    def simplify_tail(self):
        if self.Fa[0] == self.BDD.false and self.Fb[0] == self.BDD.false and self.Fc[0] == self.BDD.false and self.Fd[
            0] == self.BDD.false:
            self.Fa = self.Fa[1:]
            self.Fb = self.Fb[1:]
            self.Fc = self.Fc[1:]
            self.Fd = self.Fd[1:]
            self.k -= 2
        self.r = len(self.Fd)

    def simplify_overflow(self):
        if self.Fa[-1] == self.Fa[-2] and self.Fb[-1] == self.Fb[-2] and self.Fc[-1] == self.Fc[-2] and self.Fd[-1] == \
                self.Fd[-2]:
            self.Fa.pop()
            self.Fb.pop()
            self.Fc.pop()
            self.Fd.pop()

    def signed_extend(self, length):
        for i in range(length):
            self.Fa.append(self.Fa[-1])
            self.Fb.append(self.Fb[-1])
            self.Fc.append(self.Fc[-1])
            self.Fd.append(self.Fd[-1])
        self.r += length

    def print_bdd(self):
        """
            Only can be used when import autoref instead of cudd!
        """
        print("Fa:")
        for i in range(len(self.Fa)):
            print(self.Fa[i].to_expr())
        print("Fb:")
        for i in range(len(self.Fb)):
            print(self.Fb[i].to_expr())
        print("Fc:")
        for i in range(len(self.Fc)):
            print(self.Fc[i].to_expr())
        print("Fd:")
        for i in range(len(self.Fd)):
            print(self.Fd[i].to_expr())

    def print_state_vec(self):
        for i in range(1 << self.n):
            print("The amplitude of |%s> is" % bin(i)[2:].zfill(self.n), self.get_amplitude(i), end='.\n')


class BDDSeqSim:
    def __init__(self, n, m, r):
        """
            n represents the number of all qubits
            m represents the number of input qubits
        """
        self.comb_bdd = BDDCombSim(n, r)
        self.stored_bdd = BDDCombSim(m, r)
        self.input_bdd = BDDCombSim(n - m, r)
        self.n = n
        self.m = m
        self.r = r
        self.k = 0
        self.prob_list = []

    def init_stored_state_by_basis(self, basis):
        assert basis < (1 << self.m), "Basis state is out of range!"
        tmp = dict()
        for i in range(self.m):
            tmp['q%d' % i] = bool((basis >> (self.m - 1 - i)) & 1)
        self.stored_bdd.Fd[0] = self.stored_bdd.BDD.cube(tmp)

    def init_stored_state_by_bdd(self, bdd):
        self.stored_bdd = bdd

    def init_input_state_by_basis(self, basis):
        num = self.n - self.m
        assert basis < (1 << num), "Basis state is out of range!"
        tmp = dict()
        for i in range(num):
            tmp['q%d' % i] = bool((basis >> (num - 1 - i)) & 1)
        self.input_bdd.Fd[0] = self.input_bdd.BDD.cube(tmp)

    # def init_input_state_by_bdd(self, bdd):
    #     self.input_bdd = bdd

    def init_comb_bdd(self):
        """
            input_bdd and stored_bdd should be initialized before calling this function.
            comb_bdd is the tensor product of the input_bdd and stored_bdd.
        """
        # TODO: the case of different r needs to be tested, now they are always the same.
        if self.input_bdd.r > self.stored_bdd.r:
            self.stored_bdd.signed_extend(self.input_bdd.r - self.stored_bdd.r)
        elif self.input_bdd.r < self.stored_bdd.r:
            self.input_bdd.signed_extend(self.stored_bdd.r - self.input_bdd.r)
        self.comb_bdd = BDDCombSim(self.n, self.stored_bdd.r)

        def tensor(x, y):
            tmpx = self.input_bdd.BDD.copy(x, self.comb_bdd.BDD)
            tmpy = self.stored_bdd.BDD.copy(y, self.comb_bdd.BDD)
            tmpd = dict()
            for i in range(self.m):
                tmpd['q%d' % i] = 'q%d' % (i + self.n - self.m)
            tmpy = self.comb_bdd.BDD.let(tmpd, tmpy)
            return tmpx & tmpy

        for i in range(self.comb_bdd.r):
            # Because input_bdd is represented by a basis state, it only has Fd[0].
            self.comb_bdd.Fa[i] = tensor(self.input_bdd.Fd[0], self.stored_bdd.Fa[i])
            self.comb_bdd.Fb[i] = tensor(self.input_bdd.Fd[0], self.stored_bdd.Fb[i])
            self.comb_bdd.Fc[i] = tensor(self.input_bdd.Fd[0], self.stored_bdd.Fc[i])
            self.comb_bdd.Fd[i] = tensor(self.input_bdd.Fd[0], self.stored_bdd.Fd[i])
        self.comb_bdd.k = self.stored_bdd.k
        self.r = self.comb_bdd.r
        self.k = self.comb_bdd.k

    def X(self, target):
        self.comb_bdd.X(target)

    def Y(self, target):
        self.comb_bdd.Y(target)

    def Z(self, target):
        self.comb_bdd.Z(target)

    def H(self, target):
        self.comb_bdd.H(target)

    def S(self, target):
        self.comb_bdd.S(target)

    def T(self, target):
        self.comb_bdd.T(target)

    def X2P(self, target):
        self.comb_bdd.X2P(target)

    def Y2P(self, target):
        self.comb_bdd.Y2P(target)

    def CNOT(self, control, target):
        self.comb_bdd.CNOT(control, target)

    def SWAP(self, target1, target2):
        self.comb_bdd.SWAP(target1, target2)

    def CZ(self, control, target):
        self.comb_bdd.CZ(control, target)

    def Toffoli(self, control1, control2, target):
        self.comb_bdd.Toffoli(control1, control2, target)

    def Fredkin(self, control, target1, target2):
        self.comb_bdd.Fredkin(control, target1, target2)

    def cwalk(self, control, targets):
        self.comb_bdd.cwalk(control, targets)

    def multi_controlled_X(self, controls, target):
        self.comb_bdd.multi_controlled_X(controls, target)

    def mid_measure(self, target_list, result_list):
        self.comb_bdd.mid_measure(target_list, result_list)

    def reset(self, target):
        self.comb_bdd.reset(target)

    def measure(self, result_list):
        
        l = len(result_list)
        assert l == self.n - self.m, "The length of result list is wrong!"
        self.prob_list.append(self.comb_bdd.get_prob(list(range(l)), result_list))
        d = {'q%d' % j: bool(result_list[j]) for j in range(l)}
        for i in range(self.comb_bdd.r):
            self.comb_bdd.Fa[i] = self.comb_bdd.BDD.let(d, self.comb_bdd.Fa[i])
            self.comb_bdd.Fb[i] = self.comb_bdd.BDD.let(d, self.comb_bdd.Fb[i])
            self.comb_bdd.Fc[i] = self.comb_bdd.BDD.let(d, self.comb_bdd.Fc[i])
            self.comb_bdd.Fd[i] = self.comb_bdd.BDD.let(d, self.comb_bdd.Fd[i])
        self.comb_bdd.simplify_tail()
        self.stored_bdd = BDDCombSim(self.m, self.comb_bdd.r)
        self.stored_bdd.k = self.comb_bdd.k

        def update(x):
            tmpd = dict()
            for i in range(self.m):
                tmpd['q%d' % (i + self.n - self.m)] = 'q%d' % i
            x = self.comb_bdd.BDD.let(tmpd, x)
            return self.comb_bdd.BDD.copy(x, self.stored_bdd.BDD)

        for i in range(self.comb_bdd.r):
            self.stored_bdd.Fa[i] = update(self.comb_bdd.Fa[i])
            self.stored_bdd.Fb[i] = update(self.comb_bdd.Fb[i])
            self.stored_bdd.Fc[i] = update(self.comb_bdd.Fc[i])
            self.stored_bdd.Fd[i] = update(self.comb_bdd.Fd[i])

        self.r = self.stored_bdd.r
        self.k = self.stored_bdd.k

    def get_step_prob(self):
        if len(self.prob_list) == 1:
            return self.prob_list[-1]
        else:
            return self.prob_list[-1] / self.prob_list[-2]

    def print_stored_state_vec(self):
        for i in range(1 << self.m):
            print("The amplitude of |%s> is" % bin(i)[2:].zfill(self.m),
                  self.stored_bdd.get_amplitude(i) / sqrt(self.prob_list[-1]), end='.\n')
