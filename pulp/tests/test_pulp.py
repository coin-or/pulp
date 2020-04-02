"""
Tests for pulp
"""
from pulp.constants import PulpError
from pulp.apis import *
from pulp import LpVariable, LpProblem, lpSum, LpConstraintVar, LpFractionConstraint
from pulp import constants as const
import unittest


def dumpTestProblem(prob):
    try:
        prob.writeLP("debug.lp")
        prob.writeMPS("debug.mps")
    except:
        print("(Failed to write the test problem.)")


class TestLoaderWithKwargs(unittest.TestLoader):
    """A test loader which allows to parse keyword arguments to the
       test case class."""
    def loadTestsFromTestCase(self, testCaseClass, **kwargs):
        """Return a suite of all tests cases contained in
           testCaseClass."""
        if issubclass(testCaseClass, unittest.suite.TestSuite):
            raise TypeError("Test cases should not be derived from " +
                            "TestSuite. Maybe you meant to derive from" +
                            " TestCase?")
        testCaseNames = self.getTestCaseNames(testCaseClass)
        if not testCaseNames and hasattr(testCaseClass, 'runTest'):
            testCaseNames = ['runTest']

        # Modification here: parse keyword arguments to testCaseClass.
        test_cases = []
        for test_case_name in testCaseNames:
            test_cases.append(testCaseClass(test_case_name, **kwargs))
        loaded_suite = self.suiteClass(test_cases)

        return loaded_suite


class PuLPTest(unittest.TestCase):

    def __init__(self, testName, solver, *args, **kwargs):
        unittest.TestCase.__init__(self, testName)
        self.solver = solver.copy()

    def test_pulp_001(self):
        """
        Test that a variable is deleted when it is suptracted to 0
        """
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        c1 = x + y <= 5
        c2 = c1 + z - z
        print("\t Testing zero subtraction")
        assert str(c2)  # will raise an exception

    def test_pulp_009(self):
        # infeasible
        prob = LpProblem("test09", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += lpSum([v for v in [x] if False]) >= 5, "c1"  # this is a 0 >=5 constraint
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing inconsistant lp solution")
        # this was a problem with use_mps=false
        if self.solver.__class__ in [PULP_CBC_CMD, COIN_CMD]:
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible], {x: 4, y: -1, z: 6, w: 0},
                          use_mps=False)
        elif self.solver.__class__ in [PULP_CHOCO_CMD, CHOCO_CMD, MIPCL_CMD]:
            # this error is not detected with mps and choco, MIPCL_CMD can only use mps files
            pass
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible, const.LpStatusNotSolved,
                                              const.LpStatusUndefined])

    def test_pulp_010(self):
        # Continuous
        prob = LpProblem("test010", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing continuous LP solution")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})

    def test_pulp_011(self):
        # Continuous Maximisation
        prob = LpProblem("test011", const.LpMaximize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing maximize continuous LP solution")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 8, w: 0})

    def test_pulp_012(self):
        # Unbounded
        prob = LpProblem("test012", const.LpMaximize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z + w, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing unbounded continuous LP solution")
        if self.solver.__class__ in [GUROBI, CPLEX_CMD, YAPOSIB, MOSEK]:
            # These solvers report infeasible or unbounded
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible, const.LpStatusUnbounded])
        elif self.solver.__class__ in [COINMP_DLL, MIPCL_CMD]:
            # COINMP_DLL is just plain wrong
            # also MIPCL_CMD
            print('\t\t Error in CoinMP and MIPCL_CMD: reports Optimal')
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
        elif self.solver.__class__ is GLPK_CMD:
            # GLPK_CMD Does not report unbounded problems, correctly
            pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
        elif self.solver.__class__ in [CPLEX_DLL, GUROBI_CMD]:
            # CPLEX_DLL Does not report unbounded problems, correctly
            # GUROBI_CMD has a very simple interface
            pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
        elif self.solver.__class__ in [PULP_CHOCO_CMD, CHOCO_CMD]:
            # choco bounds all variables. Would not return unbounded status
            pass
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])

    def test_pulp_013(self):
        # Long name
        prob = LpProblem("test013", const.LpMinimize)
        x = LpVariable("x" * 120, 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing Long Names")
        if self.solver.__class__ in [CPLEX_CMD, GLPK_CMD, GUROBI_CMD, MIPCL_CMD]:
            try:
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})
            except PulpError:
                # these solvers should raise an error'
                pass
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})

    def test_pulp_014(self):
        # repeated name
        prob = LpProblem("test014", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("x", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing repeated Names")
        if self.solver.__class__ in [COIN_CMD, COINMP_DLL, PULP_CBC_CMD,
                                CPLEX_CMD, CPLEX_DLL, CPLEX_PY,
                                GLPK_CMD, GUROBI_CMD, PULP_CHOCO_CMD, CHOCO_CMD, MIPCL_CMD, MOSEK]:
            try:
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})
            except PulpError:
                # these solvers should raise an error
                pass
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})

    def test_pulp_015(self):
        # zero constraint
        prob = LpProblem("test015", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        prob += lpSum([0, 0]) <= 0, "c5"
        print("\t Testing zero constraint")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})

    def test_pulp_016(self):
        # zero objective
        prob = LpProblem("test016", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        prob += lpSum([0, 0]) <= 0, "c5"
        print("\t Testing zero objective")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

    def test_pulp_017(self):
        # variable as objective
        prob = LpProblem("test017", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob.setObjective(x)
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        prob += lpSum([0, 0]) <= 0, "c5"
        print("\t Testing LpVariable (not LpAffineExpression) objective")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

    def test_pulp_018(self):
        # Long name in lp
        prob = LpProblem("test018", const.LpMinimize)
        x = LpVariable("x" * 90, 0, 4)
        y = LpVariable("y" * 90, -1, 1)
        z = LpVariable("z" * 90, 0)
        w = LpVariable("w" * 90, 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        if self.solver.__class__ in [PULP_CBC_CMD, COIN_CMD]:
            print("\t Testing Long lines in LP")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0},
                          use_mps=False)

    def test_pulp_019(self):
        # divide
        prob = LpProblem("test019", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += (2 * x + 2 * y).__div__(2.0) <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        print("\t Testing LpAffineExpression divide")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0})

    def test_pulp_020(self):
        # MIP
        prob = LpProblem("test020", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0, None, const.LpInteger)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        print("\t Testing MIP solution")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7})

    def test_pulp_021(self):
        # MIP with floats in objective
        prob = LpProblem("test021", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0, None, const.LpInteger)
        prob += 1.1 * x + 4.1 * y + 9.1 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        print("\t Testing MIP solution with floats in objective")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7},
                      objective=64.95)

    def test_pulp_030(self):
        # relaxed MIP
        prob = LpProblem("test030", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0, None, const.LpInteger)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        self.solver.mip = 0
        print("\t Testing MIP relaxation")
        if self.solver.__class__ in [GUROBI_CMD, PULP_CHOCO_CMD, CHOCO_CMD, MIPCL_CMD]:
            # gurobi command, choco and mipcl do not let the problem be relaxed
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 3.0, y: -0.5, z: 7})
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 3.5, y: -1, z: 6.5})

    def test_pulp_040(self):
        # Feasibility only
        prob = LpProblem("test040", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0, None, const.LpInteger)
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        print("\t Testing feasibility problem (no objective)")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

    def test_pulp_050(self):
        # Infeasible
        prob = LpProblem("test050", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0, 10)
        prob += x + y <= 5.2, "c1"
        prob += x + z >= 10.3, "c2"
        prob += -y + z == 17.5, "c3"
        print("\t Testing an infeasible problem")
        if self.solver.__class__ is GLPK_CMD:
            # GLPK_CMD return codes are not informative enough
            pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
        elif self.solver.__class__ in [CPLEX_DLL, GUROBI_CMD]:
            # CPLEX_DLL Does not solve the problem
            pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

    def test_pulp_060(self):
        # Integer Infeasible
        prob = LpProblem("test060", const.LpMinimize)
        x = LpVariable("x", 0, 4, const.LpInteger)
        y = LpVariable("y", -1, 1, const.LpInteger)
        z = LpVariable("z", 0, 10, const.LpInteger)
        prob += x + y <= 5.2, "c1"
        prob += x + z >= 10.3, "c2"
        prob += -y + z == 7.4, "c3"
        print("\t Testing an integer infeasible problem")
        if self.solver.__class__ in [GLPK_CMD, COIN_CMD, PULP_CBC_CMD, MOSEK]:
            # GLPK_CMD returns InfeasibleOrUnbounded
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible, const.LpStatusUndefined])
        elif self.solver.__class__ in [COINMP_DLL]:
            # Currently there is an error in COINMP for problems where
            # presolve eliminates too many variables
            print("\t\t Error in CoinMP to be fixed, reports Optimal")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
        elif self.solver.__class__ in [GUROBI_CMD]:
            pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

    def test_pulp_070(self):
        # Column Based modelling of test_pulp_1
        prob = LpProblem("test070", const.LpMinimize)
        obj = LpConstraintVar("obj")
        # constraints
        a = LpConstraintVar("C1", const.LpConstraintLE, 5)
        b = LpConstraintVar("C2", const.LpConstraintGE, 10)
        c = LpConstraintVar("C3", const.LpConstraintEQ, 7)

        prob.setObjective(obj)
        prob += a
        prob += b
        prob += c
        # Variables
        x = LpVariable("x", 0, 4, const.LpContinuous, obj + a + b)
        y = LpVariable("y", -1, 1, const.LpContinuous, 4 * obj + a - c)
        z = LpVariable("z", 0, None, const.LpContinuous, 9 * obj + b + c)
        print("\t Testing column based modelling")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6})

    def test_pulp_075(self):
        # Column Based modelling of test_pulp_1 with empty constraints
        prob = LpProblem("test075", const.LpMinimize)
        obj = LpConstraintVar("obj")
        # constraints
        a = LpConstraintVar("C1", const.LpConstraintLE, 5)
        b = LpConstraintVar("C2", const.LpConstraintGE, 10)
        c = LpConstraintVar("C3", const.LpConstraintEQ, 7)

        prob.setObjective(obj)
        prob += a
        prob += b
        prob += c
        # Variables
        x = LpVariable("x", 0, 4, const.LpContinuous, obj + b)
        y = LpVariable("y", -1, 1, const.LpContinuous, 4 * obj - c)
        z = LpVariable("z", 0, None, const.LpContinuous, 9 * obj + b + c)
        if self.solver.__class__ in [CPLEX_DLL, CPLEX_CMD, COINMP_DLL, YAPOSIB,
                                PYGLPK]:
            print("\t Testing column based modelling with empty constraints")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6})

    def test_pulp_080(self):
        """
        Test the reporting of dual variables slacks and reduced costs
        """
        prob = LpProblem("test080", const.LpMinimize)
        x = LpVariable("x", 0, 5)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        c1 = x + y <= 5
        c2 = x + z >= 10
        c3 = -y + z == 7

        prob += x + 4 * y + 9 * z, "obj"
        prob += c1, "c1"
        prob += c2, "c2"
        prob += c3, "c3"

        if self.solver.__class__ in [CPLEX_DLL, CPLEX_CMD, COINMP_DLL,
                                PULP_CBC_CMD, YAPOSIB, PYGLPK]:
            print("\t Testing dual variables and slacks reporting")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal],
                          sol={x: 4, y: -1, z: 6},
                          reducedcosts={x: 0, y: 12, z: 0},
                          duals={"c1": 0, "c2": 1, "c3": 8},
                          slacks={"c1": 2, "c2": 0, "c3": 0})

    def test_pulp_090(self):
        # Column Based modelling of test_pulp_1 with a resolve
        prob = LpProblem("test090", const.LpMinimize)
        obj = LpConstraintVar("obj")
        # constraints
        a = LpConstraintVar("C1", const.LpConstraintLE, 5)
        b = LpConstraintVar("C2", const.LpConstraintGE, 10)
        c = LpConstraintVar("C3", const.LpConstraintEQ, 7)

        prob.setObjective(obj)
        prob += a
        prob += b
        prob += c

        prob.setSolver(self.solver)  # Variables
        x = LpVariable("x", 0, 4, const.LpContinuous, obj + a + b)
        y = LpVariable("y", -1, 1, const.LpContinuous, 4 * obj + a - c)
        prob.resolve()
        z = LpVariable("z", 0, None, const.LpContinuous, 9 * obj + b + c)
        if self.solver.__class__ in [CPLEX_DLL, COINMP_DLL]:
            print("\t Testing resolve of problem")
            prob.resolve()
            # difficult to check this is doing what we want as the resolve is
            # over ridden if it is not implemented
            # test_pulp_Check(prob, self.solver, [const.LpStatusOptimal], {x:4, y:-1, z:6})

    def test_pulp_100(self):
        """
        Test the ability to sequentially solve a problem
        """
        # set up a cubic feasible region
        prob = LpProblem("test100", const.LpMinimize)
        x = LpVariable("x", 0, 1)
        y = LpVariable("y", 0, 1)
        z = LpVariable("z", 0, 1)

        obj1 = x + 0 * y + 0 * z
        obj2 = 0 * x - 1 * y + 0 * z
        prob += x <= 1, "c1"

        if self.solver.__class__ in [CPLEX_DLL, COINMP_DLL, GUROBI]:
            print("\t Testing Sequential Solves")
            status = prob.sequentialSolve([obj1, obj2], solver=self.solver)
            pulpTestCheck(prob, self.solver, [[const.LpStatusOptimal, const.LpStatusOptimal]],
                          sol={x: 0, y: 1},
                          status=status)

    def test_pulp_110(self):
        """
        Test the ability to use fractional constraints
        """
        prob = LpProblem("test110", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        prob += LpFractionConstraint(x, z, const.LpConstraintEQ, 0.5, name='c5')
        print("\t Testing fractional constraints")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal],
                      {x: 10 / 3.0, y: -1 / 3.0, z: 20 / 3.0, w: 0})

    def test_pulp_120(self):
        """
        Test the ability to use Elastic constraints
        """
        prob = LpProblem("test120", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w")
        prob += x + 4 * y + 9 * z + w, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob.extend((w >= -1).makeElasticSubProblem())
        print("\t Testing elastic constraints (no change)")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal],
                      {x: 4, y: -1, z: 6, w: -1})

    def test_pulp_121(self):
        """
        Test the ability to use Elastic constraints
        """
        prob = LpProblem("test121", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w")
        prob += x + 4 * y + 9 * z + w, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob.extend((w >= -1).makeElasticSubProblem(proportionFreeBound=0.1))
        print("\t Testing elastic constraints (freebound)")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal],
                      {x: 4, y: -1, z: 6, w: -1.1})

    def test_pulp_122(self):
        """
        Test the ability to use Elastic constraints (penalty unchanged)
        """
        prob = LpProblem("test122", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w")
        prob += x + 4 * y + 9 * z + w, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob.extend((w >= -1).makeElasticSubProblem(penalty=1.1))
        print("\t Testing elastic constraints (penalty unchanged)")
        pulpTestCheck(prob, self.solver, [const.LpStatusOptimal],
                      {x: 4, y: -1, z: 6, w: -1.0})

    def test_pulp_123(self):
        """
        Test the ability to use Elastic constraints (penalty unbounded)
        """
        prob = LpProblem("test123", const.LpMinimize)
        x = LpVariable("x", 0, 4)
        y = LpVariable("y", -1, 1)
        z = LpVariable("z", 0)
        w = LpVariable("w")
        prob += x + 4 * y + 9 * z + w, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob.extend((w >= -1).makeElasticSubProblem(penalty=0.9))
        print("\t Testing elastic constraints (penalty unbounded)")
        if self.solver.__class__ in [COINMP_DLL, GUROBI, CPLEX_CMD, YAPOSIB, MOSEK]:
            # COINMP_DLL Does not report unbounded problems, correctly
            pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible, const.LpStatusUnbounded])
        elif self.solver.__class__ is GLPK_CMD:
            # GLPK_CMD Does not report unbounded problems, correctly
            pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
        elif self.solver.__class__ in [CPLEX_DLL, GUROBI_CMD]:
            # GLPK_CMD Does not report unbounded problems, correctly
            pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
        elif self.solver.__class__ in [PULP_CHOCO_CMD, CHOCO_CMD]:
            # choco bounds all variables. Would not return unbounded status
            pass
        else:
            pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])


def pulpTestCheck(prob, solver, okstatus, sol=None,
                  reducedcosts=None,
                  duals=None,
                  slacks=None,
                  eps=10 ** -3,
                  status=None,
                  objective=None,
                  **kwargs):
    if status is None:
        status = prob.solve(solver, **kwargs)
    if status not in okstatus:
        dumpTestProblem(prob)
        print("Failure: status ==", status, "not in", okstatus)
        print("Failure: status ==", const.LpStatus[status], "not in", \
              [const.LpStatus[s] for s in okstatus])
        raise PulpError("Tests failed for solver %s" % solver)
    if sol is not None:
        for v, x in sol.items():
            if abs(v.varValue - x) > eps:
                dumpTestProblem(prob)
                print("Test failed: var", v, "==", v.varValue, "!=", x)
                raise PulpError("Tests failed for solver %s" % solver)
    if reducedcosts:
        for v, dj in reducedcosts.items():
            if abs(v.dj - dj) > eps:
                dumpTestProblem(prob)
                print("Test failed: var.dj", v, "==", v.dj, "!=", dj)
                raise PulpError("Tests failed for solver %s" % solver)
    if duals:
        for cname, p in duals.items():
            c = prob.constraints[cname]
            if abs(c.pi - p) > eps:
                dumpTestProblem(prob)
                print("Test failed: constraint.pi", cname, "==", c.pi, "!=", p)
                raise PulpError("Tests failed for solver %s" % solver)
    if slacks:
        for cname, slack in slacks.items():
            c = prob.constraints[cname]
            if abs(c.slack - slack) > eps:
                dumpTestProblem(prob)
                print("Test failed: constraint.slack", cname, "==",
                      c.slack, "!=", slack)
                raise PulpError("Tests failed for solver %s" % solver)
    if objective is not None:
        z = prob.objective.value()
        if abs(z - objective) > eps:
            dumpTestProblem(prob)
            print("Test failed: objective ", z, " != ", objective)
            raise PulpError("Tests failed for solver %s" % solver)


def suite():
    solvers = [PULP_CBC_CMD,
               CPLEX_DLL,
               CPLEX_CMD,
               CPLEX_PY,
               COIN_CMD,
               COINMP_DLL,
               GLPK_CMD,
               XPRESS,
               GUROBI,
               GUROBI_CMD,
               PYGLPK,
               YAPOSIB,
               PULP_CHOCO_CMD,
               MIPCL_CMD,
               MOSEK
               ]

    loader = TestLoaderWithKwargs()
    suite = unittest.TestSuite()
    for solver in solvers:
        if solver().available():
            print("Solver %s available" % solver)
            tests = loader.loadTestsFromTestCase(PuLPTest, solver=solver(msg=0))
            suite.addTests(tests)
        else:
            print("Solver %s unavailable" % solver)
    return suite


if __name__ == '__main__':
    # Tests
    runner = unittest.TextTestRunner(verbosity=0)
    runner.run(suite())
    # To run a single test:
    # suite = unittest.TestSuite()
    # suite.addTest(PuLPTest('test_pulp_060', PULP_CBC_CMD(msg=0)))
    # unittest.TextTestRunner(verbosity=0).run(suite)

