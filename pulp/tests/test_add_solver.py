import unittest

from pulp import LpSolver, apis
from pulp.apis import addSolver, getSolver, listSolvers


class SolverAvailable(LpSolver):
    name = "SOLVER_AVAILABLE"

    def available(self):
        return True


class SolverNotAvailable(LpSolver):
    name = "SOLVER_NOT_AVAILABLE"

    def available(self):
        return False


class SolverShadow(LpSolver):
    name = "COIN_CMD"

    def available(self):
        return True


class TestAddSolver(unittest.TestCase):
    def test_add_solver(self):
        _all_solvers = apis._all_solvers.copy()

        old = listSolvers()
        addSolver(SolverAvailable, SolverNotAvailable)
        new = listSolvers()

        self.assertEqual(len(old) + 2, len(new))

        apis._all_solvers = _all_solvers

    def test_add_solver_unavailable(self):
        _all_solvers = apis._all_solvers.copy()

        old = listSolvers(onlyAvailable=True)
        addSolver(SolverAvailable, SolverNotAvailable)
        new = listSolvers(onlyAvailable=True)

        self.assertEqual(len(old) + 1, len(new))

        apis._all_solvers = _all_solvers

    def test_add_solver_shadow(self):
        _all_solvers = apis._all_solvers.copy()

        old = getSolver(SolverShadow.name)
        addSolver(SolverShadow)
        new = getSolver(SolverShadow.name)

        self.assertIsNot(old, new)

        apis._all_solvers = _all_solvers
