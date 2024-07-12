"""
Tests for pulp
"""

import tempfile

from pulp.constants import PulpError
from pulp.apis import *
from pulp import LpVariable, LpProblem, lpSum, LpConstraintVar, LpFractionConstraint
from pulp import constants as const
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.utilities import makeDict
import functools
import unittest

try:
    import gurobipy as gp
except ImportError:
    gp = None

# from: http://lpsolve.sourceforge.net/5.5/mps-format.htm
EXAMPLE_MPS_RHS56 = """NAME          TESTPROB
ROWS
 N  COST
 L  LIM1
 G  LIM2
 E  MYEQN
COLUMNS
    XONE      COST                 1   LIM1                 1
    XONE      LIM2                 1
    YTWO      COST                 4   LIM1                 1
    YTWO      MYEQN               -1
    ZTHREE    COST                 9   LIM2                 1
    ZTHREE    MYEQN                1
RHS
    RHS1      LIM1                 5   LIM2                10
    RHS1      MYEQN                7
BOUNDS
 UP BND1      XONE                 4
 LO BND1      YTWO                -1
 UP BND1      YTWO                 1
ENDATA
"""

EXAMPLE_MPS_PL_BOUNDS = EXAMPLE_MPS_RHS56.replace(
    "LO BND1      YTWO                -1", "PL BND1      YTWO                  "
)


def gurobi_test(test_item):
    @functools.wraps(test_item)
    def skip_wrapper(test_obj, *args, **kwargs):
        if not test_obj.solver.name in ["GUROBI", "GUROBI_CMD"]:
            # if we're not testing gurobi, we do not care on the licence
            return test_item(test_obj, *args, **kwargs)
        if gp is None:
            raise unittest.SkipTest("No gurobipy, can't check license")
        try:
            return test_item(test_obj, *args, **kwargs)
        except gp.GurobiError as ge:
            # Skip the test if the failure was due to licensing
            if ge.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
                raise unittest.SkipTest("Size-limited Gurobi license")
            if ge.errno == gp.GRB.Error.NO_LICENSE:
                raise unittest.SkipTest("No Gurobi license")
            # Otherwise, let the error go through as-is
            raise

    return skip_wrapper


def dumpTestProblem(prob):
    try:
        prob.writeLP("debug.lp")
        prob.writeMPS("debug.mps")
    except:
        pass


class BaseSolverTest:
    class PuLPTest(unittest.TestCase):
        solveInst = None

        def setUp(self):
            self.solver = self.solveInst(msg=False)
            if not self.solver.available():
                self.skipTest(f"solver {self.solveInst.name} not available")

        def tearDown(self):
            for ext in ["mst", "log", "lp", "mps", "sol"]:
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

        def test_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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

        def test_continuous(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_continuous_max(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 8, w: 0}
            )

        def test_unbounded(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.__class__ in [GUROBI, CPLEX_CMD, YAPOSIB, MOSEK, COPT]:
                # These solvers report infeasible or unbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUnbounded],
                )
            elif self.solver.__class__ in [COINMP_DLL, MIPCL_CMD]:
                # COINMP_DLL is just plain wrong
                # also MIPCL_CMD
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ is GLPK_CMD:
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.__class__ in [GUROBI_CMD, SCIP_CMD, FSCIP_CMD, SCIP_PY]:
                # GUROBI_CMD has a very simple interface
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [CHOCO_CMD, HiGHS_CMD]:
                # choco bounds all variables. Would not return unbounded status
                # highs_cmd is inconsistent
                pass
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])

        def test_long_var_name(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x" * 120, 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.__class__ in [
                CPLEX_CMD,
                GLPK_CMD,
                GUROBI_CMD,
                MIPCL_CMD,
                SCIP_CMD,
                FSCIP_CMD,
                SCIP_PY,
                HiGHS,
                HiGHS_CMD,
                XPRESS,
                XPRESS_CMD,
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

        def test_repeated_name(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("x", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
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
                FSCIP_CMD,
                SCIP_PY,
                HiGHS,
                HiGHS_CMD,
                XPRESS,
                XPRESS_CMD,
                XPRESS_PY,
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

        def test_zero_constraint(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_no_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_variable_as_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_longname_lp(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                    use_mps=False,
                )

        def test_divide(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += (2 * x + 2 * y).__div__(2.0) <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_mip(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_mip_floats_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += 1.1 * x + 4.1 * y + 9.1 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 3, y: -0.5, z: 7},
                objective=64.95,
            )

        def test_initial_value(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            if self.solver.name in [
                "GUROBI",
                "GUROBI_CMD",
                "CPLEX_CMD",
                "CPLEX_PY",
                "COPT",
                "HiGHS_CMD",
            ]:
                self.solver.optionsDict["warmStart"] = True
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_fixed_value(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], solution)

        def test_relaxed_mip(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            self.solver.mip = 0
            if self.solver.__class__ in [
                GUROBI_CMD,
                CHOCO_CMD,
                MIPCL_CMD,
                SCIP_CMD,
                FSCIP_CMD,
                SCIP_PY,
            ]:
                # these solvers do not let the problem be relaxed
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 3.0, y: -0.5, z: 7}
                )
            else:
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 3.5, y: -1, z: 6.5}
                )

        def test_feasibility_only(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, None, const.LpInteger)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0, 10)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 17.5, "c3"
            if self.solver.__class__ is GLPK_CMD:
                # GLPK_CMD return codes are not informative enough
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.__class__ in [GUROBI_CMD, FSCIP_CMD]:
                # GUROBI_CMD Does not solve the problem
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_integer_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4, const.LpInteger)
            y = LpVariable("y", -1, 1, const.LpInteger)
            z = LpVariable("z", 0, 10, const.LpInteger)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 7.4, "c3"
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
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ in [GUROBI_CMD, FSCIP_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_integer_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)

            dummy = LpVariable("dummy")
            c1 = LpVariable("c1", 0, 1, const.LpBinary)
            c2 = LpVariable("c2", 0, 1, const.LpBinary)

            prob += dummy
            prob += c1 + c2 == 2
            prob += c1 <= 0
            if self.solver.__class__ in [GUROBI_CMD, SCIP_CMD, FSCIP_CMD, SCIP_PY]:
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

        def test_column_based(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6}
            )

        def test_colum_based_empty_constraints(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            if self.solver.__class__ in [CPLEX_CMD, COINMP_DLL, YAPOSIB, PYGLPK]:
                pulpTestCheck(
                    prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6}
                )

        def test_dual_variables_reduced_costs(self):
            """
            Test the reporting of dual variables slacks and reduced costs
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    sol={x: 4, y: -1, z: 6},
                    reducedcosts={x: 0, y: 12, z: 0},
                    duals={"c1": 0, "c2": 1, "c3": 8},
                    slacks={"c1": 2, "c2": 0, "c3": 0},
                )

        def test_column_based_modelling_resolve(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
                prob.resolve()
                # difficult to check this is doing what we want as the resolve is
                # overridden if it is not implemented
                # test_pulp_Check(prob, self.solver, [const.LpStatusOptimal], {x:4, y:-1, z:6})

        def test_sequential_solve(self):
            """
            Test the ability to sequentially solve a problem
            """
            # set up a cubic feasible region
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 1)
            y = LpVariable("y", 0, 1)
            z = LpVariable("z", 0, 1)

            obj1 = x + 0 * y + 0 * z
            obj2 = 0 * x - 1 * y + 0 * z
            prob += x <= 1, "c1"

            if self.solver.__class__ in [COINMP_DLL, GUROBI]:
                status = prob.sequentialSolve([obj1, obj2], solver=self.solver)
                pulpTestCheck(
                    prob,
                    self.solver,
                    [[const.LpStatusOptimal, const.LpStatusOptimal]],
                    sol={x: 0, y: 1},
                    status=status,
                )

        def test_fractional_constraints(self):
            """
            Test the ability to use fractional constraints
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 10 / 3.0, y: -1 / 3.0, z: 20 / 3.0, w: 0},
            )

        def test_elastic_constraints(self):
            """
            Test the ability to use Elastic constraints
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w")
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob.extend((w >= -1).makeElasticSubProblem())
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1}
            )

        def test_elastic_constraints_2(self):
            """
            Test the ability to use Elastic constraints
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w")
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob.extend((w >= -1).makeElasticSubProblem(proportionFreeBound=0.1))
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1.1}
            )

        def test_elastic_constraints_penalty_unchanged(self):
            """
            Test the ability to use Elastic constraints (penalty unchanged)
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w")
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob.extend((w >= -1).makeElasticSubProblem(penalty=1.1))
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: -1.0}
            )

        def test_elastic_constraints_penalty_unbounded(self):
            """
            Test the ability to use Elastic constraints (penalty unbounded)
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w")
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob.extend((w >= -1).makeElasticSubProblem(penalty=0.9))
            if self.solver.__class__ in [
                COINMP_DLL,
                GUROBI,
                CPLEX_CMD,
                YAPOSIB,
                MOSEK,
                COPT,
            ]:
                # COINMP_DLL Does not report unbounded problems, correctly
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUnbounded],
                )
            elif self.solver.__class__ is GLPK_CMD:
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.__class__ in [GUROBI_CMD, SCIP_CMD, FSCIP_CMD, SCIP_PY]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [CHOCO_CMD]:
                # choco bounds all variables. Would not return unbounded status
                pass
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])

        def test_msg_arg(self):
            """
            Test setting the msg arg to True does not interfere with solve
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
            pulpTestCheck(
                prob1,
                self.solveInst(msg=True),
                [const.LpStatusOptimal],
                {x: 4, y: -1, z: 6, w: 0},
            )

        def test_pulpTestAll(self):
            """
            Test the availability of the function pulpTestAll
            """
            from pulp import pulpTestAll

        def test_export_dict_LP(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_dict_LP_no_obj(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 6, w: 0}
            )

        def test_export_json_LP(self):
            name = self._testMethodName
            prob = LpProblem(self._testMethodName, const.LpMinimize)
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
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
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
            x, y, z = (var1[name] for name in ["x", "y", "z"])
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
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
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
            if self.solver.name != "CHOCO_CMD":
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_assignInvalidStatus(self):
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
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )
                if not os.path.exists(logFilename):
                    raise PulpError(f"Test failed for solver: {self.solver}")
                if not os.path.getsize(logFilename):
                    raise PulpError(f"Test failed for solver: {self.solver}")

        def test_makeDict_behavior(self):
            """
            Test if makeDict is returning the expected value.
            """
            headers = [["A", "B"], ["C", "D"]]
            values = [[1, 2], [3, 4]]
            target = {"A": {"C": 1, "D": 2}, "B": {"C": 3, "D": 4}}
            dict_with_default = makeDict(headers, values, default=0)
            dict_without_default = makeDict(headers, values)
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
            self.assertDictEqual(_dict1, _dict2)

        def test_importMPS_noname(self):
            name = self._testMethodName
            prob = LpProblem("", const.LpMaximize)
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
            self.assertDictEqual(_dict1, _dict2)

        def test_importMPS_RHS_fields56(self):
            """Import MPS file with RHS definitions in fields 5 & 6."""
            with tempfile.NamedTemporaryFile(delete=False) as h:
                h.write(str.encode(EXAMPLE_MPS_RHS56))
            _, problem = LpProblem.fromMPS(h.name)
            os.unlink(h.name)
            self.assertEqual(problem.constraints["LIM2"].constant, -10)

        def test_importMPS_PL_bound(self):
            """Import MPS file with PL bound type."""
            with tempfile.NamedTemporaryFile(delete=False) as h:
                h.write(str.encode(EXAMPLE_MPS_PL_BOUNDS))
            _, problem = LpProblem.fromMPS(h.name)
            os.unlink(h.name)
            self.assertIsInstance(problem, LpProblem)

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
            if self.solver.name in ["GUROBI_CMD", "FSCIP_CMD"]:
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

        @gurobi_test
        def test_measuring_solving_time(self):

            time_limit = 10
            solver_settings = dict(
                PULP_CBC_CMD=30,
                COIN_CMD=30,
                SCIP_CMD=30,
                GUROBI_CMD=50,
                CPLEX_CMD=50,
                GUROBI=50,
                HiGHS=50,
                HiGHS_CMD=50,
            )
            bins = solver_settings.get(self.solver.name)
            if bins is None:
                # not all solvers have timeLimit support
                return
            prob = create_bin_packing_problem(bins=bins, seed=99)
            self.solver.timeLimit = time_limit
            status = prob.solve(self.solver)

            delta = 20
            reported_time = prob.solutionTime
            if self.solver.name in ["PULP_CBC_CMD", "COIN_CMD"]:
                reported_time = prob.solutionCpuTime

            self.assertAlmostEqual(
                reported_time,
                time_limit,
                delta=delta,
                msg=f"optimization time for solver {self.solver.name}",
            )
            self.assertTrue(prob.objective.value() is not None)
            self.assertEqual(status, const.LpStatusOptimal)
            for v in prob.variables():
                self.assertTrue(v.varValue is not None)

        @gurobi_test
        def test_time_limit_no_solution(self):

            time_limit = 1
            solver_settings = dict(HiGHS_CMD=60, HiGHS=60, PULP_CBC_CMD=60, COIN_CMD=60)
            bins = solver_settings.get(self.solver.name)
            if bins is None:
                # not all solvers have timeLimit support
                return
            prob = create_bin_packing_problem(bins=bins, seed=99)
            self.solver.timeLimit = time_limit
            status = prob.solve(self.solver)
            self.assertEqual(prob.status, const.LpStatusNotSolved)
            self.assertEqual(status, const.LpStatusNotSolved)
            self.assertEqual(prob.sol_status, const.LpSolutionNoSolutionFound)

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
            if self.solver.name not in [
                "GUROBI_CMD",  # end is a key-word for LP files
            ]:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_LpVariable_indexs_param(self):
            """
            Test that 'indexs' param continues to work
            """
            customers = [1, 2, 3]
            agents = ["A", "B", "C"]

            # explicit param creates a dict of type LpVariable
            assign_vars = LpVariable.dicts(name="test", indices=(customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # param by position creates a dict of type LpVariable
            assign_vars = LpVariable.dicts("test", (customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # explicit param creates list of LpVariable
            assign_vars_matrix = LpVariable.matrix(
                name="test", indices=(customers, agents)
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

            # explicit param creates a dict of type LpVariable
            assign_vars = LpVariable.dicts(name="test", indices=(customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # explicit param creates list of list of LpVariable
            assign_vars_matrix = LpVariable.matrix(
                name="test", indices=(customers, agents)
            )
            for a in assign_vars_matrix:
                for b in a:
                    self.assertIsInstance(b, LpVariable)

        def test_parse_cplex_mipopt_solution(self):
            """
            Ensures `readsol` can parse CPLEX mipopt solutions (see issue #508).
            """
            from io import StringIO

            # Example solution generated by CPLEX mipopt solver
            file_content = """<?xml version = "1.0" encoding="UTF-8" standalone="yes"?>
                <CPLEXSolution version="1.2">
                <header
                    problemName="mipopt_solution_example.lp"
                    solutionName="incumbent"
                    solutionIndex="-1"
                    objectiveValue="442"
                    solutionTypeValue="3"
                    solutionTypeString="primal"
                    solutionStatusValue="101"
                    solutionStatusString="integer optimal solution"
                    solutionMethodString="mip"
                    primalFeasible="1"
                    dualFeasible="1"
                    MIPNodes="25471"
                    MIPIterations="282516"
                    writeLevel="1"/>
                <quality
                    epInt="1.0000000000000001e-05"
                    epRHS="9.9999999999999995e-07"
                    maxIntInfeas="8.8817841970012523e-16"
                    maxPrimalInfeas="0"
                    maxX="48"
                maxSlack="141"/>
                <linearConstraints>
                    <constraint name="C1" index="0" slack="0"/>
                    <constraint name="C2" index="1" slack="0"/>
                </linearConstraints>
                <variables>
                    <variable name="x" index="0" value="42"/>
                    <variable name="y" index="1" value="0"/>
                </variables>
                <objectiveValues>
                    <objective index="0" name="x" value="42"/>
                </objectiveValues>
                </CPLEXSolution>
            """
            solution_file = StringIO(file_content)

            # This call to `readsol` would crash for this solution format #508
            _, _, reducedCosts, shadowPrices, _, _ = CPLEX_CMD().readsol(solution_file)

            # Because mipopt solutions have no `reducedCost` fields
            # it should be all None
            self.assertTrue(all(c is None for c in reducedCosts.values()))

            # Because mipopt solutions have no `shadowPrices` fields
            # it should be all None
            self.assertTrue(all(c is None for c in shadowPrices.values()))

        def test_options_parsing_SCIP_HIGHS(self):
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
            # CHOCO has issues when given a time limit
            if self.solver.__class__ in [SCIP_CMD, FSCIP_CMD]:
                self.solver.options = ["limits/time", 20]
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )
            elif self.solver.__class__ in [HiGHS_CMD]:
                self.solver.options = ["time_limit", 20]
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_sum_nan_values(self):
            import math

            a = math.nan
            x = LpVariable("x")
            self.assertRaises(PulpError, lambda: x + a)

        def test_multiply_nan_values(self):
            import math

            a = math.nan
            x = LpVariable("x")
            self.assertRaises(PulpError, lambda: x * a)


class PULP_CBC_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = PULP_CBC_CMD


class CPLEX_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = CPLEX_CMD


class CPLEX_PYTest(BaseSolverTest.PuLPTest):
    solveInst = CPLEX_CMD


class XPRESS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = XPRESS_CMD


class XPRESS_PyTest(BaseSolverTest.PuLPTest):
    solveInst = XPRESS_PY


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


class FSCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = FSCIP_CMD


class SCIP_PYTest(BaseSolverTest.PuLPTest):
    solveInst = SCIP_PY


class HiGHS_PYTest(BaseSolverTest.PuLPTest):
    solveInst = HiGHS


class HiGHS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = HiGHS_CMD


class COPTTest(BaseSolverTest.PuLPTest):
    solveInst = COPT


def pulpTestCheck(
    prob,
    solver,
    okstatus,
    sol=None,
    reducedcosts=None,
    duals=None,
    slacks=None,
    eps=10**-3,
    status=None,
    objective=None,
    **kwargs,
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
                f"Tests failed for solver {solver}:\nobjective {z} != {objective}"
            )


def getSortedDict(prob, keyCons="name", keyVars="name"):
    _dict = prob.toDict()
    _dict["constraints"].sort(key=lambda v: v[keyCons])
    _dict["variables"].sort(key=lambda v: v[keyVars])
    return _dict


if __name__ == "__main__":
    unittest.main()
