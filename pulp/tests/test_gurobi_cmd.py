"""Unit tests for gurobi_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class GUROBI_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("LpStatusNotSolved")),
        "test_infeasible_problem__is_not_valid": PulpTestConfig(
            okstatus=_status(
                "LpStatusNotSolved", "LpStatusInfeasible", "LpStatusUndefined"
            )
        ),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_integer_infeasible": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved")
        ),
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_unbounded": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
    }

    def test_relaxed_mip(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0, None, const.LpInteger)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        self.solver.mip = 0
        self._apply_pulp_check(prob, sol={x: 3.0, y: -0.5, z: 7})
