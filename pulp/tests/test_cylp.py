"""Unit tests for cylp solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpMaximize, LpMinimize, LpProblem, LpSolveStatus, const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
)


class CYLPTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CYLP
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_sequential_solve": PulpTestConfig(skip=False),
    }

    def test_best_bound(self):
        # 3x + 2y peaks at 18 on (4, 3); the constant must be part of the bound, as it
        # is of the objective
        for sense in (LpMaximize, LpMinimize):
            with self.subTest(sense=sense):
                prob = LpProblem("best_bound", sense)
                x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
                y = prob.add_variable("y", 0, 10, cat=const.LpInteger)
                prob += -sense * (3 * x + 2 * y) + 5, "obj"
                prob += x + y <= 7, "c1"
                prob += x - y <= 2, "c2"
                stats = prob.solve(self.solver)
                self.assertIs(stats.status, LpSolveStatus.Optimal)
                assert stats.objective is not None and stats.best_bound is not None
                self.assertAlmostEqual(stats.objective, -sense * 18 + 5, places=4)
                self.assertAlmostEqual(stats.best_bound, stats.objective, places=4)

    def test_no_best_bound_for_an_lp(self):
        prob = LpProblem("lp", LpMaximize)
        x = prob.add_variable("x", 0, 4)
        prob += x
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertIsNone(stats.best_bound)

    def test_options(self):
        # the options reach the CyLP model and the solve still succeeds
        prob = LpProblem("options", LpMaximize)
        x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
        y = prob.add_variable("y", 0, 10, cat=const.LpInteger)
        prob += 3 * x + 2 * y, "obj"
        prob += x + y <= 7, "c1"
        prob += x - y <= 2, "c2"
        solver = solvers.CYLP(msg=False, maxNodes=100, maxSolutions=10)
        stats = prob.solve(solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        model = prob.solverModel
        assert model is not None
        self.assertEqual(model.maximumNodes, 100)
        self.assertEqual(model.maximumSolutions, 10)

    def test_presolve_off(self):
        prob = LpProblem("presolve", LpMaximize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", 0, 3)
        prob += x + 2 * y, "obj"
        prob += x + y <= 5, "c1"
        stats = prob.solve(solvers.CYLP(msg=False, presolve=False))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert stats.objective is not None
        self.assertAlmostEqual(stats.objective, 8)
