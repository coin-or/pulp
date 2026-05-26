"""Unit tests for pyglpk solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
)


class PYGLPKTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.PYGLPK
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
    }
