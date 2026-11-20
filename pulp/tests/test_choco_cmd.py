"""Unit tests for choco_cmd solver."""

import os
from typing import ClassVar
from unittest import mock

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


class CHOCO_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CHOCO_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible": PulpTestConfig(
            skip=True,
            skip_reason="CHOCO_CMD does not detect this infeasible case with MPS",
        ),
        "test_relaxed_mip": PulpTestConfig(okstatus=_status("Optimal"), sol={}),
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="CHOCO_CMD bounds all variables; unbounded status not returned",
        ),
    }


FAKE_JAVA = FAKE_SOLVER_ARGV_PREAMBLE + """\

print("s OPTIMUM FOUND")
print("x 0")
print("y -1")
"""


class CHOCO_CMDPathsWithSpacesTest(SolverCmdPathsWithSpacesTestCase):
    def test_paths_with_spaces(self):
        write_fake_executable(self.spaced, "java", FAKE_JAVA)
        jar = os.path.join(self.spaced, "choco parser.jar")
        with open(jar, "w") as f:
            f.write("")
        prob = self.build_problem()
        with mock.patch.dict(
            os.environ, {"PATH": self.spaced + os.pathsep + os.environ["PATH"]}
        ):
            stats = prob.solve(
                solvers.CHOCO_CMD(
                    path=jar, msg=False, timeLimit=60, options=[("-fs", "1")]
                )
            )
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertEqual(argv[argv.index("-cp") + 1], jar)
        self.assertTrue(argv[-1].endswith("-pulp.mps"))
        # the time limit is the token after -limit, and each option
        # key/value pair arrives as two separate tokens
        self.assertEqual(argv[argv.index("-limit") + 1], "[-60s]")
        self.assertEqual(argv[argv.index("-fs") + 1], "1")
