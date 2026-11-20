"""Unit tests for gurobi_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    FAKE_SOLVER_ARGV_PREAMBLE,
    BaseSolverTest,
    PulpTestConfig,
    SolverCmdPathsWithSpacesTestCase,
    _status,
    write_fake_executable,
)


class GUROBI_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("NotSolved")),
        "test_infeasible_problem__is_not_valid": PulpTestConfig(
            okstatus=_status("NotSolved", "Infeasible", "Undefined")
        ),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_integer_infeasible": PulpTestConfig(okstatus=_status("NotSolved")),
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("NotSolved", "Undefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_unbounded": PulpTestConfig(okstatus=_status("NotSolved", "Undefined")),
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


FAKE_GUROBI = FAKE_SOLVER_ARGV_PREAMBLE + """\

sol = next(a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("ResultFile="))
with open(sol, "w") as f:
    f.write("# Objective value = -4\\n")
    f.write("x 0\\n")
    f.write("y -1\\n")
"""


class GUROBI_CMDPathsWithSpacesTest(SolverCmdPathsWithSpacesTestCase):
    def test_paths_with_spaces(self):
        fake = write_fake_executable(self.spaced, "gurobi_cl", FAKE_GUROBI)
        prob = self.build_problem()
        stats = prob.solve(solvers.GUROBI_CMD(path=fake, msg=False))
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertTrue(argv[-1].endswith("-pulp.lp"))
        self.assertIn(f"ResultFile={argv[-1].replace('.lp', '.sol')}", argv)
        # the capture log path (from LpSolver_CMD.capture_log) is not under
        # the spaced dir, but it must still arrive as one whole element
        log_args = [a for a in argv if a.startswith("LogFile=")]
        self.assertEqual(len(log_args), 1)
        self.assertTrue(log_args[0].endswith("-pulp.log"))
        # with a time limit and a warm start, TimeLimit is a single
        # "key=value" token and InputFile= carries the whole spaced path
        prob = self.build_problem()
        prob.variables()[0].setInitialValue(1)
        stats = prob.solve(
            solvers.GUROBI_CMD(path=fake, msg=False, timeLimit=99, warmStart=True)
        )
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        argv = self.recorded_argv()[1]
        self.assert_paths_not_split(argv)
        self.assertIn("TimeLimit=99", argv)
        input_args = [a for a in argv if a.startswith("InputFile=")]
        self.assertEqual(len(input_args), 1)
        self.assertTrue(input_args[0].split("=", 1)[1].startswith(self.spaced))
        self.assertTrue(input_args[0].endswith("-pulp.mst"))
