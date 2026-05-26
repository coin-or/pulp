"""Unit tests for coinmp_dll solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class COINMP_DLLTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COINMP_DLL
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_integer_infeasible": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
        "test_sequential_solve": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
    }
