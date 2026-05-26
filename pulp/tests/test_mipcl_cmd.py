"""Unit tests for mipcl_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.MIPCL_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible": PulpTestConfig(
            skip=True,
            skip_reason="MIPCL_CMD does not detect this infeasible case with MPS",
        ),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_relaxed_mip": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol={}),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
        "test_unbounded": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
    }
