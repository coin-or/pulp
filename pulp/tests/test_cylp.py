"""Unit tests for cylp solver."""

import contextlib
import os
import tempfile
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
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
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

    def test_iteration_limit(self):
        # several pivots are needed: one iteration stops Clp short of the optimum
        prob = LpProblem("iterations", LpMaximize)
        xs = [prob.add_variable(f"x{i}", 0, 10) for i in range(6)]
        prob += sum((i + 1) * x for i, x in enumerate(xs)), "obj"
        for k in range(4):
            prob += sum((i + k) % 3 * x for i, x in enumerate(xs)) <= 10 + k, f"c{k}"
        solver = solvers.CYLP(msg=False, maxIterations=1)
        stats = prob.solve(solver)
        self.assertIs(stats.status, LpSolveStatus.IterationLimit)
        self.assertFalse(stats.has_solution)
        model = prob.solverModel
        assert model is not None
        self.assertEqual(model.maxNumIteration, 1)
        # a resolve without the limit lifts it from the model it keeps
        del solver.optionsDict["maxIterations"]
        prob += xs[0] <= 9, "cut"
        stats = prob.resolve()
        self.assertIs(prob.solverModel, model)
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        self.assertTrue(stats.has_solution)

    def test_solver_params(self):
        # the extra options are attributes of the Clp (LP) or Cbc (MIP) model
        prob = LpProblem("params", LpMinimize)
        x = prob.add_variable("x", 0, 4)
        prob += x
        prob += x >= 1, "c1"
        stats = prob.solve(solvers.CYLP(msg=False, primalTolerance=1e-9))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        model = prob.solverModel
        assert model is not None
        self.assertEqual(model.primalTolerance, 1e-9)

        y = prob.add_variable("y", 0, 4, cat=const.LpInteger)
        prob += y >= 1.5, "c2"
        stats = prob.solve(solvers.CYLP(msg=False, allowableGap=0.5))
        self.assertIs(stats.status, LpSolveStatus.Optimal)
        model = prob.solverModel
        assert model is not None
        self.assertEqual(model.allowableGap, 0.5)

        with self.assertRaises(AttributeError):
            prob.solve(solvers.CYLP(msg=False, not_a_param=1))

    @contextlib.contextmanager
    def _console(self):
        """Collect what is written to the process's standard output (the file
        descriptor, where Clp and Cbc print) during the block."""
        with tempfile.TemporaryFile("w+") as console:
            text: list[str] = []
            with solvers.coin._redirect_c_stdout(console):
                yield text
            console.seek(0)
            text.append(console.read())

    def _lp(self) -> LpProblem:
        prob = LpProblem("log", LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", 0, 4)
        prob += 2 * x + 3 * y
        prob += x + y >= 3, "c1"
        return prob

    def test_log_goes_to_the_file_not_the_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "cylp.log")
            prob = self._lp()
            with self._console() as console:
                stats = prob.solve(solvers.CYLP(msg=False, logPath=log_path))
            self.assertIs(stats.status, LpSolveStatus.Optimal)
            self.assertEqual(console[0], "")
            with open(log_path) as f:
                self.assertIn("Clp0000I Optimal", f.read())
        # standard output works again after the solve
        print("", end="", flush=True)

    def test_no_msg_prints_nothing(self):
        prob = self._lp()
        with self._console() as console:
            prob.solve(solvers.CYLP(msg=False))
        self.assertEqual(console[0], "")

    def test_resolve_method(self):
        # either simplex, forced or chosen from the changes, re-solves to the optimum
        for method in (None, "dual", "primal"):
            with self.subTest(method=method):
                prob = self._lp()
                options = {} if method is None else {"resolveMethod": method}
                prob.solve(solvers.CYLP(msg=False, **options))
                model = prob.solverModel
                prob += prob.variables()[0] <= 1, "cut"
                stats = prob.resolve()
                self.assertIs(prob.solverModel, model)
                self.assertEqual(stats.status, LpSolveStatus.Optimal)
                self.assertAlmostEqual(prob.objective.value(), 8)
        prob = self._lp()
        prob.solve(solvers.CYLP(msg=False, resolveMethod="barrier"))
        prob += prob.variables()[0] <= 1, "cut"
        with self.assertRaises(ValueError):
            prob.resolve()

    def test_perturbation(self):
        # passed to Clp (which has no getter for it) on the solve and the resolve,
        # not set as a model attribute; the optimum is the same
        prob = self._lp()
        stats = prob.solve(solvers.CYLP(msg=False, perturbation=50))
        self.assertEqual(stats.status, LpSolveStatus.Optimal)
        prob += prob.variables()[0] <= 1, "cut"
        self.assertEqual(prob.resolve().status, LpSolveStatus.Optimal)
        self.assertAlmostEqual(prob.objective.value(), 8)

    def test_resolve_writes_its_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "cylp.log")
            prob = self._lp()
            solver = solvers.CYLP(msg=False, logPath=log_path)
            prob.solve(solver)
            model = prob.solverModel
            prob += prob.variables()[0] <= 1, "cut"
            prob.resolve()
            self.assertIs(prob.solverModel, model)
            with open(log_path) as f:
                # the log of the resolve (a dual simplex), not of the first solve
                log = f.read()
            self.assertIn("Clp", log)
            self.assertNotIn("Presolve", log)
