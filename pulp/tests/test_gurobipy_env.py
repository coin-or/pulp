import unittest

import gurobipy as gp


from pulp import GUROBI, GUROBI_CMD, LpProblem, LpVariable, const


def check_dummy_env():
    with gp.Env():
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
        self.options = {"OutputFlag": 1}
        self.env_options = {"MemLimit": 1}

    def test_gp_env(self):
        # Using gp.Env within a context manager
        with gp.Env(params=self.env_options) as env:
            prob = generate_lp()
            solver = GUROBI(msg=True, env=env, **self.options)
            prob.solve(solver)
            solver.close()
        check_dummy_env()

    def test_multiple_gp_env(self):
        # Using the same env multiple times
        with gp.Env() as env:
            solver = GUROBI(msg=True, env=env)
            prob = generate_lp()
            prob.solve(solver)
            solver.close()

            solver2 = GUROBI(msg=True, env=env)
            prob2 = generate_lp()
            prob2.solve(solver2)
            solver2.close()

        check_dummy_env()

    @unittest.SkipTest
    def test_backward_compatibility(self):
        """
        Backward compatibility check as previously the environment was not being
        freed. On a single-use license this passes (fails to initialise a dummy
        env).
        """
        solver = GUROBI(msg=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        self.assertRaises(gp.GurobiError, check_dummy_env)
        gp.disposeDefaultEnv()
        solver.close()

    def test_manage_env(self):
        solver = GUROBI(msg=True, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

    def test_multiple_solves(self):
        solver = GUROBI(msg=True, manageEnv=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        solver.close()
        check_dummy_env()

        solver2 = GUROBI(msg=True, manageEnv=True, **self.options)
        prob.solve(solver2)

        solver2.close()
        check_dummy_env()

    @unittest.SkipTest
    def test_leak(self):
        """
        Check that we cannot initialise environments after a memory leak. On a
        single-use license this passes (fails to initialise a dummy env with a
        memory leak).
        """
        solver = GUROBI(msg=True, **self.options)
        prob = generate_lp()
        prob.solve(solver)

        tmp = solver.model
        solver.close()

        solver2 = GUROBI(msg=True, **self.options)

        prob2 = generate_lp()
        prob2.solve(solver2)
        self.assertRaises(gp.GurobiError, check_dummy_env)
