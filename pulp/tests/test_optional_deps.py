"""PuLP works without its optional dependencies."""

import subprocess
import sys
import textwrap
import unittest

# numpy is only needed by some solver APIs (HiGHS, CyLP, Clarabel...): blocked in
# sys.modules, any import of it raises ImportError
_WITHOUT_NUMPY = textwrap.dedent(
    """
    import sys

    sys.modules["numpy"] = None
    import pulp

    for solver in (pulp.HiGHS, pulp.CYLP, pulp.CLARABEL, pulp.CUOPT):
        assert not solver(msg=False).available(), solver.name
    solver = pulp.COIN_CMD(msg=False)
    if solver.available():
        prob = pulp.LpProblem("no_numpy", pulp.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        prob += x
        prob += x >= 1, "c1"
        stats = prob.solve(solver)
        assert stats.status == pulp.LpSolveStatus.Optimal, stats.status
        assert x.varValue == 1, x.varValue
    """
)

# scipy is only needed by Clarabel, which also needs numpy
_WITHOUT_SCIPY = textwrap.dedent(
    """
    import sys

    sys.modules["scipy"] = None
    sys.modules["scipy.sparse"] = None
    import pulp

    assert not pulp.CLARABEL(msg=False).available()
    """
)


class OptionalDependenciesTest(unittest.TestCase):
    def test_without_numpy(self):
        result = subprocess.run(
            [sys.executable, "-c", _WITHOUT_NUMPY], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_without_scipy(self):
        result = subprocess.run(
            [sys.executable, "-c", _WITHOUT_SCIPY], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
