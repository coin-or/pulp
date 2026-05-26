"""Unit tests for gurobi solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
)


class GUROBITest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
    }
