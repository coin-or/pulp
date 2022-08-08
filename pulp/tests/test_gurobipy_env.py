import unittest

from pulp import GUROBI, LpProblem, LpVariable, const


class GurobiEnvTests(unittest.TestCase):
    def setUp(self):
        self.options = {"OutputFlag": 1, "MemLimit": 1}
        self.prob = LpProblem("test011", const.LpMaximize)
        x = LpVariable("x", 0, 1)
        y = LpVariable("y", 0, 1)
        z = LpVariable("z", 0, 1)
        self.prob += x + y + z, "obj"
        self.prob += x + y + z <= 1, "c1"

    def testContextManager(self):
        # Using solver within a context manager
        with GUROBI(msg=True, **self.options) as solver:
            status = self.prob.solve(solver)

    def testGpEnv(self):
        # Using gp.Env within a context manager
        import gurobipy as gp

        with gp.Env() as env:
            solver = GUROBI(msg=True, manageEnv=False, env=env, **self.options)
            self.prob.solve(solver)

    def testDefault(self):
        solver = GUROBI(msg=True, **self.options)
        self.prob.solve(solver)

    def testNoEnv(self):
        # Failing test for no environment handling
        solver = GUROBI(msg=True, manageEnv=False, envOptions=self.options)
        self.assertRaises(AttributeError, self.prob.solve, solver)
