"""Unit tests for the GLOP solver."""

import os
import random
import tempfile
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpMaximize, LpMinimize, LpProblem, LpSolveStatus, const
from pulp.apis.core import PulpSolverError
from pulp.tests.solver_common import BaseSolverTest, PulpTestConfig

# shared tests on problems with integer variables, which GLOP refuses with
# mip=True (see test_mip_needs_mip_false)
_MIP_TESTS = {
    "test_api_steps",
    "test_decimal_815",
    "test_feasibility_only",
    "test_fixed_value",
    "test_initial_value",
    "test_integer_infeasible",
    "test_integer_infeasible_2",
    "test_mip",
    "test_mip_floats_objective",
    "test_stats_objective_sense_max",
    "test_stats_objective_sense_min",
}


def _random_lp(n: int = 60, m: int = 40) -> LpProblem:
    """A dense LP that takes GLOP a few dozen simplex iterations."""
    prob = LpProblem("random_lp", LpMaximize)
    xs = [prob.add_variable(f"x{j}", 0, 10) for j in range(n)]
    prob += sum(((j * 7) % 11 + 1) * x for j, x in enumerate(xs))
    for i in range(m):
        prob += sum(((i * j) % 13 + 1) * x for j, x in enumerate(xs)) <= 50, f"c{i}"
    return prob


def _covering_lp(rows: int = 200, cols: int = 400) -> LpProblem:
    """min cost covering: each column covers 5 random rows, each row >= 1.

    It takes GLOP a few hundred simplex iterations from scratch."""
    rng = random.Random(1)
    prob = LpProblem("covering", LpMinimize)
    xs = [prob.add_variable(f"x{j}", 0) for j in range(cols)]
    covers: list[list[int]] = [[] for _ in range(rows)]
    for j in range(cols):
        for i in rng.sample(range(rows), 5):
            covers[i].append(j)
    prob += sum(rng.uniform(1, 10) * x for x in xs)
    for i, members in enumerate(covers):
        prob += sum(xs[j] for j in members) >= 1, f"r{i}"
    return prob


def _iterations(prob: LpProblem) -> int:
    assert prob.solverModel is not None
    return prob.solverModel.result.solve_stats.simplex_iterations


class GLOPTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GLOP
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
    }

    def setUp(self):
        if self._testMethodName in _MIP_TESTS:
            self.skipTest("GLOP solves LPs only")
        super().setUp()

    def test_mip_needs_mip_false(self):
        prob = LpProblem("mip", LpMaximize)
        x = prob.add_variable("x", 0, 3.5, cat=const.LpInteger)
        prob += x
        with self.assertRaises(PulpSolverError):
            prob.solve(self.solver)
        stats = prob.solve(solvers.GLOP(msg=False, mip=False))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert x.varValue is not None
        self.assertAlmostEqual(x.varValue, 3.5)

    def test_maximize_with_constant(self):
        prob = LpProblem("max", LpMaximize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", 0, None)
        prob += 3 * x + 2 * y + 5
        prob += x + y <= 5, "c1"
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert stats.objective is not None
        self.assertAlmostEqual(stats.objective, 19)
        self.assertIsNone(stats.best_bound)

    def test_unbounded_and_infeasible(self):
        prob = LpProblem("unbounded", LpMaximize)
        x = prob.add_variable("x", 0)
        y = prob.add_variable("y", 0)
        prob += x + y
        prob += x - y <= 1, "c1"
        # presolve may only tell that the problem is infeasible or unbounded
        for presolve, okstatus in (
            (True, (LpSolveStatus.Unbounded, LpSolveStatus.Undefined)),
            (False, (LpSolveStatus.Unbounded,)),
        ):
            with self.subTest(presolve=presolve):
                stats = prob.solve(solvers.GLOP(msg=False, presolve=presolve))
                self.assertIn(stats.status, okstatus)
                self.assertFalse(stats.has_solution)

        prob = LpProblem("infeasible", LpMinimize)
        x = prob.add_variable("x", 0, 1)
        prob += x
        prob += x >= 2, "c1"
        for presolve, okstatus in (
            (True, (LpSolveStatus.Infeasible, LpSolveStatus.Undefined)),
            (False, (LpSolveStatus.Infeasible,)),
        ):
            with self.subTest(presolve=presolve):
                stats = prob.solve(solvers.GLOP(msg=False, presolve=presolve))
                self.assertIn(stats.status, okstatus)
                self.assertFalse(stats.has_solution)

    def test_iteration_limit(self):
        prob = _random_lp()
        stats = prob.solve(solvers.GLOP(msg=False, presolve=False, iteration_limit=2))
        self.assertIs(stats.status, LpSolveStatus.IterationLimit)

    def test_time_limit(self):
        prob = _random_lp()
        self.solver.timeLimit = 30
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert prob.solverModel is not None
        self.assertEqual(prob.solverModel.params.time_limit.total_seconds(), 30)

    def test_interrupter(self):
        from ortools.util.python.solve_interrupter import SolveInterrupter

        interrupter = SolveInterrupter()
        interrupter.interrupt()
        prob = _random_lp()
        stats = prob.solve(
            solvers.GLOP(msg=False, presolve=False, interrupter=interrupter)
        )
        self.assertIs(stats.status, LpSolveStatus.Interrupted)

    def test_msg_callback(self):
        lines: list[str] = []
        prob = _random_lp()
        stats = prob.solve(solvers.GLOP(msg=False), callback=lines.extend)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertTrue(lines)
        self.assertTrue(all(isinstance(line, str) for line in lines))

    def test_log_path_and_callback(self):
        lines: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "glop.log")
            _random_lp().solve(
                solvers.GLOP(msg=False, logPath=path), callback=lines.extend
            )
            with open(path) as f:
                self.assertEqual(f.read().splitlines(), lines)

    def test_solver_params(self):
        prob = _random_lp()
        solver = solvers.GLOP(
            msg=False,
            use_dual_simplex=True,
            primal_feasibility_tolerance=1e-9,
            lp_algorithm="primal_simplex",
            threads=1,
        )
        stats = prob.solve(solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert prob.solverModel is not None
        params = prob.solverModel.params
        self.assertTrue(params.glop.use_dual_simplex)
        self.assertEqual(params.threads, 1)

        with self.assertRaises(AttributeError):
            prob.solve(solvers.GLOP(msg=False, not_a_parameter=1))

    def test_result_and_basis(self):
        prob = _random_lp()
        prob.solve(self.solver)
        assert prob.solverModel is not None
        result = prob.solverModel.result
        self.assertTrue(result.has_basis())
        self.assertGreater(result.solve_stats.simplex_iterations, 0)

    def _cold(self, prob: LpProblem) -> tuple[float, int]:
        """Objective value and simplex iterations of a solve from scratch."""
        cold = prob.copy()
        stats = cold.solve(solvers.GLOP(msg=False, presolve=False))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert stats.objective is not None
        return stats.objective, _iterations(cold)

    def test_resolve_keeps_basis_when_rows_are_added(self):
        # column generation: new columns, and new rows the old solution satisfies.
        # MathOpt's incremental GLOP drops most of its basis on new rows, unless it
        # is handed back
        rng = random.Random(2)
        prob = _covering_lp()
        prob.solve(solvers.GLOP(msg=False, presolve=False))
        rows = prob.constraints()
        new = [
            prob.add_column(
                f"y{j}",
                0,
                None,
                obj=rng.uniform(1, 10),
                coefficients={row: 1 for row in rng.sample(rows, 5)},
            )
            for j in range(20)
        ]
        for k in range(5):
            prob += sum(new[k::5]) <= 3, f"cap{k}"
        stats = prob.resolve()
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        objective, cold_iterations = self._cold(prob)
        assert stats.objective is not None
        self.assertAlmostEqual(stats.objective, objective, places=6)
        self.assertLess(_iterations(prob), cold_iterations / 3)

    def test_resolve_after_upper_bound_changes(self):
        # fixed at 0, then free above, then fixed again: the statuses of the
        # previous basis must fit the new bounds
        prob = _covering_lp()
        xs = prob.variables()
        for x in xs[::3]:
            x.upBound = 0
        prob.solve(solvers.GLOP(msg=False, presolve=False))
        for up in (None, 0):
            with self.subTest(upBound=up):
                for x in xs[::3]:
                    x.upBound = up
                stats = prob.resolve()
                self.assertIs(stats.status, LpSolveStatus.Optimal)
                objective, _ = self._cold(prob)
                assert stats.objective is not None
                self.assertAlmostEqual(stats.objective, objective, places=6)

    def test_resolve_after_rebuild(self):
        # an integer variable cannot be replayed (the rebuild refuses it); the
        # model built next has new MathOpt objects, so no basis may be carried over
        prob = _covering_lp(rows=40, cols=80)
        prob.solve(self.solver)
        model = prob.solverModel
        x = prob.variables()[0]
        x.cat = const.LpInteger
        with self.assertRaises(PulpSolverError):
            prob.resolve()
        x.cat = const.LpContinuous
        prob += x <= 0.5, "cut"
        stats = prob.resolve()
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertIsNot(prob.solverModel, model)
        objective, _ = self._cold(prob)
        assert stats.objective is not None
        self.assertAlmostEqual(stats.objective, objective, places=6)
