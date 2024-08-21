from pulp import lpDot, LpVariable


def test_lpdot():
    x = LpVariable(name="x")

    product = lpDot(1, 2 * x)
    assert product.toDict() == [{"name": "x", "value": 2}]
