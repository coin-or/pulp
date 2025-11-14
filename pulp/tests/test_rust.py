"""
Tests for pulp
"""

import os
import unittest
from typing import Optional, Type

from pulp_rs import LpVariable

import pulp.apis as solvers

try:
    import gurobipy as gp  # type: ignore[import-not-found, import-untyped, unused-ignore]
except ImportError:
    gp = None  # type: ignore[assignment, unused-ignore]


class BaseSolverTest:
    class PuLPTest(unittest.TestCase):
        solveInst: Optional[Type[solvers.LpSolver]] = None
        solver: solvers.LpSolver

        def setUp(self):
            if self.solveInst == solvers.CUOPT:
                # cuOpt requires a user provided time limit for MIP problems
                self.solver = self.solveInst(msg=False, timeLimit=120)
            else:
                self.solver = self.solveInst(msg=False)
            if not self.solver.available():
                self.skipTest(f"solver {self.solveInst.name} not available")

        def tearDown(self):
            for ext in ["mst", "log", "lp", "mps", "sol", "out"]:
                filename = f"{self._testMethodName}.{ext}"
                try:
                    os.remove(filename)
                except:
                    pass
            pass

        def test_variable_0_is_deleted(self):
            """
            Test that a variable is deleted when it is subtracted to 0
            """
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            c1 = x + y <= 5
            c2 = c1 + z - z
            assert str(c2)
            assert c2[z] == 0

class PULP_CBC_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.PULP_CBC_CMD


if __name__ == "__main__":
    unittest.main()
