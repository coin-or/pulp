"""
Tests for the statistics object every solve returns
"""

from __future__ import annotations

import glob
import json
import os
import random
import tempfile
import unittest
from typing import Any
from unittest import mock

from orloge.base import MIPProgressRow

import pulp.apis as solvers
from pulp import LpProblem, LpSolveStats, lpSum
from pulp import constants as const
from pulp.apis.core import clocks
from pulp.constants import LpSolveStatus
from pulp.core.lp_stats import dialect_for_solver, parse_logs


class SolveStatsTest(unittest.TestCase):
    """Tests for ``LpProblem.solve`` against the default solver."""

    def setUp(self):
        if solvers.LpSolverDefault is None:
            self.skipTest("no default solver available")
        self.solver = solvers.LpSolverDefault.copy()
        self.solver.msg = False

    def _problem(self):
        """min 3x + 2y  s.t.  x + y >= 5, x >= 2, x integer. Optimum is 12."""
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
        y = prob.add_variable("y", 0, 10)
        prob += x + y >= 5, "c1"
        prob += x >= 2, "c2"
        prob += 3 * x + 2 * y
        return prob

    def _solve(self, prob=None):
        prob = self._problem() if prob is None else prob
        return prob, prob.solve(self.solver)

    def test_returns_stats_object(self):
        _, stats = self._solve()
        self.assertIsInstance(stats, LpSolveStats)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertEqual(stats.status_str, "Optimal")
        self.assertIs(stats.has_solution, True)
        self.assertEqual(stats.solver, self.solver.name)
        self.assertAlmostEqual(stats.objective, 12, places=4)

    def test_solver_solve_returns_the_same_kind_of_stats(self):
        stats = self.solver.solve(self._problem())
        self.assertIsInstance(stats, LpSolveStats)
        self.assertIs(stats.status, LpSolveStatus.Optimal)

    def test_model_shape_recorded(self):
        prob, stats = self._solve()
        self.assertEqual(stats.num_variables, prob.numVariables())
        self.assertEqual(stats.num_constraints, prob.numConstraints())
        self.assertTrue(stats.is_mip)

    def test_timings_are_recorded(self):
        _, stats = self._solve()
        self.assertGreater(stats.time, 0)
        self.assertGreaterEqual(stats.cpu_time, 0)

    def test_the_problem_keeps_no_solve_state(self):
        prob, _ = self._solve()
        for name in ("stats", "status", "solutionTime", "bestBound", "assignStatus"):
            with self.subTest(attribute=name):
                self.assertFalse(hasattr(prob, name))
        self.assertNotIn("status", prob.toDict()["parameters"])
        self.assertNotIn("sol_status", prob.toDict()["parameters"])

    def test_each_solve_returns_its_own_stats(self):
        prob = self._problem()
        first = prob.solve(self.solver)
        second = prob.solve(self.solver)
        self.assertIsNot(first, second)

    def test_infeasible_problem_is_not_feasible(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        prob += x >= 8, "lo"
        prob += x <= 2, "hi"
        prob += x
        stats = prob.solve(self.solver)
        self.assertIn(stats.status, (LpSolveStatus.Infeasible, LpSolveStatus.Undefined))
        self.assertIs(stats.has_solution, False)

    def test_gap_is_zero_at_the_optimum(self):
        _, stats = self._solve()
        if stats.best_bound is None:
            self.skipTest(f"{self.solver.name} reports no bound")
        self.assertAlmostEqual(stats.gap_abs, 0, places=4)
        self.assertAlmostEqual(stats.gap_rel, 0, places=4)

    def test_toDict_holds_the_derived_values(self):
        _, stats = self._solve()
        data = stats.toDict()
        self.assertNotIn("logs", data)
        self.assertEqual(data["status"], LpSolveStatus.Optimal)
        self.assertIs(data["has_solution"], True)
        self.assertEqual(data["status_str"], "Optimal")
        self.assertEqual(data["solver"], self.solver.name)

    def test_toDict_can_include_the_raw_log(self):
        _, stats = self._solve()
        self.assertIn("logs", stats.toDict(logs=True))

    def test_toJson_roundtrips(self):
        _, stats = self._solve()
        filename = os.path.join(tempfile.mkdtemp(), "stats.json")
        try:
            stats.toJson(filename)
            with open(filename) as f:
                data = json.load(f)
        finally:
            os.remove(filename)
        self.assertEqual(data["status"], stats.status)
        self.assertEqual(data["solver"], stats.solver)
        self.assertNotIn("logs", data)

    def test_str_mentions_the_solver_and_status(self):
        _, stats = self._solve()
        text = str(stats)
        self.assertIn(self.solver.name, text)
        self.assertIn("Optimal", text)

    def test_solver_options_are_recorded(self):
        _, stats = self._solve()
        self.assertEqual(stats.solver_options["solver"], self.solver.name)

    def test_no_temp_log_is_left_behind(self):
        pattern = os.path.join(tempfile.gettempdir(), "*-pulp.log")
        before = set(glob.glob(pattern))
        self._solve()
        self.assertEqual(set(glob.glob(pattern)) - before, set())

    def test_a_user_log_path_is_kept(self):
        if dialect_for_solver(self.solver.name) is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        log_path = os.path.join(tempfile.mkdtemp(), "solver.log")
        solver = self.solver.copy()
        solver.optionsDict["logPath"] = log_path
        self._problem().solve(solver)
        self.assertTrue(os.path.isfile(log_path))
        os.remove(log_path)

    def test_logs_are_parsed_without_a_log_path(self):
        if dialect_for_solver(self.solver.name) is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        _, stats = self._solve()
        self.assertIsInstance(stats.logs, dict)
        self.assertIsNotNone(stats.solver_version)
        self.assertIsNotNone(stats.solver_status)
        self.assertIsNotNone(stats.solver_status_code)
        # a log this small carries no timing line, so solver_time may stay None
        self.assertIsNotNone(stats.matrix)
        self.assertIn("variables", stats.matrix)

    def test_best_bound_falls_back_to_the_log(self):
        if dialect_for_solver(self.solver.name) is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        _, stats = self._solve()
        # COIN_CMD reports no bound itself, so this can only come from the log
        self.assertAlmostEqual(stats.best_bound, 12, places=4)

    def test_sequential_solve_returns_one_stats_per_objective(self):
        prob = self._problem()
        x, y = prob.variables()
        results = prob.sequentialSolve([x + y, 3 * x + 2 * y], solver=self.solver)
        self.assertEqual(len(results), 2)
        for stats in results:
            self.assertIsInstance(stats, LpSolveStats)
            self.assertEqual(stats.solver, self.solver.name)
        self.assertIsNot(results[0], results[1])

    def test_resolve_returns_stats(self):
        prob = self._problem()
        prob.solve(self.solver)
        self.assertIsInstance(prob.resolve(), LpSolveStats)


class _StubSolver(solvers.LpSolver):
    """Reports a fixed outcome without solving anything."""

    name = "Stub"

    def __init__(
        self,
        status: int = LpSolveStatus.Optimal,
        # Any, so tests can hand buildStats values it must reject
        has_solution: Any = True,
        best_bound: float | None = None,
    ):
        super().__init__(msg=False)
        self.status = status
        self.has_solution = has_solution
        self.best_bound = best_bound

    def actualSolve(self, lp, **kwargs):
        start = clocks()
        return self.buildStats(
            lp,
            self.status,
            self.has_solution,
            start=start,
            best_bound=self.best_bound,
        )


class BuildStatsTest(unittest.TestCase):
    """Tests for ``LpSolver.buildStats``, the one place LpSolveStats is built."""

    _LOG = {
        "version": "2.10.3",
        "status": "Stopped on time limit",
        "status_code": -4,
        "sol_code": 2,
        "time": 1.25,
        "gap": 0.1,
        "nodes": 42,
        "rootTime": 0.5,
        "matrix": {"constraints": 3, "variables": 2},
        "best_solution": 12.0,
        "best_bound": 11.0,
    }

    def _problem(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        prob += x >= 1, "c1"
        prob += x
        return prob

    def _solve(self, solver, log=None):
        with mock.patch("pulp.core.lp_stats.parse_logs", return_value=log):
            return self._problem().solve(solver)

    def test_records_the_solver_outcome(self):
        stats = self._solve(_StubSolver(LpSolveStatus.TimeLimit, True, best_bound=4.0))
        self.assertIs(stats.status, LpSolveStatus.TimeLimit)
        self.assertIs(stats.has_solution, True)
        self.assertEqual(stats.best_bound, 4.0)
        self.assertEqual(stats.solver, "Stub")
        self.assertEqual(stats.num_variables, 1)
        self.assertEqual(stats.num_constraints, 1)
        self.assertIs(stats.is_mip, False)
        self.assertIsNone(stats.logs)

    def test_accepts_plain_integer_codes(self):
        stats = self._solve(_StubSolver(-1, False))
        self.assertIs(stats.status, LpSolveStatus.Infeasible)

    def test_rejects_unknown_status_codes(self):
        with self.assertRaises(const.PulpError):
            self._solve(_StubSolver(99, False))

    def test_rejects_a_non_bool_has_solution(self):
        with self.assertRaises(const.PulpError):
            self._solve(_StubSolver(LpSolveStatus.Optimal, 1))

    def test_log_values_are_exposed(self):
        stats = self._solve(_StubSolver(LpSolveStatus.TimeLimit, True), self._LOG)
        self.assertEqual(stats.solver_version, "2.10.3")
        self.assertEqual(stats.solver_status, "Stopped on time limit")
        self.assertEqual(stats.solver_status_code, -4)
        self.assertEqual(stats.solver_sol_code, 2)
        self.assertEqual(stats.solver_time, 1.25)
        self.assertEqual(stats.solver_gap, 0.1)
        self.assertEqual(stats.nodes, 42)
        self.assertEqual(stats.root_time, 0.5)
        self.assertEqual(stats.matrix, {"constraints": 3, "variables": 2})
        # the stub reported no bound, so the log supplies it
        self.assertEqual(stats.best_bound, 11.0)

    def test_the_solver_wins_over_the_log(self):
        stats = self._solve(
            _StubSolver(LpSolveStatus.TimeLimit, True, best_bound=4.0), self._LOG
        )
        self.assertEqual(stats.best_bound, 4.0)

    def test_a_bare_stop_is_refined_from_the_log(self):
        stats = self._solve(_StubSolver(LpSolveStatus.Stopped, True), self._LOG)
        self.assertIs(stats.status, LpSolveStatus.TimeLimit)

    def test_a_specific_status_is_not_touched_by_the_log(self):
        stats = self._solve(_StubSolver(LpSolveStatus.NodeLimit, True), self._LOG)
        self.assertIs(stats.status, LpSolveStatus.NodeLimit)

    def test_no_objective_without_a_solution(self):
        prob = self._problem()
        # values left behind by the solver, as CBC does on an infeasible model
        prob.variables()[0].varValue = 2.0
        with mock.patch("pulp.core.lp_stats.parse_logs", return_value=self._LOG):
            stats = prob.solve(_StubSolver(LpSolveStatus.Infeasible, False))
        self.assertIsNone(stats.objective)
        self.assertIsNone(stats.gap_abs)

    def test_objective_with_a_solution(self):
        prob = self._problem()
        prob.variables()[0].varValue = 2.0
        with mock.patch("pulp.core.lp_stats.parse_logs", return_value=None):
            stats = prob.solve(_StubSolver(LpSolveStatus.Optimal, True))
        self.assertEqual(stats.objective, 2.0)


class SolveStatsUnitTest(unittest.TestCase):
    """Tests for LpSolveStats itself, needing no solver."""

    def test_status_str_names_the_reason(self):
        self.assertEqual(
            LpSolveStats(status=LpSolveStatus.TimeLimit).status_str, "TimeLimit"
        )
        self.assertEqual(LpSolveStats().status_str, "NotSolved")

    def test_unknown_status_codes_stay_readable(self):
        self.assertEqual(LpSolveStats(status=99).status_str, "Unknown")  # ty: ignore[invalid-argument-type]

    def test_gap_needs_both_ends(self):
        self.assertIsNone(LpSolveStats(objective=10).gap_abs)
        self.assertIsNone(LpSolveStats(best_bound=10).gap_abs)
        stats = LpSolveStats(objective=10, best_bound=8)
        self.assertEqual(stats.gap_abs, 2)
        gap_rel = stats.gap_rel
        assert gap_rel is not None
        self.assertAlmostEqual(gap_rel, 0.2)

    def test_gap_rel_falls_back_to_the_solver_value(self):
        stats = LpSolveStats(objective=10, logs={"gap": 0.05})
        self.assertEqual(stats.gap_rel, 0.05)

    def test_gap_rel_with_a_zero_objective(self):
        self.assertEqual(LpSolveStats(objective=0, best_bound=0).gap_rel, 0)
        self.assertEqual(LpSolveStats(objective=0, best_bound=3).gap_rel, float("inf"))

    def test_log_properties_without_a_log(self):
        stats = LpSolveStats()
        self.assertIsNone(stats.logs)
        self.assertIsNone(stats.solver_version)

    def test_log_properties_skip_empty_dicts(self):
        stats = LpSolveStats(logs={"cut_info": {}, "first_solution": None})
        self.assertIsNone(stats.cut_info)
        self.assertIsNone(stats.first_solution)

    def test_parse_logs_returns_none_when_unusable(self):
        self.assertIsNone(parse_logs(None, "CBC"))
        self.assertIsNone(parse_logs("nonexistent.log", "CBC"))
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("not a solver log")
            path = f.name
        try:
            # no dialect means no parser, whatever the file holds
            self.assertIsNone(parse_logs(path, None))
            # an unknown dialect must not raise either
            self.assertIsNone(parse_logs(path, "NOT_A_SOLVER"))
        finally:
            os.remove(path)


class FlipStatsSenseTest(unittest.TestCase):
    """Tests for ``LpSolver.flipStatsSense``, called by a solver that was handed
    the objective negated (e.g. COIN_CMD writing a maximize problem as a
    minimize MPS) to undo that in the stats it already built."""

    def setUp(self):
        self.solver = solvers.LpSolver(msg=False)

    def _stats(self, **overrides) -> LpSolveStats:
        defaults: dict[str, Any] = dict(
            objective=12.0,
            best_bound=-11.0,
            logs={
                "best_bound": -11.0,
                "best_solution": -12.0,
                "first_relaxed": -18.5,
                "first_solution": {
                    "Node": 3,
                    "NodesLeft": 2,
                    "BestInteger": -17.0,
                    "CutsBestBound": -18.5,
                },
                "cut_info": {
                    "time": 0.1,
                    "cuts": {"Gomory": 2},
                    "best_bound": -18.2,
                    "best_solution": "text",
                },
                "progress": [
                    MIPProgressRow(
                        Node=0, NodesLeft=1, BestInteger=1e50, CutsBestBound=-18.5
                    ),
                    MIPProgressRow(
                        Node=3, NodesLeft=2, BestInteger=-17.0, CutsBestBound=-18.5
                    ),
                ],
            },
        )
        defaults.update(overrides)
        return LpSolveStats(**defaults)

    def test_flips_the_best_bound(self):
        stats = self.solver.flipStatsSense(self._stats())
        self.assertEqual(stats.best_bound, 11.0)

    def test_leaves_the_objective_alone(self):
        # it already comes from lp.objective.value(), in the problem's sense
        stats = self.solver.flipStatsSense(self._stats())
        self.assertEqual(stats.objective, 12.0)

    def test_a_missing_bound_is_left_as_none(self):
        stats = self.solver.flipStatsSense(self._stats(best_bound=None))
        self.assertIsNone(stats.best_bound)

    def test_flips_the_top_level_log_values(self):
        stats = self.solver.flipStatsSense(self._stats())
        assert stats.logs is not None
        self.assertEqual(stats.logs["best_bound"], 11.0)
        self.assertEqual(stats.logs["best_solution"], 12.0)
        self.assertEqual(stats.first_relaxed, 18.5)

    def test_flips_first_solution_and_cut_info(self):
        stats = self.solver.flipStatsSense(self._stats())
        self.assertEqual(
            stats.first_solution,
            {"Node": 3, "NodesLeft": 2, "BestInteger": 17.0, "CutsBestBound": 18.5},
        )
        self.assertEqual(
            stats.cut_info,
            {
                "time": 0.1,
                "cuts": {"Gomory": 2},
                "best_bound": 18.2,
                # text is descriptive (e.g. "Cuts: 5"), not a number, so untouched
                "best_solution": "text",
            },
        )

    def test_flips_progress_rows_without_touching_the_sentinel(self):
        stats = self.solver.flipStatsSense(self._stats())
        assert stats.logs is not None
        progress = stats.logs["progress"]
        # CBC's magic number for "no incumbent found yet" is left alone
        self.assertEqual(progress[0].BestInteger, 1e50)
        self.assertEqual(progress[0].CutsBestBound, 18.5)
        self.assertEqual(progress[1].BestInteger, 17.0)
        self.assertEqual(progress[1].CutsBestBound, 18.5)
        # Node/NodesLeft, not objective values, are untouched
        self.assertEqual(progress[1].Node, 3)
        self.assertEqual(progress[1].NodesLeft, 2)

    def test_a_missing_log_is_left_as_none(self):
        stats = self.solver.flipStatsSense(self._stats(logs=None))
        self.assertIsNone(stats.logs)

    def test_returns_the_same_object_it_mutated(self):
        stats = self._stats()
        self.assertIs(self.solver.flipStatsSense(stats), stats)


class CBCStopReasonTest(unittest.TestCase):
    """CBC stopping on a limit reports why, and still hands back its solution."""

    def setUp(self):
        if not solvers.COIN_CMD(msg=False).available():
            self.skipTest("COIN_CMD is not available")

    def _knapsack(self):
        """A multi-dimensional knapsack CBC does not close at the root node."""
        rng = random.Random(1)
        prob = LpProblem(self._testMethodName, const.LpMaximize)
        xs = [prob.add_variable(f"x{i}", 0, 1, cat=const.LpInteger) for i in range(60)]
        for _ in range(5):
            weights = [rng.randint(10, 100) for _ in xs]
            prob += lpSum(w * x for w, x in zip(weights, xs)) <= sum(weights) // 2
        prob += lpSum(rng.randint(10, 100) * x for x in xs)
        return prob

    def _solve(self, **options):
        return self._knapsack().solve(solvers.COIN_CMD(msg=False, **options))

    def test_node_limit(self):
        stats = self._solve(maxNodes=1)
        self.assertIs(stats.status, LpSolveStatus.NodeLimit)
        self.assertIs(stats.has_solution, True)

    def test_gap_limit(self):
        stats = self._solve(gapRel=0.5)
        self.assertIs(stats.status, LpSolveStatus.GapLimit)
        self.assertIs(stats.has_solution, True)

    def _assert_maximize_stats(self, stats):
        """Bounds of a maximize problem sit above its incumbents, all positive."""
        self.assertIsNotNone(stats.objective)
        self.assertIsNotNone(stats.best_bound)
        self.assertGreater(stats.objective, 0)
        self.assertGreaterEqual(stats.best_bound, stats.objective - 1e-6)
        self.assertLess(stats.gap_rel, 1)
        if stats.first_relaxed is not None:
            self.assertGreaterEqual(stats.first_relaxed, stats.objective - 1e-6)
        if stats.first_solution is not None:
            self.assertGreater(stats.first_solution["BestInteger"], 0)
            self.assertLessEqual(
                stats.first_solution["BestInteger"], stats.objective + 1e-6
            )
        if stats.cut_info and isinstance(stats.cut_info.get("best_bound"), float):
            self.assertGreaterEqual(
                stats.cut_info["best_bound"], stats.objective - 1e-6
            )

    def test_maximize_stats_read_in_maximize_sense(self):
        # the MPS CBC reads has the objective negated, so actualSolve must flip
        # its log and bound back before returning
        stats = self._solve(maxNodes=1)
        self._assert_maximize_stats(stats)

    def test_maximize_stats_from_an_lp_file(self):
        # an LP file keeps the maximize sense, so CBC's log needs no flipping
        prob = self._knapsack()
        solver = solvers.COIN_CMD(msg=False, maxNodes=1)
        start = clocks()
        with solver.capture_log():
            status, has_solution = solver.solve_CBC(prob, use_mps=False)
            stats = solver.buildStats(prob, status, has_solution, start=start)
        self._assert_maximize_stats(stats)


if __name__ == "__main__":
    unittest.main()
