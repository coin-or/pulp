"""Unit tests for pyglpk solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpMaximize, LpProblem, LpSolveStatus
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
)


class PYGLPKTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.PYGLPK
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
    }

    def test_solver_params(self):
        # the extra options are fields of glp_smcp (simplex) or glp_iocp (MIP)
        prob = LpProblem("params", LpMaximize)
        xs = [prob.add_variable(f"x{j}", 0, 10) for j in range(6)]
        prob += sum((j + 1) * x for j, x in enumerate(xs))
        for k in range(4):
            prob += sum((j + k) % 3 * x for j, x in enumerate(xs)) <= 10 + k, f"c{k}"
        stats = prob.solve(solvers.PYGLPK(msg=False, it_lim=1))
        self.assertIsNot(stats.status, LpSolveStatus.Optimal)
        stats = prob.solve(solvers.PYGLPK(msg=False, mip_gap=0.1))
        self.assertIs(stats.status, LpSolveStatus.Optimal)

        with self.assertRaises(AttributeError):
            prob.solve(solvers.PYGLPK(msg=False, not_a_param=1))
