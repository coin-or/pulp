"""Unit tests for scip_cmd solver."""

import os
import tempfile
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
    pulpTestCheck,
)


class SCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.SCIP_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("NotSolved", "Undefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(okstatus=_status("NotSolved", "Undefined")),
    }

    def setup_test_dual_variables_reduced_costs(self, prob: LpProblem) -> None:
        self.solver.optionsDict["duals"] = True

    def _duals_problem(self, sense):
        prob = LpProblem(self._testMethodName, sense)
        x = prob.add_variable("x", 0, 5)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        sign = 1 if sense == const.LpMinimize else -1
        prob += sign * (x + 4 * y + 9 * z), "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        return prob, x, y, z

    def test_dual_variables_reduced_costs_maximize(self):
        prob, x, y, z = self._duals_problem(const.LpMaximize)
        self.solver.optionsDict["duals"] = True
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            sol={x: 4, y: -1, z: 6},
            reducedcosts={x: 0, y: -12, z: 0},
            duals={"c1": 0, "c2": -1, "c3": -8},
        )

    def test_duals_not_computed_by_default(self):
        prob, x, y, z = self._duals_problem(const.LpMinimize)
        prob.solve(self.solver)
        self.assertIsNone(x.dj)
        self.assertTrue(all(c.pi is None for c in prob.constraints()))

    def setup_test_options_parsing_SCIP_HIGHS(self, prob: LpProblem) -> None:
        self.solver.options = ["limits/time", 20]  # ty: ignore[invalid-assignment]

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

    def test_readduals(self):
        log = (
            "objective value: -54\n"
            "written solution information to file <old.sol>\n\n"
            "c1 7\n\n"
            "written solution information to file <a.sol>\n\n\n"
            "c2 -1\n"
            "c3 -8\n\n\n"
            "SCIP> quit\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write(log)
        try:
            self.assertEqual(
                solvers.SCIP_CMD.readduals(f.name, "a.sol"), {"c2": -1.0, "c3": -8.0}
            )
            self.assertEqual(solvers.SCIP_CMD.readduals(f.name, "missing.sol"), {})
        finally:
            os.remove(f.name)
