"""Unit tests for highs_cmd solver."""

import sys
import unittest
from typing import ClassVar
from unittest import mock

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
)


class HiGHS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.HiGHS_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="HiGHS_CMD unbounded handling is inconsistent",
        ),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
    }

    def setup_test_options_parsing_SCIP_HIGHS(self, prob: LpProblem) -> None:
        self.solver.options = ["time_limit", 20]  # ty: ignore[invalid-assignment]

    @unittest.skipIf(sys.platform == "win32", "Windows fails for whatever reason")
    def test_relaxed_mip(self):
        super().test_relaxed_mip()


class HiGHS_CMDLogParsingTest(unittest.TestCase):
    def test_missing_status_in_log_does_not_raise_indexerror(self) -> None:
        prob = LpProblem("test_highs_log", const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        prob += x
        prob += x >= 1

        solver = solvers.HiGHS_CMD(path="highs", msg=False)

        def fake_popen(cmd: list[str], **kwargs: object) -> mock.MagicMock:
            # Parse log_file from options file
            options_arg = [arg for arg in cmd if arg.startswith("--options_file=")][0]
            options_path = options_arg.split("=", 1)[1]
            with open(options_path) as f:
                for line in f:
                    if line.startswith("log_file="):
                        log_path = line.strip().split("=", 1)[1]
                        with open(log_path, "w") as log_f:
                            log_f.write("Running HiGHS 1.5.0\nExecution terminated\n")
            proc = mock.MagicMock()
            proc.wait.return_value = 0
            return proc

        with (
            mock.patch.object(solver, "executable", return_value=True),
            mock.patch("subprocess.Popen", side_effect=fake_popen),
        ):
            stats = solver.actualSolve(prob)

        self.assertFalse(stats.has_solution)
        self.assertEqual(stats.status, const.LpSolveStatus.NotSolved)
