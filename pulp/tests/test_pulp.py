"""
Tests for pulp
"""
from pulp.constants import PulpError
from pulp.apis import *
from pulp import LpVariable, LpProblem, lpSum, LpConstraintVar, LpFractionConstraint
from pulp import constants as const
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.utilities import makeDict
import unittest


def dumpTestProblem(prob):
    try:
        prob.writeLP("debug.lp")
        prob.writeMPS("debug.mps")
    except:
        print("(Failed to write the test problem.)")


class BaseSolverTest:
    class PuLPTest(unittest.TestCase):
        solveInst = None

        def setUp(self):
            self.solver = self.solveInst(msg=False)
            if not self.solver.available():
                self.skipTest("solver {} not available".format(self.solveInst))

        def tearDown(self):
            for ext in ["mst", "log", "lp", "mps", "sol"]:
                filename = "{}.{}".format(self._testMethodName, ext)
                try:
                    os.remove(filename)
                except:
                    pass
            pass

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
            prob += (
                lpSum([v for v in [x] if False]) >= 5,
                "c1",
            )  # this is a 0 >=5 constraint
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            print("\t Testing inconsistent lp solution")
            # this was a problem with use_mps=false
            if self.solver.__class__ in [PULP_CBC_CMD, COIN_CMD]:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible],
                    {x: 4, y: -1, z: 6, w: 0},
                    use_mps=False,
                )
            elif self.solver.__class__ in [CHOCO_CMD, MIPCL_CMD]:
                # this error is not detected with mps and choco, MIPCL_CMD can only use mps files
                pass
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [
                        const.LpStatusInfeasible,
                        const.LpStatusNotSolved,
                        const.LpStatusUndefined,
                    ],
                )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 8, w: 0}
            )

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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUnbounded],
                )
            elif self.solver.__class__ in [COINMP_DLL, MIPCL_CMD]:
                # COINMP_DLL is just plain wrong
                # also MIPCL_CMD
                print("\t\t Error in CoinMP and MIPCL_CMD: reports Optimal")
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ is GLPK_CMD:
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.__class__ in [GUROBI_CMD, SCIP_CMD]:
                # GUROBI_CMD has a very simple interface
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [CHOCO_CMD]:
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
            if self.solver.__class__ in [
                CPLEX_CMD,
                GLPK_CMD,
                GUROBI_CMD,
                MIPCL_CMD,
                SCIP_CMD,
            ]:
                try:
                    pulpTestCheck(
                        prob,
                        self.solver,
                        [const.LpStatusOptimal],
                        {x: 4, y: -1, z: 6, w: 0},
                    )
                except PulpError:
                    # these solvers should raise an error'
                    pass
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

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
            if self.solver.__class__ in [
                COIN_CMD,
                COINMP_DLL,
                PULP_CBC_CMD,
                CPLEX_CMD,
                CPLEX_PY,
                GLPK_CMD,
                GUROBI_CMD,
                CHOCO_CMD,
                MIPCL_CMD,
                MOSEK,
                SCIP_CMD,
            ]:
                try:
                    pulpTestCheck(
                        prob,
                        self.solver,
                        [const.LpStatusOptimal],
                        {x: 4, y: -1, z: 6, w: 0},
                    )
                except PulpError:
                    # these solvers should raise an error
                    pass
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                    use_mps=False,
                )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

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
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 3, y: -0.5, z: 7},
                objective=64.95,
            )

        def test_pulp_022(self):
            # Initial value
            prob = LpProblem("test022", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            x.setInitialValue(3)
            y.setInitialValue(-0.5)
            z.setInitialValue(7)
            if self.solver.name in ["GUROBI", "GUROBI_CMD", "CPLEX_CMD", "CPLEX_PY"]:
                self.solver.optionsDict["warmStart"] = True
            print("\t Testing Initial value in MIP solution")
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_pulp_023(self):
            # Initial value (fixed)
            prob = LpProblem("test023", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            solution = {x: 4, y: -0.5, z: 7}
            for v in [x, y, z]:
                v.setInitialValue(solution[v])
                v.fixValue()
            self.solver.optionsDict["warmStart"] = True
            print("\t Testing fixing value in MIP solution")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], solution)

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
            if self.solver.__class__ in [
                GUROBI_CMD,
                CHOCO_CMD,
                MIPCL_CMD,
                SCIP_CMD,
            ]:
                # gurobi command, choco and mipcl do not let the problem be relaxed
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 3.0, y: -0.5, z: 7}
                )
            else:
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 3.5, y: -1, z: 6.5}
                )

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
            elif self.solver.__class__ in [GUROBI_CMD]:
                # GUROBI_CMD Does not solve the problem
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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            elif self.solver.__class__ in [COINMP_DLL]:
                # Currently there is an error in COINMP for problems where
                # presolve eliminates too many variables
                print("\t\t Error in CoinMP to be fixed, reports Optimal")
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ in [GUROBI_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_pulp_061(self):
            # Integer Infeasible
            prob = LpProblem("sample", const.LpMaximize)

            dummy = LpVariable("dummy")
            c1 = LpVariable("c1", 0, 1, const.LpBinary)
            c2 = LpVariable("c2", 0, 1, const.LpBinary)

            prob += dummy
            prob += c1 + c2 == 2
            prob += c1 <= 0
            print("\t Testing another integer infeasible problem")
            if self.solver.__class__ in [GUROBI_CMD, SCIP_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [GLPK_CMD]:
                # GLPK_CMD returns InfeasibleOrUnbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6}
            )

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
            if self.solver.__class__ in [
                CPLEX_CMD,
                COINMP_DLL,
                YAPOSIB,
                PYGLPK,
            ]:
                print("\t Testing column based modelling with empty constraints")
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6}
                )

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

            if self.solver.__class__ in [
                CPLEX_CMD,
                COINMP_DLL,
                PULP_CBC_CMD,
                YAPOSIB,
                PYGLPK,
            ]:
                print("\t Testing dual variables and slacks reporting")
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    sol={x: 4, y: -1, z: 6},
                    reducedcosts={x: 0, y: 12, z: 0},
                    duals={"c1": 0, "c2": 1, "c3": 8},
                    slacks={"c1": 2, "c2": 0, "c3": 0},
                )

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
            if self.solver.__class__ in [COINMP_DLL]:
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

            if self.solver.__class__ in [COINMP_DLL, GUROBI]:
                print("\t Testing Sequential Solves")
                status = prob.sequentialSolve([obj1, obj2], solver=self.solver)
                pulpTestCheck(
                    prob,
                    self.solver,
                    [[const.LpStatusOptimal, const.LpStatusOptimal]],
                    sol={x: 0, y: 1},
                    status=status,
                )

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
            prob += LpFractionConstraint(x, z, const.LpConstraintEQ, 0.5, name="c5")
            print("\t Testing fractional constraints")
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 10 / 3.0, y: -1 / 3.0, z: 20 / 3.0, w: 0},
            )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1}
            )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1.1}
            )

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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1.0}
            )

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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUnbounded],
                )
            elif self.solver.__class__ is GLPK_CMD:
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.__class__ in [GUROBI_CMD, SCIP_CMD]:
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [CHOCO_CMD]:
                # choco bounds all variables. Would not return unbounded status
                pass
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])

        def test_pulpTestAll(self):
            """
            Test the availability of the function pulpTestAll
            """
            print("\t Testing the availability of the function pulpTestAll")
            from pulp import pulpTestAll

        def test_export_dict_LP(self):
            prob = LpProblem("test_export_dict_LP", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            data = prob.toDict()
            var1, prob1 = LpProblem.fromDict(data)
            x, y, z, w = [var1[name] for name in ["x", "y", "z", "w"]]
            print("\t Testing continuous LP solution - export dict")
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_dict_LP_no_obj(self):
            prob = LpProblem("test_export_dict_LP_no_obj", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0, 0)
            prob += x + y >= 5, "c1"
            prob += x + z == 10, "c2"
            prob += -y + z <= 7, "c3"
            prob += w >= 0, "c4"
            data = prob.toDict()
            var1, prob1 = LpProblem.fromDict(data)
            x, y, z, w = [var1[name] for name in ["x", "y", "z", "w"]]
            print("\t Testing export dict for LP")
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 6, w: 0}
            )

        def test_export_json_LP(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            filename = name + ".json"
            prob.toJson(filename, indent=4)
            var1, prob1 = LpProblem.fromJson(filename)
            try:
                os.remove(filename)
            except:
                pass
            x, y, z, w = [var1[name] for name in ["x", "y", "z", "w"]]
            print("\t Testing continuous LP solution - export JSON")
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_dict_MIP(self):
            import copy

            prob = LpProblem("test_export_dict_MIP", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            data = prob.toDict()
            data_backup = copy.deepcopy(data)
            var1, prob1 = LpProblem.fromDict(data)
            x, y, z = [var1[name] for name in ["x", "y", "z"]]
            print("\t Testing export dict MIP")
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )
            # we also test that we have not modified the dictionary when importing it
            self.assertDictEqual(data, data_backup)

        def test_export_dict_max(self):
            prob = LpProblem("test_export_dict_max", const.LpMaximize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            data = prob.toDict()
            var1, prob1 = LpProblem.fromDict(data)
            x, y, z, w = [var1[name] for name in ["x", "y", "z", "w"]]
            print("\t Testing maximize continuous LP solution")
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 8, w: 0}
            )

        def test_export_solver_dict_LP(self):
            prob = LpProblem("test_export_dict_LP", const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            data = self.solver.toDict()
            solver1 = getSolverFromDict(data)
            print("\t Testing continuous LP solution - export solver dict")
            pulpTestCheck(
                prob, solver1, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_solver_json(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self.solver.mip = True
            logFilename = name + ".log"
            if self.solver.name == "CPLEX_CMD":
                self.solver.optionsDict = dict(
                    gapRel=0.1,
                    gapAbs=1,
                    maxMemory=1000,
                    maxNodes=1,
                    threads=1,
                    logPath=logFilename,
                    warmStart=True,
                )
            elif self.solver.name in ["GUROBI_CMD", "COIN_CMD", "PULP_CBC_CMD"]:
                self.solver.optionsDict = dict(
                    gapRel=0.1, gapAbs=1, threads=1, logPath=logFilename, warmStart=True
                )
            filename = name + ".json"
            self.solver.toJson(filename, indent=4)
            solver1 = getSolverFromJson(filename)
            try:
                os.remove(filename)
            except:
                pass
            print("\t Testing continuous LP solution - export solver JSON")
            pulpTestCheck(
                prob, solver1, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_timeLimit(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self.solver.timeLimit = 20
            # CHOCO has issues when given a time limit
            print("\t Testing timeLimit argument")
            if self.solver.name != "CHOCO_CMD":
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_assignInvalidStatus(self):
            print("\t Testing invalid status")
            t = LpProblem("test")
            Invalid = -100
            self.assertRaises(const.PulpError, lambda: t.assignStatus(Invalid))
            self.assertRaises(const.PulpError, lambda: t.assignStatus(0, Invalid))

        def test_logPath(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            logFilename = name + ".log"
            self.solver.optionsDict["logPath"] = logFilename
            if self.solver.name in [
                "CPLEX_PY",
                "CPLEX_CMD",
                "GUROBI",
                "GUROBI_CMD",
                "PULP_CBC_CMD",
                "COIN_CMD",
            ]:
                print("\t Testing logPath argument")
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )
                if not os.path.exists(logFilename):
                    raise PulpError("Test failed for solver: {}".format(self.solver))
                if not os.path.getsize(logFilename):
                    raise PulpError("Test failed for solver: {}".format(self.solver))

        def test_makeDict_behavior(self):
            """
            Test if makeDict is returning the expected value.
            """
            headers = [["A", "B"], ["C", "D"]]
            values = [[1, 2], [3, 4]]
            target = {"A": {"C": 1, "D": 2}, "B": {"C": 3, "D": 4}}
            dict_with_default = makeDict(headers, values, default=0)
            dict_without_default = makeDict(headers, values)
            print("\t Testing makeDict general behavior")
            self.assertEqual(dict_with_default, target)
            self.assertEqual(dict_without_default, target)

        def test_makeDict_default_value(self):
            """
            Test if makeDict is returning a default value when specified.
            """
            headers = [["A", "B"], ["C", "D"]]
            values = [[1, 2], [3, 4]]
            dict_with_default = makeDict(headers, values, default=0)
            dict_without_default = makeDict(headers, values)
            print("\t Testing makeDict default value behavior")
            # Check if a default value is passed
            self.assertEqual(dict_with_default["X"]["Y"], 0)
            # Check if a KeyError is raised
            _func = lambda: dict_without_default["X"]["Y"]
            self.assertRaises(KeyError, _func)

        def test_importMPS_maximize(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            filename = name + ".mps"
            prob.writeMPS(filename)
            _vars, prob2 = LpProblem.fromMPS(filename, sense=prob.sense)
            _dict1 = getSortedDict(prob)
            _dict2 = getSortedDict(prob2)
            print("\t Testing reading MPS files - maximize")
            self.assertDictEqual(_dict1, _dict2)

        def test_importMPS_integer(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += 1.1 * x + 4.1 * y + 9.1 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            filename = name + ".mps"
            prob.writeMPS(filename)
            _vars, prob2 = LpProblem.fromMPS(filename, sense=prob.sense)
            _dict1 = getSortedDict(prob)
            _dict2 = getSortedDict(prob2)
            print("\t Testing reading MPS files - integer variable")
            self.assertDictEqual(_dict1, _dict2)

        def test_importMPS_binary(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            dummy = LpVariable("dummy")
            c1 = LpVariable("c1", 0, 1, const.LpBinary)
            c2 = LpVariable("c2", 0, 1, const.LpBinary)
            prob += dummy
            prob += c1 + c2 == 2
            prob += c1 <= 0
            filename = name + ".mps"
            prob.writeMPS(filename)
            _vars, prob2 = LpProblem.fromMPS(
                filename, sense=prob.sense, dropConsNames=True
            )
            _dict1 = getSortedDict(prob, keyCons="constant")
            _dict2 = getSortedDict(prob2, keyCons="constant")
            print("\t Testing reading MPS files - binary variable, no constraint names")
            self.assertDictEqual(_dict1, _dict2)

        # def test_importMPS_2(self):
        #     name = self._testMethodName
        #     # filename = name + ".mps"
        #     filename = "/home/pchtsp/Downloads/test.mps"
        #     _vars, _prob = LpProblem.fromMPS(filename)
        #     _prob.solve()
        #     for k, v in _vars.items():
        #         print(k, v.value())

        def test_unset_objective_value__is_valid(self):
            """Given a valid problem that does not converge,
            assert that it is still categorised as valid.
            """
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = LpVariable("x")
            prob += 0 * x
            prob += x >= 1
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            self.assertTrue(prob.valid())

        def test_unbounded_problem__is_not_valid(self):
            """Given an unbounded problem, where x will tend to infinity
            to maximise the objective, assert that it is categorised
            as invalid."""
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = LpVariable("x")
            prob += 1000 * x
            prob += x >= 1
            self.assertFalse(prob.valid())

        def test_infeasible_problem__is_not_valid(self):
            """Given a problem where x cannot converge to any value
            given conflicting constraints, assert that it is invalid."""
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = LpVariable("x")
            prob += 1 * x
            prob += x >= 2  # Constraint x to be more than 2
            prob += x <= 1  # Constraint x to be less than 1
            if self.solver.name in ["GUROBI_CMD"]:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [
                        const.LpStatusNotSolved,
                        const.LpStatusInfeasible,
                        const.LpStatusUndefined,
                    ],
                )
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            self.assertFalse(prob.valid())

        def test_false_constraint(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)

            def add_const(prob):
                prob += 0 - 3 == 0

            self.assertRaises(TypeError, add_const, prob=prob)

        def test_measuring_solving_time(self):
            print("\t Testing measuring optimization time")

            time_limit = 10
            solver_settings = dict(
                PULP_CBC_CMD=30, COIN_CMD=30, SCIP_CMD=30, GUROBI_CMD=50, CPLEX_CMD=50
            )
            bins = solver_settings.get(self.solver.name)
            if bins is None:
                # not all solvers have timeLimit support
                return
            prob = create_bin_packing_problem(bins=bins, seed=99)
            self.solver.timeLimit = time_limit
            prob.solve(self.solver)
            delta = 4
            reported_time = prob.solutionTime
            if self.solver.name in ["PULP_CBC_CMD", "COIN_CMD"]:
                # CBC is less exact with the timeLimit
                reported_time = prob.solutionCpuTime
                delta = 5

            self.assertAlmostEqual(
                reported_time,
                time_limit,
                delta=delta,
                msg="optimization time for solver {}".format(self.solver.name),
            )

        def test_invalid_var_names(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("a")
            w = LpVariable("b")
            y = LpVariable("g", -1, 1)
            z = LpVariable("End")
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            print("\t Testing invalid var names")
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_LpVariable_indexs_param(self):
            """
            Test that 'indexs' param continues to work
            """

            prob = LpProblem(self._testMethodName, const.LpMinimize)
            customers = [1, 2, 3]
            agents = ["A", "B", "C"]

            print("\t Testing 'indexs' param continues to work for LpVariable.dicts")
            # explicit param creates a dict of type LpVariable
            assign_vars = LpVariable.dicts(name="test", indexs=(customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # param by position creates a dict of type LpVariable
            assign_vars = LpVariable.dicts("test", (customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            print("\t Testing 'indexs' param continues to work for LpVariable.matrix")
            # explicit param creates list of list of LpVariable
            assign_vars_matrix = LpVariable.matrix(
                name="test", indexs=(customers, agents)
            )
            for a in assign_vars_matrix:
                for b in a:
                    self.assertIsInstance(b, LpVariable)

            # param by position creates list of list of LpVariable
            assign_vars_matrix = LpVariable.matrix("test", (customers, agents))
            for a in assign_vars_matrix:
                for b in a:
                    self.assertIsInstance(b, LpVariable)

        def test_LpVariable_indices_param(self):
            """
            Test that 'indices' argument works
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            customers = [1, 2, 3]
            agents = ["A", "B", "C"]

            print("\t Testing 'indices' argument works in LpVariable.dicts")
            # explicit param creates a dict of type LpVariable
            assign_vars = LpVariable.dicts(name="test", indices=(customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            print("\t Testing 'indices' param continues to work for LpVariable.matrix")
            # explicit param creates list of list of LpVariable
            assign_vars_matrix = LpVariable.matrix(
                name="test", indices=(customers, agents)
            )
            for a in assign_vars_matrix:
                for b in a:
                    self.assertIsInstance(b, LpVariable)

        def test_LpVariable_indexs_deprecation_logic(self):
            """
            Test that logic put in place for deprecation handling of indexs works
            """
            print(
                "\t Test that logic put in place for deprecation handling of indexs works"
            )
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            customers = [1, 2, 3]
            agents = ["A", "B", "C"]

            with self.assertRaises(TypeError):
                # both variables
                assign_vars_matrix = LpVariable.dicts(
                    name="test",
                    indices=(customers, agents),
                    indexs=(customers, agents),
                )

            with self.assertRaises(TypeError):
                # no variables
                assign_vars_matrix = LpVariable.dicts(
                    name="test",
                )

            # Not supported in 2.7.  Introduced to unittest in 3.2
            # with self.assertWarns(DeprecationWarning):
            #    assign_vars_matrix = LpVariable.dicts(
            #        name="test",
            #        indexs=(customers, agents),
            #    )


class PULP_CBC_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = PULP_CBC_CMD


class CPLEX_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = CPLEX_CMD


class CPLEX_PYTest(BaseSolverTest.PuLPTest):
    solveInst = CPLEX_CMD


class XPRESSTest(BaseSolverTest.PuLPTest):
    solveInst = XPRESS


class COIN_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = COIN_CMD


class COINMP_DLLTest(BaseSolverTest.PuLPTest):
    solveInst = COINMP_DLL


class GLPK_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = GLPK_CMD


class GUROBITest(BaseSolverTest.PuLPTest):
    solveInst = GUROBI


class GUROBI_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = GUROBI_CMD


class PYGLPKTest(BaseSolverTest.PuLPTest):
    solveInst = PYGLPK


class YAPOSIBTest(BaseSolverTest.PuLPTest):
    solveInst = YAPOSIB


class CHOCO_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = CHOCO_CMD


class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = MIPCL_CMD


class MOSEKTest(BaseSolverTest.PuLPTest):
    solveInst = MOSEK


class SCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = SCIP_CMD


def pulpTestCheck(
    prob,
    solver,
    okstatus,
    sol=None,
    reducedcosts=None,
    duals=None,
    slacks=None,
    eps=10 ** -3,
    status=None,
    objective=None,
    **kwargs
):
    if status is None:
        status = prob.solve(solver, **kwargs)
    if status not in okstatus:
        dumpTestProblem(prob)
        raise PulpError(
            "Tests failed for solver {}:\nstatus == {} not in {}\nstatus == {} not in {}".format(
                solver,
                status,
                okstatus,
                const.LpStatus[status],
                [const.LpStatus[s] for s in okstatus],
            )
        )
    if sol is not None:
        for v, x in sol.items():
            if abs(v.varValue - x) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nvar {} == {} != {}".format(
                        solver, v, v.varValue, x
                    )
                )
    if reducedcosts:
        for v, dj in reducedcosts.items():
            if abs(v.dj - dj) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nTest failed: var.dj {} == {} != {}".format(
                        solver, v, v.dj, dj
                    )
                )
    if duals:
        for cname, p in duals.items():
            c = prob.constraints[cname]
            if abs(c.pi - p) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nconstraint.pi {} == {} != {}".format(
                        solver, cname, c.pi, p
                    )
                )
    if slacks:
        for cname, slack in slacks.items():
            c = prob.constraints[cname]
            if abs(c.slack - slack) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nconstraint.slack {} == {} != {}".format(
                        solver, cname, c.slack, slack
                    )
                )
    if objective is not None:
        z = prob.objective.value()
        if abs(z - objective) > eps:
            dumpTestProblem(prob)
            raise PulpError(
                "Tests failed for solver {}:\nobjective {} != {}".format(
                    solver, z, objective
                )
            )


def getSortedDict(prob, keyCons="name", keyVars="name"):
    _dict = prob.toDict()
    _dict["constraints"].sort(key=lambda v: v[keyCons])
    _dict["variables"].sort(key=lambda v: v[keyVars])
    return _dict


if __name__ == "__main__":
    unittest.main()
