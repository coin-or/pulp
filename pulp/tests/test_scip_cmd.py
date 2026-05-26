"""Unit tests for scip_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class SCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.SCIP_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
    }

    def setup_test_options_parsing_SCIP_HIGHS(self, prob: LpProblem) -> None:
        self.solver.options = ["limits/time", 20]

    def test_relaxed_mip(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0, None, const.LpInteger)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        self._apply_pulp_check(prob, sol={x: 3.0, y: -0.5, z: 7})
