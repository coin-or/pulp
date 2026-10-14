"""Unit tests for gurobi solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpInteger, LpMinimize, LpProblem
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
)


class GUROBITest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
    }

    def test_gap_params(self):
        prob = LpProblem(self._testMethodName, LpMinimize)
        x = prob.add_variable("x", 0, 4, LpInteger)
        y = prob.add_variable("y", -1, 1, LpInteger)
        prob += x + 4 * y
        prob += x + y >= 2
        prob.solve(solvers.GUROBI(msg=False, gapRel=0.1, gapAbs=5))
        assert prob.solverModel is not None
        params = prob.solverModel.Params
        self.assertAlmostEqual(params.MIPGap, 0.1)
        self.assertAlmostEqual(params.MIPGapAbs, 5)
