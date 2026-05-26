"""Unit tests for gurobi solver."""

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
)


class GUROBITest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI
