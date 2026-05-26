"""Unit tests for xpress_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
)


class XPRESS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.XPRESS_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
    }
