"""Unit tests for the Clarabel solver."""

import os
import tempfile
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpMaximize, LpMinimize, LpProblem, LpSolveStatus, const
from pulp.apis.core import PulpSolverError
from pulp.tests.solver_common import BaseSolverTest, PulpTestConfig

# shared tests on problems with integer variables, which Clarabel refuses with
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

# shared tests that expect w = 0 on an LP where w has no cost: an interior
# point solution lies inside the optimal face, not at a vertex (see
# test_continuous_without_w)
_VERTEX_TESTS = {
    "test_continuous",
    "test_continuous_max",
    "test_divide",
    "test_invalid_var_names",
    "test_logPath",
    "test_long_var_name",
    "test_msg_arg",
    "test_zero_constraint",
}


def _std_lp(sense: int = LpMinimize) -> LpProblem:
    """The LP of the shared test_continuous tests."""
    prob = LpProblem("std_lp", sense)
    x = prob.add_variable("x", 0, 4)
    y = prob.add_variable("y", -1, 1)
    z = prob.add_variable("z", 0)
    w = prob.add_variable("w", 0)
    prob += x + 4 * y + 9 * z, "obj"
    prob += x + y <= 5, "c1"
    prob += x + z >= 10, "c2"
    prob += -y + z == 7, "c3"
    prob += w >= 0, "c4"
    return prob


def _random_lp(n: int = 60, m: int = 40) -> LpProblem:
    """A dense LP that takes Clarabel several iterations."""
    prob = LpProblem("random_lp", LpMaximize)
    xs = [prob.add_variable(f"x{j}", 0, 10) for j in range(n)]
    prob += sum(((j * 7) % 11 + 1) * x for j, x in enumerate(xs))
    for i in range(m):
        prob += sum(((i * j) % 13 + 1) * x for j, x in enumerate(xs)) <= 50, f"c{i}"
    return prob


class CLARABELTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CLARABEL
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
    }

    def setUp(self):
        if self._testMethodName in _MIP_TESTS:
            self.skipTest("Clarabel solves LPs only")
        if self._testMethodName in _VERTEX_TESTS:
            self.skipTest("an interior point solution is not at a vertex")
        super().setUp()

    def test_mip_needs_mip_false(self):
        prob = LpProblem("mip", LpMaximize)
        x = prob.add_variable("x", 0, 3.5, cat=const.LpInteger)
        prob += x
        with self.assertRaises(PulpSolverError):
            prob.solve(self.solver)
        stats = prob.solve(solvers.CLARABEL(msg=False, mip=False))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert x.varValue is not None
        self.assertAlmostEqual(x.varValue, 3.5, places=6)

    def test_continuous_without_w(self):
        for sense, expected in (
            (LpMinimize, {"x": 4, "y": -1, "z": 6}),
            (LpMaximize, {"x": 4, "y": 1, "z": 8}),
        ):
            with self.subTest(sense=sense):
                prob = _std_lp(sense)
                stats = prob.solve(self.solver)
                self.assertIs(stats.status, LpSolveStatus.Optimal)
                values = {v.name: v.value() for v in prob.variables()}
                for name, value in expected.items():
                    self.assertAlmostEqual(values[name] or 0.0, value, places=6)
                # w has no cost, but stays within its bounds
                w = values["w"]
                assert w is not None
                self.assertGreaterEqual(w, 0)

    def test_log_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clarabel.log")
            stats = _std_lp().solve(solvers.CLARABEL(msg=False, logPath=path))
            self.assertIs(stats.status, LpSolveStatus.Optimal)
            with open(path) as f:
                self.assertIn("Clarabel", f.read())

    def test_maximize_with_constant(self):
        prob = LpProblem("max", LpMaximize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", 0, None)
        prob += 3 * x + 2 * y + 5
        prob += x + y <= 5, "c1"
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert stats.objective is not None
        self.assertAlmostEqual(stats.objective, 19, places=6)
        c1 = prob.constraints()[0]
        assert c1.pi is not None
        self.assertAlmostEqual(c1.pi, 2, places=6)

    def test_bounds(self):
        # fixed, free, negative and greater-or-equal rows
        prob = LpProblem("bounds", LpMinimize)
        x = prob.add_variable("x", 2, 2)
        y = prob.add_variable("y", None, None)
        z = prob.add_variable("z", -5, -1)
        prob += x + y - z
        prob += y + z >= -3, "c1"
        prob += x + y == 4, "c2"
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        for var, value in ((x, 2), (y, 2), (z, -1)):
            assert var.varValue is not None
            self.assertAlmostEqual(var.varValue, value, places=6)
        c1, c2 = prob.constraints()
        assert c1.slack is not None and c2.slack is not None
        self.assertAlmostEqual(c1.slack, -4, places=6)
        self.assertAlmostEqual(c2.slack, 0, places=6)

    def test_unbounded_and_infeasible(self):
        prob = LpProblem("unbounded", LpMaximize)
        x = prob.add_variable("x", 0)
        y = prob.add_variable("y", 0)
        prob += x + y
        prob += x - y <= 1, "c1"
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Unbounded)
        self.assertFalse(stats.has_solution)

        prob = LpProblem("infeasible", LpMinimize)
        x = prob.add_variable("x", 0, 1)
        prob += x
        prob += x >= 2, "c1"
        stats = prob.solve(self.solver)
        self.assertIs(stats.status, LpSolveStatus.Infeasible)
        self.assertFalse(stats.has_solution)

    def test_iteration_limit(self):
        prob = _random_lp()
        stats = prob.solve(solvers.CLARABEL(msg=False, max_iter=1))
        self.assertIs(stats.status, LpSolveStatus.IterationLimit)
        self.assertFalse(stats.has_solution)

    def test_callback(self):
        infos: list[object] = []

        def callback(info) -> bool:
            infos.append(info)
            return True

        stats = _random_lp().solve(self.solver, callback=callback)
        self.assertIs(stats.status, LpSolveStatus.Interrupted)
        self.assertTrue(infos)

    def test_solver_params(self):
        prob = _random_lp()
        stats = prob.solve(
            solvers.CLARABEL(msg=False, tol_gap_rel=1e-6, presolve_enable=False)
        )
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        assert prob.solverModel is not None
        settings = prob.solverModel.get_settings()
        self.assertEqual(settings.tol_gap_rel, 1e-6)
        self.assertFalse(settings.presolve_enable)

        with self.assertRaises(AttributeError):
            prob.solve(solvers.CLARABEL(msg=False, not_a_parameter=1))

    def test_resolve_rebuilds(self):
        prob = _random_lp()
        prob.solve(self.solver)
        model = prob.solverModel
        xs = prob.variables()
        prob += xs[0] + xs[1] <= 1, "cut"
        stats = prob.resolve()
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertIsNot(prob.solverModel, model)
        cold = prob.copy()
        cold_stats = cold.solve(solvers.CLARABEL(msg=False))
        assert stats.objective is not None and cold_stats.objective is not None
        self.assertAlmostEqual(stats.objective, cold_stats.objective, places=5)
