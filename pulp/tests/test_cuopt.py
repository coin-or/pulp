"""Unit tests for cuopt solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class CUOPTTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CUOPT
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusInfeasible", "LpStatusUndefined")
        ),
        "test_unbounded": PulpTestConfig(
            okstatus=_status("LpStatusUnbounded", "LpStatusUndefined")
        ),
    }
