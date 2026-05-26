"""Unit tests for cplex_py solver."""

from typing import ClassVar

import pulp.apis as solvers
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
            okstatus=_status(
                "LpStatusInfeasible", "LpStatusUnbounded", "LpStatusUndefined"
            )
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
            problem, self.solver, [const.LpStatusOptimal], callback=[Callback]
        )
        self.assertGreaterEqual(counter, 1)
