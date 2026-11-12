"""Unit tests for fscip_cmd solver."""

import unittest
from typing import ClassVar
from unittest import mock

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class FSCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.FSCIP_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("NotSolved")),
        "test_infeasible_problem__is_not_valid": PulpTestConfig(
            okstatus=_status("NotSolved", "Infeasible", "Undefined")
        ),
        "test_integer_infeasible": PulpTestConfig(okstatus=_status("NotSolved")),
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("NotSolved", "Undefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="FSCIP_CMD unbounded handling is inconsistent",
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
        self.solver.mip = False
        self._apply_pulp_check(prob, sol={x: 3.0, y: -0.5, z: 7})


class FSCIP_CMDParameterTest(unittest.TestCase):
    def _run_actual_solve_capturing_prm(self, time_limit: float | None) -> str:
        prob = LpProblem("fscip_param_test", const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        prob += x
        prob += x >= 1

        solver = solvers.FSCIP_CMD(path="fscip", timeLimit=time_limit, msg=False)
        captured_prm: list[str] = []

        def fake_check_call(cmd: list[str], **kwargs: object) -> int:
            prm_path = cmd[1]
            with open(prm_path) as f:
                captured_prm.append(f.read())
            sol_path = cmd[cmd.index("-fsol") + 1]
            with open(sol_path, "w") as f:
                f.write("")
            return 0

        with (
            mock.patch.object(solver, "executable", return_value=True),
            mock.patch("subprocess.check_call", side_effect=fake_check_call),
            mock.patch.object(
                solver,
                "readsol",
                return_value=(const.LpSolveStatus.Optimal, {"x": 1.0}),
            ),
        ):
            solver.actualSolve(prob)

        self.assertEqual(len(captured_prm), 1)
        return captured_prm[0]

    def test_timelimit_written_to_prm_file(self) -> None:
        prm_contents = self._run_actual_solve_capturing_prm(time_limit=60)
        self.assertIn("TimeLimit = 60", prm_contents)

    def test_no_timelimit_omitted_from_prm_file(self) -> None:
        prm_contents = self._run_actual_solve_capturing_prm(time_limit=None)
        self.assertNotIn("TimeLimit", prm_contents)
