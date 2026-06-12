import unittest

from pulp import LpProblem, lpDot


class TestLpDot(unittest.TestCase):
    def test_lpdot(self):
        prob = LpProblem("test")
        x = prob.add_variable("x")

        product = lpDot(1, 2 * x)
        self.assertListEqual(product.toDict(), [{"name": "x", "value": 2}])

    def test_pulp_002(self):
        """
        Test the lpDot operation
        """
        prob = LpProblem("test")
        x = prob.add_variable("x")
        y = prob.add_variable("y")
        z = prob.add_variable("z")
        a = [1, 2, 3]
        self.assertDictEqual(dict(lpDot([x, y, z], a)), {x: 1, y: 2, z: 3})
        self.assertDictEqual(dict(lpDot([2 * x, 2 * y, 2 * z], a)), {x: 2, y: 4, z: 6})
        self.assertDictEqual(dict(lpDot([x + y, y + z, z], a)), {x: 1, y: 3, z: 5})
        self.assertDictEqual(dict(lpDot(a, [x + y, y + z, z])), {x: 1, y: 3, z: 5})
