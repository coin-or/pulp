import unittest
import dataclasses

from pulp import lpDot, LpVariable


class SparseTest(unittest.TestCase):

    def test_lpdot(self):
        x = LpVariable(name="x")

        product = lpDot(1, 2 * x)
        assert [dataclasses.asdict(dc) for dc in product.toDataclass()] == [
            {"name": "x", "value": 2}
        ]

    def test_pulp_002(self):
        """
        Test the lpDot operation
        """
        x = LpVariable("x")
        y = LpVariable("y")
        z = LpVariable("z")
        a = [1, 2, 3]
        assert dict(lpDot([x, y, z], a)) == {x: 1, y: 2, z: 3}
        assert dict(lpDot([2 * x, 2 * y, 2 * z], a)) == {x: 2, y: 4, z: 6}
        assert dict(lpDot([x + y, y + z, z], a)) == {x: 1, y: 3, z: 5}
        assert dict(lpDot(a, [x + y, y + z, z])) == {x: 1, y: 3, z: 5}


if __name__ == "__main__":
    unittest.main()
