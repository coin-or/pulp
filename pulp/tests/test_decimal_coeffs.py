from __future__ import annotations

import unittest
from decimal import Decimal

import pulp


class TestDecimalCoefficients(unittest.TestCase):
    def test_decimal_in_objective(self) -> None:
        x = pulp.LpVariable("x", lowBound=0, upBound=10)
        prob = pulp.LpProblem("obj_decimal", pulp.LpMaximize)

        prob += Decimal("2.5") * x
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        x_val = pulp.value(x)
        obj_val = pulp.value(prob.objective)

        self.assertIsNotNone(x_val)
        self.assertIsNotNone(obj_val)
        self.assertAlmostEqual(float(x_val), 10.0)
        self.assertAlmostEqual(float(obj_val), 25.0)

    def test_decimal_in_constraint(self) -> None:
        x = pulp.LpVariable("x", lowBound=0, upBound=10)
        prob = pulp.LpProblem("constr_decimal", pulp.LpMaximize)

        prob += x
        prob += Decimal("1") * x <= Decimal("8")
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        x_val = pulp.value(x)
        self.assertIsNotNone(x_val)
        self.assertAlmostEqual(float(x_val), 8.0)

    def test_decimal_on_left_multiplication(self) -> None:
        x = pulp.LpVariable("x", lowBound=0, upBound=10)
        expr = Decimal("3.5") * x

        self.assertIsInstance(expr, pulp.LpAffineExpression)
        self.assertAlmostEqual(float(expr[x]), 3.5)

    def test_decimal_division(self) -> None:
        x = pulp.LpVariable("x", lowBound=0)
        expr = x / Decimal("2")

        self.assertIsInstance(expr, pulp.LpAffineExpression)
        self.assertAlmostEqual(float(expr[x]), 0.5)

    def test_decimal_sum_of_expressions(self) -> None:
        x = pulp.LpVariable("x", lowBound=0)
        y = pulp.LpVariable("y", lowBound=0)

        expr = Decimal("1.5") * x + Decimal("2.5") * y + Decimal("3.0")

        self.assertIsInstance(expr, pulp.LpAffineExpression)
        self.assertAlmostEqual(float(expr[x]), 1.5)
        self.assertAlmostEqual(float(expr[y]), 2.5)
        self.assertAlmostEqual(float(expr.constant), 3.0)


if __name__ == "__main__":
    unittest.main()
