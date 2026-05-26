import unittest

from pulp import CPSAT, LpMaximize, LpMinimize, LpProblem, LpStatusOptimal, const
from pulp.apis.core import PulpSolverError


class CPSATUnitTest(unittest.TestCase):
    def setUp(self):
        self.solver = CPSAT(msg=False)
        if not self.solver.available():
            self.skipTest("ortools not available")

    def test_available(self):
        self.assertTrue(self.solver.available())

    def test_integer_mip(self):
        prob = LpProblem("integer_mip", LpMinimize)
        x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
        y = prob.add_variable("y", 0, 10, cat=const.LpInteger)
        prob += x + 2 * y
        prob += x + y >= 7
        prob += x <= 5
        status = prob.solve(self.solver)
        self.assertEqual(status, LpStatusOptimal)
        self.assertEqual(x.value(), 5)
        self.assertEqual(y.value(), 2)

    def test_continuous_as_integer(self):
        prob = LpProblem("continuous_as_int", LpMinimize)
        x = prob.add_variable("x", 0.0, 10.0, cat=const.LpContinuous)
        prob += 2.5 * x
        prob += x >= 3.7
        status = prob.solve(self.solver)
        self.assertEqual(status, LpStatusOptimal)
        self.assertEqual(x.value(), 4)

    def test_feasibility_only(self):
        prob = LpProblem("feasibility", LpMinimize)
        x = prob.add_variable("x", 0, 5)
        y = prob.add_variable("y", 0, 5)
        prob += x + y >= 4
        prob += x <= 2
        status = prob.solve(self.solver)
        self.assertEqual(status, LpStatusOptimal)
        self.assertGreaterEqual(x.value() + y.value(), 4)

    def test_unbounded_variable_raises(self):
        prob = LpProblem("unbounded", LpMinimize)
        x = prob.add_variable("x", 0, None)
        prob += x
        with self.assertRaises(PulpSolverError):
            prob.solve(self.solver)

    def test_warm_start(self):
        prob = LpProblem("warm_start", LpMinimize)
        x = prob.add_variable("x", 0, 20, cat=const.LpInteger)
        y = prob.add_variable("y", 0, 20, cat=const.LpInteger)
        prob += x + y
        prob += x + 2 * y >= 15
        x.varValue = 10
        y.varValue = 3
        status = prob.solve(CPSAT(msg=False, warmStart=True))
        self.assertEqual(status, LpStatusOptimal)
        self.assertEqual(x.value() + y.value(), 8)

    def test_repeated_name_raises(self):
        prob = LpProblem("repeated_name", LpMinimize)
        x1 = prob.add_variable("x", 0, 4)
        x2 = prob.add_variable("x", -1, 1)
        prob += x1 + x2
        with self.assertRaises(PulpSolverError):
            prob.solve(self.solver)

    def test_maximize(self):
        prob = LpProblem("maximize", LpMaximize)
        x = prob.add_variable("x", 0, 10)
        prob += x
        prob += x <= 7
        status = prob.solve(self.solver)
        self.assertEqual(status, LpStatusOptimal)
        self.assertEqual(x.value(), 7)
