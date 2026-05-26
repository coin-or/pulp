"""Unit tests for xpress_py solver."""

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
)


class XPRESS_PyTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.XPRESS_PY
