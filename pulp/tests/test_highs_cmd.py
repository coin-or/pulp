"""Unit tests for highs_cmd solver."""

import sys
import unittest
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
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
        self.solver.options = ["time_limit", 20]

    @unittest.skipIf(sys.platform == "win32", "Windows fails for whatever reason")
    def test_relaxed_mip(self):
        super().test_relaxed_mip()
