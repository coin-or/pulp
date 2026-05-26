"""Unit tests for yaposib solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class YAPOSIBTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.YAPOSIB
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(
            okstatus=_status(
                "LpStatusInfeasible", "LpStatusUnbounded", "LpStatusUndefined"
            )
        ),
    }
