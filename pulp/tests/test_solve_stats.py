"""
Tests for the statistics object returned by ``LpProblem.solve(stats=True)``
"""

from __future__ import annotations

import glob
import json
import os
import tempfile
import unittest
import warnings
from importlib.util import find_spec

import pulp.apis as solvers
from pulp import LpProblem, LpSolveStats
from pulp import constants as const
from pulp.core import lp_problem
from pulp.core.lp_stats import parse_logs


class SolveStatsTest(unittest.TestCase):
    """Tests for ``LpProblem.solve(stats=True)`` against the default solver."""

    def setUp(self):
        if solvers.LpSolverDefault is None:
            self.skipTest("no default solver available")
        self.solver = solvers.LpSolverDefault.copy()
        self.solver.msg = False
        # the "solve() will return stats" notice fires once per process
        lp_problem._warned_about_stats = False

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
        return prob, prob.solve(self.solver, stats=True)

    def test_returns_stats_object(self):
        _, stats = self._solve()
        self.assertIsInstance(stats, LpSolveStats)
        self.assertEqual(stats.status, const.LpStatusOptimal)
        self.assertEqual(stats.sol_status, const.LpSolutionOptimal)
        self.assertEqual(stats.status_str, "Optimal")
        self.assertEqual(stats.feasible, 1)
        self.assertEqual(stats.solver, self.solver.name)
        self.assertAlmostEqual(stats.objective, 12, places=4)

    def test_model_shape_recorded(self):
        prob, stats = self._solve()
        self.assertEqual(stats.num_variables, prob.numVariables())
        self.assertEqual(stats.num_constraints, prob.numConstraints())
        self.assertTrue(stats.is_mip)

    def test_timings_are_recorded(self):
        _, stats = self._solve()
        self.assertGreater(stats.time, 0)
        self.assertGreaterEqual(stats.cpu_time, 0)

    def test_status_matches_plain_solve(self):
        prob = self._problem()
        status = prob.solve(self.solver)
        self.assertIsInstance(status, int)
        self.assertEqual(status, prob.stats.status)
        self.assertEqual(status, prob.solve(self.solver, stats=True).status)

    def test_stats_property_is_the_last_result(self):
        prob, stats = self._solve()
        self.assertIs(prob.stats, stats)

    def test_solve_without_stats_warns_once(self):
        prob = self._problem()
        with self.assertWarns(DeprecationWarning):
            prob.solve(self.solver)
        # the notice is one per process, not one per solve
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prob.solve(self.solver)
        self.assertEqual([w for w in caught if "stats=True" in str(w.message)], [])

    def test_solve_with_stats_does_not_warn(self):
        prob = self._problem()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prob.solve(self.solver, stats=True)
        self.assertEqual([w for w in caught if "stats=True" in str(w.message)], [])

    def test_legacy_attributes_warn_and_agree(self):
        prob, stats = self._solve()
        for name, expected in (
            ("status", stats.status),
            ("sol_status", stats.sol_status),
            ("solutionTime", stats.time),
            ("solutionCpuTime", stats.cpu_time),
            ("bestBound", stats.best_bound),
        ):
            with self.subTest(attribute=name):
                with self.assertWarns(DeprecationWarning):
                    self.assertEqual(getattr(prob, name), expected)

    def test_legacy_setters_reach_the_stats(self):
        prob = self._problem()
        with self.assertWarns(DeprecationWarning):
            prob.status = const.LpStatusInfeasible
        self.assertEqual(prob.stats.status, const.LpStatusInfeasible)
        with self.assertWarns(DeprecationWarning):
            prob.bestBound = 7.5
        self.assertEqual(prob.stats.best_bound, 7.5)

    def test_infeasible_problem_is_not_feasible(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        prob += x >= 8, "lo"
        prob += x <= 2, "hi"
        prob += x
        stats = prob.solve(self.solver, stats=True)
        self.assertIn(stats.status, (const.LpStatusInfeasible, const.LpStatusUndefined))
        self.assertEqual(stats.feasible, 0)

    def test_unsolved_problem_has_empty_stats(self):
        prob = self._problem()
        self.assertEqual(prob.stats.status, const.LpStatusNotSolved)
        self.assertEqual(prob.stats.feasible, 0)
        self.assertIsNone(prob.stats.logs)

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
        self.assertEqual(data["status"], stats.status)
        self.assertEqual(data["feasible"], 1)
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

    def test_str_mentions_the_solver_and_status(self):
        _, stats = self._solve()
        text = str(stats)
        self.assertIn(self.solver.name, text)
        self.assertIn("Optimal", text)

    def test_solver_options_are_recorded(self):
        _, stats = self._solve()
        self.assertEqual(stats.solver_options["solver"], self.solver.name)

    def test_legacy_pickle_is_migrated(self):
        prob, stats = self._solve()
        state = prob.__getstate__()
        state.pop("_stats")
        state["status"] = const.LpStatusInfeasible
        state["solutionTime"] = 1.5
        state["bestBound"] = 3.0
        restored = LpProblem.__new__(LpProblem)
        restored.__setstate__(state)
        self.assertEqual(restored.stats.status, const.LpStatusInfeasible)
        self.assertEqual(restored.stats.time, 1.5)
        self.assertEqual(restored.stats.best_bound, 3.0)

    def test_copy_keeps_the_stats_independent(self):
        prob, stats = self._solve()
        clone = prob.copy()
        self.assertEqual(clone.stats.status, stats.status)
        clone.stats.status = const.LpStatusUndefined
        self.assertEqual(prob.stats.status, stats.status)

    def test_no_temp_log_is_left_behind(self):
        pattern = os.path.join(tempfile.gettempdir(), "*-pulp.log")
        before = set(glob.glob(pattern))
        self._solve()
        self.assertEqual(set(glob.glob(pattern)) - before, set())

    def test_a_user_log_path_is_kept(self):
        if self.solver.logDialect is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        log_path = os.path.join(tempfile.mkdtemp(), "solver.log")
        solver = self.solver.copy()
        solver.optionsDict["logPath"] = log_path
        self._problem().solve(solver, stats=True)
        self.assertTrue(os.path.isfile(log_path))
        os.remove(log_path)

    @unittest.skipIf(find_spec("orloge") is None, "orloge is not installed")
    def test_logs_are_parsed_without_a_log_path(self):
        if self.solver.logDialect is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        _, stats = self._solve()
        self.assertIsInstance(stats.logs, dict)
        self.assertIsNotNone(stats.solver_version)
        self.assertIsNotNone(stats.solver_status)
        self.assertIsNotNone(stats.solver_status_code)
        # a log this small carries no timing line, so solver_time may stay None
        self.assertIsNotNone(stats.matrix)
        self.assertIn("variables", stats.matrix)

    @unittest.skipIf(find_spec("orloge") is None, "orloge is not installed")
    def test_best_bound_falls_back_to_the_log(self):
        if self.solver.logDialect is None:
            self.skipTest(f"{self.solver.name} writes no parseable log")
        _, stats = self._solve()
        # COIN_CMD reports no bound itself, so this can only come from the log
        self.assertAlmostEqual(stats.best_bound, 12, places=4)

    def test_sequential_solve_returns_one_stats_per_objective(self):
        prob = self._problem()
        x, y = prob.variables()
        results = prob.sequentialSolve(
            [x + y, 3 * x + 2 * y], solver=self.solver, stats=True
        )
        self.assertEqual(len(results), 2)
        for stats in results:
            self.assertIsInstance(stats, LpSolveStats)
            self.assertEqual(stats.solver, self.solver.name)
        self.assertIsNot(results[0], results[1])

    def test_resolve_passes_stats_through(self):
        prob = self._problem()
        prob.solve(self.solver, stats=True)
        self.assertIsInstance(prob.resolve(stats=True), LpSolveStats)


class SolveStatsUnitTest(unittest.TestCase):
    """Tests for LpSolveStats itself, needing no solver."""

    def test_feasible_flag(self):
        for sol_status, expected in (
            (const.LpSolutionOptimal, 1),
            (const.LpSolutionIntegerFeasible, 1),
            (const.LpSolutionNoSolutionFound, 0),
            (const.LpSolutionInfeasible, 0),
            (const.LpSolutionUnbounded, 0),
        ):
            with self.subTest(sol_status=sol_status):
                self.assertEqual(LpSolveStats(sol_status=sol_status).feasible, expected)

    def test_gap_needs_both_ends(self):
        self.assertIsNone(LpSolveStats(objective=10).gap_abs)
        self.assertIsNone(LpSolveStats(best_bound=10).gap_abs)
        stats = LpSolveStats(objective=10, best_bound=8)
        self.assertEqual(stats.gap_abs, 2)
        gap_rel = stats.gap_rel
        assert gap_rel is not None
        self.assertAlmostEqual(gap_rel, 0.2)

    def test_gap_rel_falls_back_to_the_solver_value(self):
        self.assertEqual(LpSolveStats(objective=10, solver_gap=0.05).gap_rel, 0.05)

    def test_gap_rel_with_a_zero_objective(self):
        self.assertEqual(LpSolveStats(objective=0, best_bound=0).gap_rel, 0)
        self.assertEqual(LpSolveStats(objective=0, best_bound=3).gap_rel, float("inf"))

    def test_fill_from_logs_promotes_fields(self):
        stats = LpSolveStats()
        stats.fill_from_logs(
            {
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
                "progress": "kept in logs only",
            }
        )
        self.assertEqual(stats.solver_version, "2.10.3")
        self.assertEqual(stats.solver_status, "Stopped on time limit")
        self.assertEqual(stats.solver_status_code, -4)
        self.assertEqual(stats.solver_sol_code, 2)
        self.assertEqual(stats.solver_time, 1.25)
        self.assertEqual(stats.solver_gap, 0.1)
        self.assertEqual(stats.nodes, 42)
        self.assertEqual(stats.root_time, 0.5)
        self.assertEqual(stats.matrix, {"constraints": 3, "variables": 2})
        # the solver reported neither, so the log supplies them
        self.assertEqual(stats.objective, 12.0)
        self.assertEqual(stats.best_bound, 11.0)

    def test_fill_from_logs_does_not_overwrite_the_solver(self):
        stats = LpSolveStats(objective=5.0, best_bound=4.0)
        stats.fill_from_logs({"best_solution": 99.0, "best_bound": 98.0})
        self.assertEqual(stats.objective, 5.0)
        self.assertEqual(stats.best_bound, 4.0)

    def test_fill_from_logs_with_nothing_to_parse(self):
        stats = LpSolveStats()
        stats.fill_from_logs(None)
        self.assertIsNone(stats.logs)
        self.assertIsNone(stats.solver_version)

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

    def test_unknown_status_codes_stay_readable(self):
        stats = LpSolveStats(status=99, sol_status=99)
        self.assertEqual(stats.status_str, "Unknown")
        self.assertEqual(stats.sol_status_str, "Unknown")


if __name__ == "__main__":
    unittest.main()
