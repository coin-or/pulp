import unittest

from pulp import LpProblem, const


class RustCoreSmokeTest(unittest.TestCase):
    def test_to_rust_model_available(self):
        prob = LpProblem("rust_smoke", const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 5)
        prob += x + y
        prob += x + 2 * y <= 7, "c1"

        self.assertTrue(hasattr(prob, "toRustModel"))

        model = prob.toRustModel()

        self.assertEqual(model.num_variables, 2)
        self.assertEqual(model.num_constraints, 1)
        summary = model.summary()
        self.assertIn("vars=2", summary)
        self.assertIn("constraints=1", summary)


if __name__ == "__main__":
    unittest.main()
