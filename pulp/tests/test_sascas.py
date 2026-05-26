"""Unit tests for sascas solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    SASTest,
)


class SASCASTest(BaseSolverTest.PuLPTest, SASTest):
    solveInst = solvers.SASCAS
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
    }
