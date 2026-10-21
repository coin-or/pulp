"""Unit tests for cplex_py solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.apis.core import PulpSolverError
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
    pulpTestCheck,
)


class CPLEX_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CPLEX_PY
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_unbounded": PulpTestConfig(
            okstatus=_status("Infeasible", "Unbounded", "Undefined")
        ),
    }

    def _build(self, **kwargs):
        """
        Builds and returns a solver instance after creating and initializing a bin packing problem.
        """
        problem = create_bin_packing_problem(bins=40, seed=99)
        solver = self.solveInst(**kwargs)
        solver.buildSolverModel(lp=problem)
        return solver

    def test_search_param_without_solver_model(self):
        """
        Tests the behavior of the `search_param` method when invoked without a `solverModel`
        initialized. Validates that an appropriate error is raised under these conditions.
        """
        solver = self.solveInst()
        with self.assertRaises(PulpSolverError):
            solver.search_param("barrier.algorithm")

    def test_get_param(self):
        """
        Tests the `get_param` method of the solver instance to ensure the correct
        value is returned for a given parameter key.
        """
        solver = self._build()
        self.assertEqual(solver.get_param("barrier.algorithm"), 0)

    def test_get_param_with_full_path(self):
        """
        Test case for accessing a solver's parameter by its full hierarchical path.
        """
        solver = self._build()
        self.assertEqual(solver.get_param("parameters.barrier.algorithm"), 0)

    def test_set_param(self):
        """
        Tests the functionality for setting a parameter in the solver.
        """
        param = "barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(solver.get_param(name=param), 100)

    def test_set_param_with_full_path(self):
        """
        Tests the functionality for setting a parameter using its full hierarchical path in the solver.
        """
        param = "parameters.barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(solver.get_param(name=param), 100)

    def test_changed_param(self):
        param = "parameters.barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(len(solver.get_changed_params()), 1)

    def test_callback(self):
        from cplex.callbacks import (
            IncumbentCallback,  # type: ignore[import-not-found, import-untyped]
        )

        counter = 0

        class Callback(IncumbentCallback):
            def __call__(self):
                nonlocal counter
                counter += 1

        problem = create_bin_packing_problem(bins=5, seed=55)
        pulpTestCheck(
            problem, self.solver, [const.LpSolveStatus.Optimal], callback=[Callback]
        )
        self.assertGreaterEqual(counter, 1)

    def _small_problem(self, cat=const.LpContinuous):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 5, cat=cat)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        return prob

    def _problem_type(self, prob, **kwargs):
        solver = self.solveInst(msg=False, **kwargs)
        solver.buildSolverModel(prob)
        model = prob.solverModel
        return model.problem_type[model.get_problem_type()]

    def test_continuous_problem_is_lp(self):
        """
        A continuous problem must be passed to CPLEX as an LP even with mip=True,
        otherwise reduced costs and duals are not available.
        """
        self.assertEqual(self._problem_type(self._small_problem()), "LP")

    def test_integer_problem_is_milp(self):
        prob = self._small_problem(cat=const.LpInteger)
        self.assertEqual(self._problem_type(prob), "MILP")

    def test_integer_problem_without_mip_is_lp(self):
        prob = self._small_problem(cat=const.LpInteger)
        self.assertEqual(self._problem_type(prob, mip=False), "LP")

    def test_continuous_problem_reduced_costs_and_duals(self):
        """
        Checks reduced costs and duals with the default mip=True, independently
        of the shared test_dual_variables_reduced_costs configuration.
        """
        prob = self._small_problem()
        prob.solve(self.solveInst(msg=False))
        dj = {v.name: v.dj for v in prob.variables()}
        pi = {c.name: c.pi for c in prob.constraints()}
        for name, value in {"x": 0, "y": 12, "z": 0}.items():
            self.assertIsNotNone(dj[name], name)
            self.assertAlmostEqual(dj[name], value, places=5)
        for name, value in {"c1": 0, "c2": 1, "c3": 8}.items():
            self.assertIsNotNone(pi[name], name)
            self.assertAlmostEqual(pi[name], value, places=5)

    def test_dual_variables_reduced_costs_is_not_skipped(self):
        """The skip=False override must win over the default skip=True."""
        self.assertFalse(self._config("test_dual_variables_reduced_costs").skip)
