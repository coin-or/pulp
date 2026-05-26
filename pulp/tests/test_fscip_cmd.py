"""Unit tests for fscip_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class FSCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.FSCIP_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("LpStatusNotSolved")),
        "test_infeasible_problem__is_not_valid": PulpTestConfig(
            okstatus=_status(
                "LpStatusNotSolved", "LpStatusInfeasible", "LpStatusUndefined"
            )
        ),
        "test_integer_infeasible": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved")
        ),
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
        "test_relaxed_mip": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol={}),
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="FSCIP_CMD unbounded handling is inconsistent",
        ),
    }
