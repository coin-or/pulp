"""Unit tests for sas94 solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    SASTest,
)


class SAS94Test(BaseSolverTest.PuLPTest, SASTest):
    solveInst = solvers.SAS94
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
    }
