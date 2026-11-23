"""Unit tests for highs_cmd solver."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem, PulpSolverError, constants
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

    def test_external_options_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "highs.options"
            path.write_text("presolve=off\n", encoding="utf-8")

            problem = LpProblem("external_options", constants.LpMinimize)
            x = problem.add_variable("x", lowBound=0)
            problem += x
            problem += x >= 1

            self.solver.options = [f"--options_file={path}"]
            result = problem.solve(self.solver)

            self.assertEqual(result.status, constants.LpSolveStatus.Optimal)
            self.assertTrue(result.has_solution)
            self.assertAlmostEqual(x.varValue, 1.0)

    def test_external_options_file_rejects_output_override(self):
        """External files cannot override PuLP-managed output settings."""
        reserved_options = (
            "solution_file=external.sol",
            "log_file=external.log",
            "write_solution_to_file=false",
            "write_solution_style=1",
            "output_flag=false",
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "highs.options"

            for option in reserved_options:
                with self.subTest(option=option):
                    path.write_text(f"{option}\n", encoding="utf-8")

                    problem = LpProblem(
                        "external_options_conflict",
                        constants.LpMinimize,
                    )
                    x = problem.add_variable("x", lowBound=0)
                    problem += x
                    problem += x >= 1

                    self.solver.options = [f"--options_file={path}"]

                    with self.assertRaisesRegex(PulpSolverError, "managed internally"):
                        problem.solve(self.solver)
