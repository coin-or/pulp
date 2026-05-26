"""Unit tests for copt solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class COPTTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COPT
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_unbounded": PulpTestConfig(
            okstatus=_status(
                "LpStatusInfeasible", "LpStatusUnbounded", "LpStatusUndefined"
            )
        ),
    }
