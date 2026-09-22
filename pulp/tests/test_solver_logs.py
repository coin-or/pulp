"""
End to end tests of pulp + solver + orloge: solve with ``stats=True`` and check what
orloge read back out of each solver's log.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from orloge.base import MIPProgressRow
from orloge.cplex import CPLEXProgressRow
from orloge.cpsat import CPSATProgressRow
from orloge.gurobi import GUROBIProgressRow

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.core.lp_stats import FEASIBLE_SOLUTIONS


class _SolverLogsTests(unittest.TestCase):
    """Tests shared by every solver whose log orloge parses.

    Subclasses set the solver class, the orloge dialect it writes and the class
    orloge uses for the rows of its progress table. Run on its own, this class only
    skips.
    """

    solver_class: type[solvers.LpSolver]
    dialect: str
    row_class: type[MIPProgressRow]
    #: whether the log ends with the solver's summary of how the solve went (status,
    #: objective, bound); orloge can only fill those fields in when it does
    log_has_summary = True

    def setUp(self):
        if type(self) is _SolverLogsTests:
            self.skipTest("shared tests, run through the per-solver subclasses")
        if not self.solver_class(msg=False).available():
            self.skipTest(f"{self.solver_class.name} is not available")

    def _solver(self, **kwargs):
        return self.solver_class(msg=False, **kwargs)

    def _problem(self):
        """min 3x + 2y  s.t.  x + y >= 5, x >= 2, x and y integer. Optimum is 12.

        Every variable is integer and bounded so CP-SAT can take the model as is.
        """
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
        y = prob.add_variable("y", 0, 10, cat=const.LpInteger)
        prob += x + y >= 5, "c1"
        prob += x >= 2, "c2"
        prob += 3 * x + 2 * y
        return prob

    def test_the_log_is_parsed(self):
        stats = self._problem().solve(self._solver(), stats=True)
        self.assertIsInstance(stats.logs, dict)
        self.assertEqual(stats.logs["solver"], self.dialect)
        self.assertIsNotNone(stats.solver_version)
        if self.log_has_summary:
            self.assertIsNotNone(stats.solver_status)
        else:
            self.assertIsNone(stats.solver_status)

    def test_the_log_agrees_with_the_solver(self):
        stats = self._problem().solve(self._solver(), stats=True)
        self.assertEqual(stats.status, const.LpStatusOptimal)
        self.assertIs(stats.has_solution, True)
        self.assertAlmostEqual(stats.objective, 12, places=4)
        if not self.log_has_summary:
            return
        self.assertEqual(stats.solver_status_code, const.LpStatusOptimal)
        self.assertEqual(stats.solver_sol_code, const.LpSolutionOptimal)
        self.assertAlmostEqual(stats.best_bound, 12, places=4)

    def test_progress_rows_use_the_solver_row_class(self):
        stats = self._problem().solve(self._solver(), stats=True)
        progress = stats.logs["progress"]
        self.assertIsInstance(progress, list)
        for row in progress:
            self.assertIsInstance(row, self.row_class)

    def test_a_user_log_path_is_parsed_and_kept(self):
        log_path = os.path.join(tempfile.mkdtemp(), "solver.log")
        try:
            stats = self._problem().solve(self._solver(logPath=log_path), stats=True)
            self.assertTrue(os.path.isfile(log_path))
            self.assertIsInstance(stats.logs, dict)
            self.assertEqual(stats.logs["solver"], self.dialect)
        finally:
            if os.path.isfile(log_path):
                os.remove(log_path)

    def test_an_infeasible_problem_has_no_solution(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
        prob += x >= 8, "lo"
        prob += x <= 2, "hi"
        prob += x
        stats = prob.solve(self._solver(), stats=True)
        self.assertIs(stats.has_solution, False)
        self.assertNotIn(stats.solver_sol_code, FEASIBLE_SOLUTIONS)


class CBCLogsTest(_SolverLogsTests):
    solver_class = solvers.COIN_CMD
    dialect = "CBC"
    row_class = MIPProgressRow


class CPLEXCmdLogsTest(_SolverLogsTests):
    solver_class = solvers.CPLEX_CMD
    dialect = "CPLEX"
    row_class = CPLEXProgressRow


class CPLEXPyLogsTest(_SolverLogsTests):
    solver_class = solvers.CPLEX_PY
    dialect = "CPLEX"
    row_class = CPLEXProgressRow
    # the callable library leaves out the closing "MIP - Integer optimal ..." lines
    # that the interactive shell prints
    log_has_summary = False


class GurobiLogsTest(_SolverLogsTests):
    solver_class = solvers.GUROBI
    dialect = "GUROBI"
    row_class = GUROBIProgressRow


class GurobiCmdLogsTest(_SolverLogsTests):
    solver_class = solvers.GUROBI_CMD
    dialect = "GUROBI"
    row_class = GUROBIProgressRow


class CPSATLogsTest(_SolverLogsTests):
    solver_class = solvers.CPSAT
    dialect = "CPSAT"
    row_class = CPSATProgressRow


if __name__ == "__main__":
    unittest.main()
