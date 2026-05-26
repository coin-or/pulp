"""Unit tests for cuopt solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class CUOPTTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CUOPT
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusInfeasible", "LpStatusUndefined")
        ),
        "test_unbounded": PulpTestConfig(
            okstatus=_status("LpStatusUnbounded", "LpStatusUndefined")
        ),
    }
