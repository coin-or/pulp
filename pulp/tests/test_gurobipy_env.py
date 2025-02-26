import unittest
from typing import Any

from pulp import GUROBI, LpProblem, LpVariable, const

try:
    import gurobipy as gp
except ImportError:
    gp = None


def check_dummy_env():
    assert gp is not None
    with gp.Env(params={"OutputFlag": 0}):
        pass


def generate_lp() -> LpProblem:
    prob = LpProblem("test", const.LpMaximize)
    x = LpVariable("x", 0, 1)
    y = LpVariable("y", 0, 1)
    z = LpVariable("z", 0, 1)
    prob += x + y + z, "obj"
    prob += x + y + z <= 1, "c1"
    return prob


class GurobiEnvTests(unittest.TestCase):
    def setUp(self):
        if gp is None:
            self.skipTest("Skipping all tests in test_gurobipy_env.py")
        self.options: dict[str, Any] = {"Method": 0}
        self.env_options: dict[str, Any] = {"MemLimit": 1, "OutputFlag": 0}

    def test_gp_env(self):
        # Using gp.Env within a context manager
        assert gp is not None
        with gp.Env(params=self.env_options) as env:
            prob = generate_lp()
            solver = GUROBI(msg=False, env=env, **self.options)
            prob.solve(solver)
            solver.close()
        check_dummy_env()

    @unittest.skip("No reason")
    def test_gp_env_no_close(self):
        # Not closing results in an error for a single use license.
        assert gp is not None
        with gp.Env(params=self.env_options) as env:
            prob = generate_lp()
            solver = GUROBI(msg=False, env=env, **self.options)
            prob.solve(solver)
        self.assertRaises(gp.GurobiError, check_dummy_env)

    def test_multiple_gp_env(self):
        # Using the same env multiple times
        assert gp is not None
        with gp.Env(params=self.env_options) as env:
            solver = GUROBI(msg=False, env=env)
            prob = generate_lp()
            prob.solve(solver)
            solver.close()

            solver2 = GUROBI(msg=False, env=env)
            prob2 = generate_lp()
            prob2.solve(solver2)
            solver2.close()

        check_dummy_env()

    @unittest.skip("No reason")
    def test_backward_compatibility(self):
        """
        Backward compatibility check as previously the environment was not being
        freed. On a single-use license this passes (fails to initialise a dummy
        env).
        """
        assert gp is not None
        solver = GUROBI(msg=False, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        self.assertRaises(gp.GurobiError, check_dummy_env)
        gp.disposeDefaultEnv()
        solver.close()

    def test_manage_env(self):
        solver = GUROBI(msg=False, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

    def test_multiple_solves(self):
        solver = GUROBI(msg=False, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

        solver2 = GUROBI(msg=False, manageEnv=True, **self.options)
        prob.solve(solver2)

        solver2.close()
        check_dummy_env()

    @unittest.skip("No reason")
    def test_leak(self):
        """
        Check that we cannot initialise environments after a memory leak. On a
        single-use license this passes (fails to initialise a dummy env with a
        memory leak).
        """
        assert gp is not None
        solver = GUROBI(msg=False, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        _tmp = solver.model
        solver.close()

        solver2 = GUROBI(msg=False, **self.options)

        prob2 = generate_lp()
        prob2.solve(solver2)
        self.assertRaises(gp.GurobiError, check_dummy_env)


if __name__ == "__main__":
    unittest.main()
