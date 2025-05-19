"""
Tests for pulp
"""

import functools
import os
import re
import tempfile
import unittest
from decimal import Decimal

from pulp import (
    LpAffineExpression,
    LpConstraint,
    LpConstraintVar,
    LpFractionConstraint,
    LpProblem,
    LpVariable,
    FixedElasticSubProblem,
)
from pulp import constants as const
from pulp import lpSum
from pulp.apis import *
from pulp.constants import PulpError
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.utilities import makeDict

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

EXAMPLE_MPS_MI_BOUNDS = EXAMPLE_MPS_RHS56.replace(
    "LO BND1      YTWO                -1", "MI BND1      YTWO                  "
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
            self.solver = self.solveInst(msg=False, timeLimit=120)
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
            # for v in [x, y, z]:
            #    v.setInitialValue(solution[v])
            #    v.fixValue()
            # self.solver.optionsDict["warmStart"] = True
            prob.writeMPS("test.mps")
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], solution)


"""        def test_integer_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4, const.LpInteger)
            y = LpVariable("y", -1, 1, const.LpInteger)
            z = LpVariable("z", 0, 10, const.LpInteger)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 7.4, "c3"
            prob.writeMPS("test.mps")
            if self.solver.__class__ in [GLPK_CMD, COIN_CMD, PULP_CBC_CMD, MOSEK]:
                # GLPK_CMD returns InfeasibleOrUnbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            elif self.solver.__class__ in [COINMP_DLL, CYLP]:
                # Currently there is an error in COINMP for problems where
                # presolve eliminates too many variables
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ in [GUROBI_CMD, FSCIP_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_elastic_constraints_penalty_unbounded(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4)
            y = LpVariable("y", -1, 1)
            z = LpVariable("z", 0)
            w = LpVariable("w")
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"

            sub_prob: FixedElasticSubProblem = (w >= -1).makeElasticSubProblem(
                penalty=0.9
            )
            self.assertEqual(sub_prob.RHS, -1)
            self.assertEqual(
                str(sub_prob.objective), "-0.9*_neg_penalty_var + 0.9*_pos_penalty_var"
            )

            prob.extend(sub_prob)

            elastic_constraint1 = sub_prob.constraints["_Constraint"]
            elastic_constraint2 = prob.constraints["None_elastic_SubProblem_Constraint"]
            self.assertEqual(str(elastic_constraint1), str(elastic_constraint2))

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
            elif self.solver.__class__ in [GUROBI_CMD, SCIP_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            elif self.solver.__class__ in [CHOCO_CMD, FSCIP_CMD]:
                # choco bounds all variables. Would not return unbounded status
                # FSCIP_CMD returns optimal
                pass
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusUnbounded])


        def test_integer_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = LpVariable("x", 0, 4, const.LpInteger)
            y = LpVariable("y", -1, 1, const.LpInteger)
            z = LpVariable("z", 0, 10, const.LpInteger)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 7.4, "c3"
            prob.writeMPS("test.mps")
            if self.solver.__class__ in [GLPK_CMD, COIN_CMD, PULP_CBC_CMD, MOSEK]:
                # GLPK_CMD returns InfeasibleOrUnbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            elif self.solver.__class__ in [COINMP_DLL, CYLP]:
                # Currently there is an error in COINMP for problems where
                # presolve eliminates too many variables
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.__class__ in [GUROBI_CMD, FSCIP_CMD]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])
"""


class CUOPTTest(BaseSolverTest.PuLPTest):
    solveInst = CUOPT


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
