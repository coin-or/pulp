"""Unit tests for mosek solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class MOSEKTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.MOSEK
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_integer_infeasible": PulpTestConfig(
            okstatus=_status("LpStatusInfeasible", "LpStatusUndefined")
        ),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
        "test_unbounded": PulpTestConfig(
            okstatus=_status(
                "LpStatusInfeasible", "LpStatusUnbounded", "LpStatusUndefined"
            )
        ),
    }
