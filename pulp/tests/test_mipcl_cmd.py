"""Unit tests for mipcl_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import constants as const
from pulp.tests.solver_common import (
    FAKE_SOLVER_ARGV_PREAMBLE,
    BaseSolverTest,
    PulpTestConfig,
    SolverCmdPathsWithSpacesTestCase,
    _status,
    write_fake_executable,
)


class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.MIPCL_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible": PulpTestConfig(
            skip=True,
            skip_reason="MIPCL_CMD does not detect this infeasible case with MPS",
        ),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_relaxed_mip": PulpTestConfig(okstatus=_status("Optimal"), sol={}),
        "test_unbounded": PulpTestConfig(okstatus=_status("Optimal")),
    }


FAKE_MIPCL = FAKE_SOLVER_ARGV_PREAMBLE + """\

sol = sys.argv[sys.argv.index("-solfile") + 1]
with open(sol, "w") as f:
    f.write("objective -4\\n")
    f.write("x 0\\n")
    f.write("y -1\\n")
"""


class MIPCL_CMDPathsWithSpacesTest(SolverCmdPathsWithSpacesTestCase):
    def test_paths_with_spaces(self):
        fake = write_fake_executable(self.spaced, "mipcl", FAKE_MIPCL)
        prob = self.build_problem()
        stats = prob.solve(
            solvers.MIPCL_CMD(
                path=fake, msg=False, timeLimit=30, options=["-threads 4"]
            )
        )
        # MIPCL solution files do not state optimality, so a completed
        # solve with a solution reads back as Stopped (see MIPCL_CMD.readsol)
        self.assertEqual(stats.status, const.LpSolveStatus.Stopped)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertTrue(argv[0].endswith("-pulp.mps"))
        sol = argv[argv.index("-solfile") + 1]
        self.assertTrue(sol.endswith("-pulp.sol"))
        self.assertEqual(argv[argv.index("-time") + 1], "30")
        # a multi-word option fragment keeps its historical tokenisation:
        # "-threads" and "4" are separate tokens, not one "-threads 4"
        self.assertNotIn("-threads 4", argv)
        self.assertEqual(argv[argv.index("-threads") + 1], "4")
