import unittest

import pulp
from pulp import LpProblem, LpVariable, const


class RustCoreSmokeTest(unittest.TestCase):
    def test_to_rust_model_available(self):
        prob = LpProblem("rust_smoke", const.LpMinimize)
        x = LpVariable("x", 0, 10)
        y = LpVariable("y", 0, 5)
        prob += x + y, "obj"
        prob += x + 2 * y <= 7, "c1"

        self.assertTrue(hasattr(prob, "toRustModel"))

        # The Rust extension is a hard dependency in this design, so
        # `toRustModel` must succeed and return a live Rust model.
        model = prob.toRustModel()

        # Basic structural checks for the mirrored model.
        self.assertEqual(model.num_variables, 2)
        self.assertEqual(model.num_constraints, 1)
        summary = model.summary()
        self.assertIn("vars=2", summary)
        self.assertIn("constraints=1", summary)


if __name__ == "__main__":
    unittest.main()

