"""Unit tests for scip_py solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class SCIP_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.SCIP_PY
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
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
        self._apply_pulp_check("test_relaxed_mip", prob, sol={x: 3.0, y: -0.5, z: 7})
