"""Unit tests for choco_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class CHOCO_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CHOCO_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible": PulpTestConfig(
            skip=True,
            skip_reason="CHOCO_CMD does not detect this infeasible case with MPS",
        ),
        "test_relaxed_mip": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol={}),
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="CHOCO_CMD bounds all variables; unbounded status not returned",
        ),
    }
