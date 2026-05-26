"""Unit tests for glpk_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class GLPK_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GLPK_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("LpStatusUndefined")),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
    }

    def test_issue814_rounding_mip(self):
        """
        Test there is no rounding issue for MIP problems as described in #814
        """

        # bounds and constraints are formatted as .12g
        # see pulp.py asCplexLpVariable / asCplexLpConstraint methods
        ub = 999999999999

        assert int(format(ub, ".12g")) == ub
        assert float(format(ub + 2, ".12g")) != float(ub + 2)

        model = LpProblem("mip-814", const.LpMaximize)
        Q = model.add_variable("Q", cat="Integer", lowBound=0, upBound=ub)
        model += Q
        model += Q >= 0
        model.solve(self.solver)
        assert Q.value() == ub

    def test_issue814_rounding_lp(self):
        """
        Test there is no rounding issue for LP (simplex method) problems as described in #814
        """
        ub = 999999999999.0
        assert float(format(ub, ".12g")) == ub
        assert float(format(ub + 0.1, ".12g")) != ub + 0.1

        for simplex in ["primal", "dual"]:
            model = LpProblem(f"lp-814-{simplex}", const.LpMaximize)
            Q = model.add_variable("Q", lowBound=0, upBound=ub)
            model += Q
            model += Q >= 0
            self.solver.options.append("--" + simplex)
            model.solve(self.solver)
            self.solver.options = self.solver.options[:-1]
            assert Q.value() == ub

    def test_issue814_rounding_ipt(self):
        """
        Test there is no rounding issue for LP (interior point method) problems as described in #814
        """
        # this one is limited by GLPK int pt feasibility, not formatting
        ub = 12345678999.0

        model = LpProblem("ipt-814", const.LpMaximize)
        Q = model.add_variable("Q", lowBound=0, upBound=ub)
        model += Q
        model += Q >= 0
        self.solver.options.append("--interior")
        model.solve(self.solver)
        self.solver.options = self.solver.options[:-1]
        assert abs(Q.value() - ub) / ub < 1e-9
