"""Unit tests for xpress_py solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
)


class XPRESS_PyTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.XPRESS_PY
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
    }
