import unittest
from typing import Any

from pulp import GUROBI, LpProblem, const

gp: Any = None
try:
    import gurobipy as gp  # type: ignore[import-not-found, import-untyped]
except ImportError:
    pass


def check_dummy_env():
    with gp.Env(params={"OutputFlag": 0}):
        pass


def is_single_use_license() -> bool:
    if gp is None:
        # no gurobi license
        return False
    try:
        with gp.Env():
            with gp.Env():
                pass
    except gp.GurobiError as ge:
        if ge.errno == gp.GRB.Error.NO_LICENSE:
            print("single use license")
            print(f"Error code {ge.errno}: {ge}")
            return True
    return False


def generate_lp() -> LpProblem:
    prob = LpProblem("test", const.LpMaximize)
    x = prob.add_variable("x", 0, 1)
    y = prob.add_variable("y", 0, 1)
    z = prob.add_variable("z", 0, 1)
    prob += x + y + z, "obj"
    prob += x + y + z <= 1, "c1"
    return prob


class GurobiEnvTests(unittest.TestCase):
    def setUp(self):
        if gp is None:
            self.skipTest("Skipping all tests in test_gurobipy_env.py")
        self.options: Any = {"Method": 0}
        self.env_options: Any = {"MemLimit": 1, "OutputFlag": 0}

    def test_gp_env(self):
        # Using gp.Env within a context manager
        with gp.Env(params=self.env_options) as env:
            prob = generate_lp()
            solver: Any = GUROBI(msg=False, env=env, **self.options)
            prob.solve(solver)
            solver.close()
        check_dummy_env()

    def test_gp_env_no_close(self):
        if not is_single_use_license():
            raise unittest.SkipTest(
                "this test is only expected to pass with a single-use license"
            )
        # Not closing results in an error for a single use license.
        with gp.Env(params=self.env_options) as env:
            prob = generate_lp()
            solver: Any = GUROBI(msg=False, env=env, **self.options)
            prob.solve(solver)
        self.assertRaises(gp.GurobiError, check_dummy_env)

    def test_multiple_gp_env(self):
        # Using the same env multiple times
        with gp.Env(params=self.env_options) as env:
            solver: Any = GUROBI(msg=False, env=env)
            prob = generate_lp()
            prob.solve(solver)
            solver.close()

            solver2: Any = GUROBI(msg=False, env=env)
            prob2 = generate_lp()
            prob2.solve(solver2)
            solver2.close()

        check_dummy_env()

    def test_backward_compatibility(self):
        """
        Backward compatibility check as previously the environment was not being
        freed. On a single-use license this passes (fails to initialise a dummy
        env).
        """
        if not is_single_use_license():
            raise unittest.SkipTest(
                "this test is only expected to pass with a single-use license"
            )
        solver: Any = GUROBI(msg=False, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        self.assertRaises(gp.GurobiError, check_dummy_env)
        gp.disposeDefaultEnv()
        solver.close()

    def test_manage_env(self):
        solver: Any = GUROBI(msg=False, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

    def test_multiple_solves(self):
        solver: Any = GUROBI(msg=False, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

        solver2: Any = GUROBI(msg=False, manageEnv=True, **self.options)
        prob.solve(solver2)

        solver2.close()
        check_dummy_env()

    def test_leak(self):
        """
        Check that we cannot initialise environments after a memory leak. On a
        single-use license this passes (fails to initialise a dummy env with a
        memory leak).
        """
        if not is_single_use_license():
            raise unittest.SkipTest(
                "this test is only expected to pass with a single-use license"
            )
        solver: Any = GUROBI(msg=False, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()

        solver2: Any = GUROBI(msg=False, **self.options)

        prob2 = generate_lp()
        prob2.solve(solver2)
        self.assertRaises(gp.GurobiError, check_dummy_env)
