import unittest
from decimal import Decimal

import pulp
from pulp import LpStatusOptimal


class TestDecimalCoefficients(unittest.TestCase):
    """Issue #815 — Decimal numbers must work as LP coefficients."""

    def _solve(self, prob):
        solver = pulp.PULP_CBC_CMD(msg=0)
        status = prob.solve(solver)
        self.assertEqual(status, LpStatusOptimal)
        return status

    def test_objective_decimal(self):
        prob = pulp.LpProblem("dec_obj", pulp.LpMaximize)
        x = pulp.LpVariable("x", lowBound=0, upBound=10)

        prob += Decimal("3") * x
        prob += x <= 8

        self._solve(prob)

        self.assertAlmostEqual(pulp.value(x), 8.0)
        self.assertAlmostEqual(pulp.value(prob.objective), 24.0)

    def test_constraint_decimal(self):
        prob = pulp.LpProblem("dec_con", pulp.LpMaximize)
        x = pulp.LpVariable("x", lowBound=0, upBound=100)

        prob += x
        prob += Decimal("2") * x <= Decimal("10")

        self._solve(prob)

        self.assertAlmostEqual(pulp.value(x), 5.0)

    def test_decimal_rmul(self):
        x = pulp.LpVariable("x", lowBound=0)

        expr = Decimal("1.5") * x

        self.assertIsInstance(expr, pulp.LpAffineExpression)
        self.assertAlmostEqual(expr[x], 1.5)

    def test_decimal_division(self):
        x = pulp.LpVariable("x", lowBound=0)

        expr = x / Decimal("4")

        self.assertIsInstance(expr, pulp.LpAffineExpression)
        self.assertAlmostEqual(expr[x], 0.25)

    def test_decimal_sum(self):
        prob = pulp.LpProblem("dec_sum", pulp.LpMaximize)

        x = pulp.LpVariable("x", lowBound=0, upBound=5)
        y = pulp.LpVariable("y", lowBound=0, upBound=5)

        prob += Decimal("2") * x + Decimal("3") * y
        prob += x + y <= 6

        self._solve(prob)

        self.assertAlmostEqual(pulp.value(prob.objective), 17.0, places=4)


if __name__ == "__main__":
    unittest.main()
