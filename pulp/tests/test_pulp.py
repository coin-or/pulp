"""
Tests for pulp
"""

import array
import functools
import os
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from typing import Optional, Type, Union

import pulp.apis as solvers
import pulp.mps_lp as mps_lp
from pulp import (
    LpAffineExpression,
    LpConstraint,
    LpProblem,
    LpVariable,
    PulpSolverError,
    lpSum,
    lpSum_vars,
    lpSum_vars_coefs,
)
from pulp import constants as const
from pulp.constants import PulpError
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.utilities import makeDict

try:
    import gurobipy as gp  # type: ignore[import-not-found, import-untyped]
except ImportError:
    gp = None  # type: ignore[assignment]

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
        if test_obj.solver.name not in ["GUROBI", "GUROBI_CMD"]:
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
    except Exception:
        pass


def _constraint_named(prob: LpProblem, name: str) -> LpConstraint:
    """Return the constraint with the given name (first match)."""
    for c in prob.constraints():
        if c.name == name:
            return c
    raise KeyError(name)


class ModelUnitTest(unittest.TestCase):
    """Solver-independent tests for the thin-wrapper architecture."""

    def _make_prob(self, name=None):
        return LpProblem(name or self._testMethodName, const.LpMinimize)

    # -- 1. Variable bounds: inf/None conversion --

    def test_variable_bounds_inf_conversion(self):
        prob = self._make_prob()
        x = prob.add_variable("x", lowBound=None, upBound=None)
        self.assertEqual(x.lowBound, float("-inf"))
        self.assertEqual(x.upBound, float("inf"))
        x.lowBound = None
        x.upBound = None
        self.assertEqual(x.lowBound, float("-inf"))
        self.assertEqual(x.upBound, float("inf"))

    def test_variable_bounds_set_finite(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 100)
        x.lowBound = 5.0
        x.upBound = 10.0
        self.assertEqual(x.lowBound, 5.0)
        self.assertEqual(x.upBound, 10.0)

    # -- 2. Variable dj property --

    def test_variable_dj_default_none(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        self.assertIsNone(x.dj)

    def test_variable_dj_set_and_get(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        x.dj = 3.5
        self.assertEqual(x.dj, 3.5)

    # -- 3. Constraint pi and slack --

    def test_constraint_pi_default_none(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        c = _constraint_named(prob, "c1")
        self.assertIsNone(c.pi)

    def test_constraint_pi_set_and_get(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        c = _constraint_named(prob, "c1")
        c.pi = 1.5
        c2 = _constraint_named(prob, "c1")
        self.assertEqual(c2.pi, 1.5)

    def test_constraint_slack_default_none(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        c = _constraint_named(prob, "c1")
        self.assertIsNone(c.slack)

    def test_constraint_slack_set_and_get(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        c = _constraint_named(prob, "c1")
        c.slack = 2.0
        c2 = _constraint_named(prob, "c1")
        self.assertEqual(c2.slack, 2.0)

    # -- 4. Constraint properties delegate to Rust --

    def test_constraint_sense_property(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "le"
        prob += x >= 1, "ge"
        prob += x == 3, "eq"
        self.assertEqual(_constraint_named(prob, "le").sense, const.LpConstraintLE)
        self.assertEqual(_constraint_named(prob, "ge").sense, const.LpConstraintGE)
        self.assertEqual(_constraint_named(prob, "eq").sense, const.LpConstraintEQ)

    def test_constraint_rhs_via_constant(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 10)
        prob += x + y <= 5, "c1"
        c = _constraint_named(prob, "c1")
        self.assertEqual(c.constant, -5)

    def test_constraint_items_keys_values(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 10)
        prob += 2 * x + 3 * y <= 10, "c1"
        c = _constraint_named(prob, "c1")
        items = c.items()
        coeffs_by_name = {v.name: coeff for v, coeff in items}
        self.assertAlmostEqual(coeffs_by_name["x"], 2.0)
        self.assertAlmostEqual(coeffs_by_name["y"], 3.0)
        key_names = sorted(v.name for v in c.keys())
        self.assertEqual(key_names, ["x", "y"])
        self.assertEqual(sorted(c.values()), [2.0, 3.0])

    # -- 5. Auto-naming constraints --

    def test_auto_named_constraint(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5
        cons = prob.constraints()
        self.assertEqual(len(cons), 1)
        name = cons[0].name
        self.assertIsNotNone(name)
        self.assertTrue(len(name) > 0, "Auto-generated name should be non-empty")

    def test_multiple_auto_named_constraints(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5
        prob += x >= 1
        prob += x <= 8
        cons = prob.constraints()
        self.assertEqual(len(cons), 3)
        names = [c.name for c in cons]
        self.assertEqual(
            len(set(names)), 3, "All auto-generated names should be distinct"
        )
        self.assertEqual(sorted(names), ["_C1", "_C2", "_C3"])

    def test_constraint_name_leading_underscore_raises(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        with self.assertRaises(ValueError):
            prob += x <= 5, "_bad"

    def test_from_dataclass_sanitizes_leading_underscore_constraint_name(self):
        mps = mps_lp.MPS(
            parameters=mps_lp.MPSParameters(
                name="p", sense=const.LpMinimize, status=0, sol_status=0
            ),
            objective=mps_lp.MPSObjective(
                name="OBJ",
                coefficients=[mps_lp.MPSCoefficient("x", 1.0)],
            ),
            variables=[
                mps_lp.MPSVariable("x", const.LpContinuous, 0, None),
            ],
            constraints=[
                mps_lp.MPSConstraint(
                    name="_row1",
                    sense=const.LpConstraintLE,
                    coefficients=[mps_lp.MPSCoefficient("x", 1.0)],
                    constant=0.0,
                )
            ],
            sos1=[],
            sos2=[],
        )
        _var, pb = LpProblem.fromDataclass(mps, objective_negate_for_max=False)
        self.assertTrue(any(c.name == "imp__row1" for c in pb.constraints()))

    # -- 6. Duplicate constraint name --

    def test_duplicate_constraint_name_raises(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        prob += x >= 1, "c1"
        with self.assertRaises(PulpError):
            prob.checkDuplicateConstraints()

    # -- 7. constraints property (fresh from Rust) --

    def test_constraints_property_returns_list(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        prob += x >= 1, "c2"
        cons = prob.constraints()
        self.assertIsInstance(cons, list)
        self.assertEqual({c.name for c in cons}, {"c1", "c2"})
        self.assertIsInstance(_constraint_named(prob, "c1"), LpConstraint)
        self.assertIsInstance(_constraint_named(prob, "c2"), LpConstraint)

    def test_constraints_property_fresh_wrappers(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        a = _constraint_named(prob, "c1")
        b = _constraint_named(prob, "c1")
        self.assertIsNot(a, b, "Each call should produce a fresh wrapper")
        self.assertEqual(a.name, b.name)

    # -- 8. variables() (fresh from Rust) --

    def test_variables_returns_list(self):
        prob = self._make_prob()
        prob.add_variable("x", 0, 10)
        prob.add_variable("y", 0, 10)
        prob.add_variable("z", 0, 10)
        vs = prob.variables()
        self.assertEqual(len(vs), 3)
        names = sorted(v.name for v in vs)
        self.assertEqual(names, ["x", "y", "z"])

    def test_variables_fresh_wrappers(self):
        prob = self._make_prob()
        prob.add_variable("x", 0, 10)
        v1 = prob.variables()[0]
        v2 = prob.variables()[0]
        self.assertIsNot(v1, v2, "Each call should produce a fresh wrapper")
        self.assertEqual(v1.name, v2.name)

    def test_lp_problem_copy_rust_model(self) -> None:
        """copy() deep-copies the Rust model; variables are independent but data matches."""
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 10)
        prob.objective = x + 2 * y
        prob.addConstraint(x + y <= 5, name="c1")
        x.setInitialValue(3.0)
        y.setInitialValue(1.0)

        prob2 = prob.copy()
        self.assertIsNot(prob, prob2)
        self.assertNotEqual(
            x._var.model_identity(), prob2.variables()[0]._var.model_identity()
        )

        vx0, vy0 = prob.variables()
        vx1, vy1 = prob2.variables()
        self.assertEqual(vx0.name, vx1.name)
        self.assertEqual(vy0.name, vy1.name)
        self.assertEqual(vx1.value(), 3.0)
        self.assertEqual(vy1.value(), 1.0)

        self.assertEqual(prob2._model.num_variables, prob._model.num_variables)
        self.assertEqual(prob2._model.num_constraints, prob._model.num_constraints)
        self.assertIsNotNone(prob2.objective)
        self.assertEqual(str(prob.objective), str(prob2.objective))
        self.assertEqual({c.name for c in prob2.constraints()}, {"c1"})

        vx1.setInitialValue(7.0)
        self.assertEqual(x.value(), 3.0)
        self.assertEqual(vx1.value(), 7.0)

        prob3 = prob.deepcopy()
        self.assertEqual(prob3.variables()[0].value(), 3.0)

    # -- 9. Batch setters --

    def test_assign_vars_vals(self):
        prob = self._make_prob()
        prob.add_variable("x", 0, 10)
        prob.add_variable("y", 0, 10)
        prob.assignVarsVals({"x": 1.0, "y": 2.0})
        vd = prob.variablesDict()
        self.assertEqual(vd["x"].varValue, 1.0)
        self.assertEqual(vd["y"].varValue, 2.0)

    def test_assign_vars_dj(self):
        prob = self._make_prob()
        prob.add_variable("x", 0, 10)
        prob.assignVarsDj({"x": 0.5})
        vd = prob.variablesDict()
        self.assertEqual(vd["x"].dj, 0.5)

    def test_assign_cons_pi(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        prob.assignConsPi({"c1": 1.5})
        self.assertEqual(_constraint_named(prob, "c1").pi, 1.5)

    def test_assign_cons_slack(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        prob += x <= 5, "c1"
        prob.assignConsSlack({"c1": 2.0})
        self.assertEqual(_constraint_named(prob, "c1").slack, 2.0)

    # -- 11. LpVariable arithmetic operators --

    def test_variable_arithmetic_operators(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 10)
        self.assertIsInstance(x + y, LpAffineExpression)
        self.assertIsInstance(x - y, LpAffineExpression)
        self.assertIsInstance(2 * x, LpAffineExpression)
        self.assertIsInstance(x * 3, LpAffineExpression)
        self.assertIsInstance(x / 2, LpAffineExpression)
        self.assertIsInstance(-x, LpAffineExpression)
        self.assertIs(+x, x)

    def test_variable_comparison_operators(self):
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 10)
        le = x <= 5
        ge = x >= 3
        eq = x == 4
        self.assertIsInstance(le, LpAffineExpression)
        self.assertIsInstance(ge, LpAffineExpression)
        self.assertIsInstance(eq, LpAffineExpression)
        self.assertEqual(le.sense, const.LpConstraintLE)
        self.assertEqual(ge.sense, const.LpConstraintGE)
        self.assertEqual(eq.sense, const.LpConstraintEQ)

    # -- 7. Dropped model: friendly ValueError --

    def test_dropped_model_raises_value_error(self):
        """Using a variable after its LpProblem was dropped raises ValueError."""
        prob = self._make_prob()
        x = prob.add_variable("x", 0, 1)
        # Reassign so the first model is dropped; x still refers to it.
        prob = LpProblem("other", const.LpMinimize)
        expr = x * 2 + 1
        with self.assertRaises(ValueError) as ctx:
            expr.items()
        self.assertIn("no longer exists", str(ctx.exception))
        self.assertIn("LpProblem", str(ctx.exception))

    def test_dropped_model_add_expr_raises_value_error(self):
        """Adding expressions from different/dropped models raises ValueError."""
        prob1 = self._make_prob()
        x = prob1.add_variable("x", 0, 1)
        prob1 = LpProblem("other", const.LpMinimize)
        y = prob1.add_variable("y", 0, 1)
        # x belongs to dropped model, y to current; adding them should fail.
        with self.assertRaises(ValueError) as ctx:
            _ = (x + y).items()
        self.assertIn("no longer exists", str(ctx.exception))

    # -- 8. Numpy scalars in constraints (constant on left) --

    def test_constraint_numpy_scalar_constant_on_left(self):
        """model += np.float64(34.5) >= var adds constraint var <= 34.5."""
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")

        model = LpProblem("numpy_const", const.LpMinimize)
        var = model.add_variable("var", 0, None, cat=const.LpContinuous)
        model += np.float64(34.5) >= var
        model += var >= np.float64(0)

        self.assertEqual(len(model.constraints()), 2)
        senses = {c.sense for c in model.constraints()}
        self.assertEqual(senses, {const.LpConstraintLE, const.LpConstraintGE})
        for c in model.constraints():
            if c.sense == const.LpConstraintLE:
                self.assertAlmostEqual(c.constant, -34.5)
                break
        else:
            self.fail("Expected one LE constraint with constant -34.5")


class VariableIndirectionTest(unittest.TestCase):
    """
    Regression-style tests for LpVariable handles that cross Python call boundaries.

    Patterns such as "create in one helper, return to caller, then pass to another
    helper" are easy to get wrong with native-backed wrappers; these tests pin
    expected behavior.
    """

    def _make_prob(self, name: Optional[str] = None) -> LpProblem:
        return LpProblem(name or self._testMethodName, const.LpMinimize)

    @staticmethod
    def _add_named_variable(prob: LpProblem, name: str) -> LpVariable:
        return prob.add_variable(name, 0, 10)

    def test_variable_from_helper_factory_uses_same_model(self) -> None:
        prob = self._make_prob()
        x = self._add_named_variable(prob, "x")
        m_from_var = x._var.containing_model()
        m_from_prob = prob.toRustModel()
        self.assertEqual(m_from_var.num_variables, m_from_prob.num_variables)
        self.assertEqual(m_from_var.num_variables, 1)
        self.assertEqual(
            x._var.model_identity(), prob.variables()[0]._var.model_identity()
        )
        prob += x, "obj"
        m_after = x._var.containing_model()
        self.assertEqual(m_after.num_variables, 1)
        self.assertEqual(m_after.num_constraints, 0)
        self.assertIn("objective=set", m_after.summary())

    def test_variable_passed_to_second_helper_for_objective_and_constraint(
        self,
    ) -> None:
        def build_objective(v1: LpVariable, v2: LpVariable) -> LpAffineExpression:
            return 2 * v1 + 3 * v2

        def add_leq(prob: LpProblem, v: LpVariable, name: str) -> None:
            prob += v <= 6, name

        prob = self._make_prob()
        x = self._add_named_variable(prob, "x")
        y = self._add_named_variable(prob, "y")
        prob += build_objective(x, y), "obj"
        add_leq(prob, y, "cy")
        names = {c.name for c in prob.constraints()}
        self.assertEqual(names, {"cy"})
        rust = prob.toRustModel()
        self.assertEqual(rust.num_variables, 2)
        self.assertEqual(rust.num_constraints, 1)

    def test_variable_in_nested_def_closure(self) -> None:
        def build() -> tuple[LpProblem, LpVariable]:
            p = LpProblem("closure_case", const.LpMinimize)

            def add_x() -> LpVariable:
                return p.add_variable("x", 0, 5)

            v = add_x()
            p += 4 * v, "obj"
            p += v >= 1, "lo"
            return p, v

        prob, x = build()
        self.assertIsInstance(x, LpVariable)
        self.assertEqual(x.name, "x")
        m = x._var.containing_model()
        self.assertEqual(m.num_variables, 1)
        self.assertEqual(m.num_constraints, 1)
        for c in prob.constraints():
            _ = c.items()
        self.assertIn("x", [v.name for v in prob.variables()])

    def test_higher_order_identity_passthrough(self) -> None:
        def ident(u: LpVariable) -> LpVariable:
            return u

        def double_pipe(u: LpVariable) -> LpVariable:
            return ident(ident(u))

        prob = self._make_prob()
        x = prob.add_variable("x", 0, 2)
        y = double_pipe(x)
        prob += y, "z"
        self.assertIs(y, x)
        e = y * 2 + 1
        d = e.items()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0][0].name, "x")

    def test_variable_forwarded_in_kwargs(self) -> None:
        def accept(prob: LpProblem, *, a: LpVariable, b: LpVariable) -> None:
            prob += a + 2 * b, "o"
            prob += a - b <= 1, "c1"

        prob = self._make_prob()
        va = prob.add_variable("a", 0, 1)
        vb = prob.add_variable("b", 0, 1)
        accept(prob, a=va, b=vb)
        self.assertEqual(prob.toRustModel().num_constraints, 1)

    def test_tuple_unpack_from_helper_then_constraint(self) -> None:
        def make_pair(p: LpProblem) -> tuple[LpVariable, LpVariable]:
            return p.add_variable("p0", 0, 1), p.add_variable("p1", 0, 1)

        def use_them(p: LpProblem, a: LpVariable, b: LpVariable) -> None:
            p += a + 3 * b, "tobj"
            p += a + b <= 1, "cxy"

        prob = self._make_prob()
        u, w = make_pair(prob)
        use_them(prob, u, w)
        self.assertEqual({v.name for v in prob.variables()}, {"p0", "p1"})

    def test_list_of_variables_built_in_helper_then_lpSum(self) -> None:
        def collect_vars(p: LpProblem, n: int) -> list[LpVariable]:
            return [p.add_variable(f"v{i}", 0, 1) for i in range(n)]

        prob = self._make_prob()
        vs = collect_vars(prob, 3)
        prob += lpSum(vs), "sumobj"
        self.assertEqual(prob.toRustModel().num_variables, 3)
        s = str(sum(vs, start=0 * vs[0]))
        self.assertIn("v0", s)
        self.assertIn("v2", s)


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
                except Exception:
                    pass
            pass

        def test_variable_0_is_deleted(self):
            """
            Test that a variable is deleted when it is subtracted to 0
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            c1 = x + y <= 5
            c2 = c1 + z - z
            assert str(c2)
            assert c2[z] == 0

        def test_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += (
                lpSum([v for v in [x] if False]) >= 5,
                "c1",
            )  # this is a 0 >=5 constraint
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            # this was a problem with use_mps=false
            if self.solver.name == "COIN_CMD":
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible],
                    {x: 4, y: -1, z: 6, w: 0},
                    use_mps=False,
                )
            elif self.solver.name in ["CHOCO_CMD", "MIPCL_CMD"]:
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

        def test_empty(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal, const.LpStatusNotSolved], {}
            )

        def test_continuous(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_NAN_const(self):
            prob = LpProblem("test", const.LpMinimize)
            my_var = prob.add_variable(
                "my_var", lowBound=None, upBound=None, cat=const.LpContinuous
            )

            def gives_error():
                prob = LpProblem("myProblem", const.LpMinimize)
                prob += my_var == float("nan")
                return prob

            self.assertRaises(const.PulpError, gives_error)

        def test_NAN_bound(self):
            prob = LpProblem("test", const.LpMinimize)

            def gives_error():
                return prob.add_variable(
                    "my_var",
                    lowBound=float("nan"),
                    upBound=None,
                    cat=const.LpContinuous,
                )

            self.assertRaises(const.PulpError, gives_error)

        def test_non_intermediate_var(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x_vars = {
                i: prob.add_variable(f"x{i}", lowBound=0, cat=const.LpContinuous)
                for i in range(3)
            }
            prob += lpSum(x_vars[i] for i in range(3)) >= 2
            prob += lpSum(x_vars[i] for i in range(3)) <= 5
            for elem in prob.constraints():
                self.assertIn(elem.constant, [-2, -5])

        def test_intermediate_var(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x_vars = {
                i: prob.add_variable(f"x{i}", lowBound=0, cat=const.LpContinuous)
                for i in range(3)
            }
            x = lpSum(x_vars[i] for i in range(3))
            prob += x >= 2
            prob += x <= 5
            for elem in prob.constraints():
                self.assertIn(elem.constant, [-2, -5])

        def test_comparison(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x_vars = {
                i: prob.add_variable(f"x{i}", lowBound=0, cat=const.LpContinuous)
                for i in range(3)
            }
            x = lpSum(x_vars[i] for i in range(3))

            with self.assertRaises(TypeError):
                prob += x > 2
            with self.assertRaises(TypeError):
                prob += x < 5

        def test_continuous_max(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.name in ["GUROBI", "CPLEX_CMD", "YAPOSIB", "MOSEK", "COPT"]:
                # These solvers report infeasible or unbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [
                        const.LpStatusInfeasible,
                        const.LpStatusUnbounded,
                        const.LpStatusUndefined,
                    ],
                )
            elif self.solver.name == "CUOPT":
                # cuOpt reports UnboundedOrInfeasible (mapped to Undefined)
                # for problems where its presolver cannot disambiguate.
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusUnbounded, const.LpStatusUndefined],
                )
            elif self.solver.name in ["COINMP_DLL", "MIPCL_CMD"]:
                # COINMP_DLL is just plain wrong
                # also MIPCL_CMD
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.name == "GLPK_CMD":
                # GLPK_CMD Does not report unbounded problems, correctly
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.name in ["GUROBI_CMD", "SCIP_CMD", "SCIP_PY"]:
                # GUROBI_CMD has a very simple interface
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusNotSolved, const.LpStatusUndefined],
                )
            elif self.solver.name in ["CHOCO_CMD", "HiGHS_CMD", "FSCIP_CMD"]:
                # choco bounds all variables. Would not return unbounded status
                # highs_cmd is inconsistent
                # FSCIP_CMD is inconsistent
                pass
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusUnbounded, const.LpStatusUndefined],
                )

        def test_long_var_name(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x" * 120, 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.name in [
                "CPLEX_CMD",
                "GLPK_CMD",
                "GUROBI_CMD",
                "MIPCL_CMD",
                "SCIP_CMD",
                "FSCIP_CMD",
                "SCIP_PY",
                "HiGHS",
                "HiGHS_CMD",
                "XPRESS",
                "XPRESS_CMD",
                "SAS94",
                "SASCAS",
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("x", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.name in [
                "COIN_CMD",
                "COINMP_DLL",
                "CPLEX_CMD",
                "CPLEX_PY",
                "GLPK_CMD",
                "GUROBI_CMD",
                "CHOCO_CMD",
                "MIPCL_CMD",
                "MOSEK",
                "SCIP_CMD",
                "FSCIP_CMD",
                "HiGHS_CMD",
                "XPRESS",
                "XPRESS_CMD",
                "XPRESS_PY",
                "SAS94",
                "SASCAS",
                "CYLP",
            ]:

                def my_func():
                    return pulpTestCheck(
                        prob,
                        self.solver,
                        [const.LpStatusOptimal],
                        {x: 4, y: -1, z: 6, w: 0},
                    )

                self.assertRaises(PulpError, my_func)
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_zero_constraint(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_variable_as_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob.setObjective(x)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_longname_lp(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x" * 90, 0, 4)
            y = prob.add_variable("y" * 90, -1, 1)
            z = prob.add_variable("z" * 90, 0)
            w = prob.add_variable("w" * 90, 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.name == "COIN_CMD":
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                    use_mps=False,
                )

        def test_divide(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += ((2 * x + 2 * y) / 2.0) <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_mip(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_mip_floats_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
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
                "SAS94",
                "SASCAS",
                "COIN_CMD",
            ]:
                self.solver.optionsDict["warmStart"] = True
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_fixed_value(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            self.solver.mip = 0
            if self.solver.name in [
                "GUROBI_CMD",
                "CHOCO_CMD",
                "MIPCL_CMD",
                "SCIP_CMD",
                "FSCIP_CMD",
                "SCIP_PY",
                "CYLP",
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, 10)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 17.5, "c3"
            if self.solver.name == "GLPK_CMD":
                # GLPK_CMD return codes are not informative enough
                pulpTestCheck(prob, self.solver, [const.LpStatusUndefined])
            elif self.solver.name in ["GUROBI_CMD", "FSCIP_CMD"]:
                # GUROBI_CMD Does not solve the problem
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_integer_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4, const.LpInteger)
            y = prob.add_variable("y", -1, 1, const.LpInteger)
            z = prob.add_variable("z", 0, 10, const.LpInteger)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 7.4, "c3"
            if self.solver.name in ["GLPK_CMD", "COIN_CMD", "MOSEK"]:
                # GLPK_CMD returns InfeasibleOrUnbounded
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            elif self.solver.name in ["COINMP_DLL", "CYLP"]:
                # Currently there is an error in COINMP for problems where
                # presolve eliminates too many variables
                pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            elif self.solver.name in ["GUROBI_CMD", "FSCIP_CMD"]:
                pulpTestCheck(prob, self.solver, [const.LpStatusNotSolved])
            else:
                pulpTestCheck(prob, self.solver, [const.LpStatusInfeasible])

        def test_integer_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)

            dummy = prob.add_variable("dummy")
            c1 = prob.add_variable("c1", 0, 1, const.LpBinary)
            c2 = prob.add_variable("c2", 0, 1, const.LpBinary)

            prob += dummy
            prob += c1 + c2 == 2
            prob += c1 <= 0
            if self.solver.name in ["GUROBI_CMD", "SCIP_CMD", "FSCIP_CMD", "SCIP_PY"]:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusNotSolved, const.LpStatusUndefined],
                )
            elif self.solver.name in ["GLPK_CMD", "CUOPT"]:
                # These solvers may return InfeasibleOrUnbounded (reported as
                # Undefined) rather than proving infeasibility.
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )
            else:
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusInfeasible, const.LpStatusUndefined],
                )

        def test_dual_variables_reduced_costs(self):
            """
            Test the reporting of dual variables slacks and reduced costs
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 5)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            c1 = x + y <= 5
            c2 = x + z >= 10
            c3 = -y + z == 7

            prob += x + 4 * y + 9 * z, "obj"
            prob += c1, "c1"
            prob += c2, "c2"
            prob += c3, "c3"

            if self.solver.name in [
                "CPLEX_CMD",
                "COIN_CMD",
                "COINMP_DLL",
                "YAPOSIB",
                "PYGLPK",
                "HiGHS",
                "SAS94",
                "SASCAS",
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

        def test_sequential_solve(self):
            """
            Test the ability to sequentially solve a problem
            """
            # set up a cubic feasible region
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 1)
            y = prob.add_variable("y", 0, 1)
            z = prob.add_variable("z", 0, 1)

            obj1 = x + 0 * y + 0 * z
            obj2 = 0 * x - 1 * y + 0 * z
            prob += x <= 1, "c1"

            if self.solver.name in ["COINMP_DLL", "GUROBI"]:
                status = prob.sequentialSolve([obj1, obj2], solver=self.solver)
                pulpTestCheck(
                    prob,
                    self.solver,
                    [[const.LpStatusOptimal, const.LpStatusOptimal]],
                    sol={x: 0, y: 1},
                    status=status,
                )

        def test_msg_arg(self):
            """
            Test setting the msg arg to True does not interfere with solve
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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

        def test_export_dict_LP(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0, 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            except Exception:
                pass
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
            pulpTestCheck(
                prob1, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_dict_MIP(self):
            import copy

            prob = LpProblem("test_export_dict_MIP", const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            data = self.solver.toDict()
            solver1 = solvers.getSolverFromDict(data)
            pulpTestCheck(
                prob, solver1, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_export_solver_json(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            elif self.solver.name in ["GUROBI_CMD", "COIN_CMD"]:
                self.solver.optionsDict = dict(
                    gapRel=0.1, gapAbs=1, threads=1, logPath=logFilename, warmStart=True
                )
            filename = name + ".json"
            self.solver.toJson(filename, indent=4)
            solver1 = solvers.getSolverFromJson(filename)
            try:
                os.remove(filename)
            except Exception:
                pass
            pulpTestCheck(
                prob, solver1, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        # def test_timeLimit(self):
        #     name = self._testMethodName
        #     prob = LpProblem(name, const.LpMinimize)
        #     x = prob.add_variable("x", 0, 4)
        #     y = prob.add_variable("y", -1, 1)
        #     z = prob.add_variable("z", 0)
        #     w = prob.add_variable("w", 0)
        #     prob += x + 4 * y + 9 * z, "obj"
        #     prob += x + y <= 5, "c1"
        #     prob += x + z >= 10, "c2"
        #     prob += -y + z == 7, "c3"
        #     prob += w >= 0, "c4"
        #     self.solver.timeLimit = 20
        #     # CHOCO has issues when given a time limit
        #     if self.solver.name != "CHOCO_CMD":
        #         pulpTestCheck(
        #             prob,
        #             self.solver,
        #             [const.LpStatusOptimal],
        #             {x: 4, y: -1, z: 6, w: 0},
        #         )

        def test_assignInvalidStatus(self):
            t = LpProblem("test")
            Invalid = -100
            self.assertRaises(const.PulpError, lambda: t.assignStatus(Invalid))
            self.assertRaises(const.PulpError, lambda: t.assignStatus(0, Invalid))

        def test_logPath(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            with self.assertRaises(KeyError):
                dict_without_default["X"]["Y"]

        def test_importMPS_maximize(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
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
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
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
            dummy = prob.add_variable("dummy")
            c1 = prob.add_variable("c1", 0, 1, const.LpBinary)
            c2 = prob.add_variable("c2", 0, 1, const.LpBinary)
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
            self.assertEqual(_constraint_named(problem, "LIM2").constant, -10)

        def test_importMPS_PL_bound(self):
            """Import MPS file with PL bound type."""
            with tempfile.NamedTemporaryFile(delete=False) as h:
                h.write(str.encode(EXAMPLE_MPS_PL_BOUNDS))
            _, problem = LpProblem.fromMPS(h.name)
            os.unlink(h.name)
            self.assertIsInstance(problem, LpProblem)

        def test_importMPF_MI_bound(self):
            """Import MPS file with MI bound type."""
            with tempfile.NamedTemporaryFile(delete=False) as h:
                h.write(str.encode(EXAMPLE_MPS_MI_BOUNDS))
            vars, problem = LpProblem.fromMPS(h.name)
            os.unlink(h.name)
            self.assertIsInstance(problem, LpProblem)
            mi_var = vars["YTWO"]
            self.assertEqual(mi_var.lowBound, float("-inf"))

        def test_unset_objective_value__is_valid(self):
            """Given a valid problem that does not converge,
            assert that it is still categorised as valid.
            """
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = prob.add_variable("x")
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
            x = prob.add_variable("x")
            prob += 1000 * x
            prob += x >= 1
            self.assertFalse(prob.valid())

        def test_infeasible_problem__is_not_valid(self):
            """Given a problem where x cannot converge to any value
            given conflicting constraints, assert that it is invalid."""
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = prob.add_variable("x")
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
        # def test_measuring_solving_time(self):
        #     time_limit = 10
        #     solver_settings = dict(
        #         COIN_CMD=30,
        #         COIN_CMD=30,
        #         SCIP_PY=30,
        #         SCIP_CMD=30,
        #         GUROBI_CMD=50,
        #         CPLEX_CMD=50,
        #         GUROBI=50,
        #         HiGHS=50,
        #         HiGHS_CMD=50,
        #     )
        #     bins = solver_settings.get(self.solver.name)
        #     if bins is None:
        #         # not all solvers have timeLimit support
        #         return
        #     prob = create_bin_packing_problem(bins=bins, seed=99)
        #     self.solver.timeLimit = time_limit
        #     status = prob.solve(self.solver)

        #     delta = 20
        #     reported_time = prob.solutionTime
        #     if self.solver.name == "COIN_CMD":
        #         reported_time = prob.solutionCpuTime

        #     self.assertAlmostEqual(
        #         reported_time,
        #         time_limit,
        #         delta=delta,
        #         msg=f"optimization time for solver {self.solver.name}",
        #     )
        #     self.assertIsNotNone(prob.objective)
        #     self.assertIsNotNone(prob.objective.value())
        #     self.assertEqual(status, const.LpStatusOptimal)
        #     for v in prob.variables():
        #         self.assertIsNotNone(v.varValue)

        # @gurobi_test
        # def test_time_limit_no_solution(self):
        #     time_limit = 1
        #     solver_settings = dict(HiGHS_CMD=60, HiGHS=60, COIN_CMD=60)
        #     bins = solver_settings.get(self.solver.name)
        #     if bins is None:
        #         # not all solvers have timeLimit support
        #         return
        #     prob = create_bin_packing_problem(bins=bins, seed=99)
        #     self.solver.timeLimit = time_limit
        #     status = prob.solve(self.solver)
        #     self.assertEqual(prob.status, const.LpStatusNotSolved)
        #     self.assertEqual(status, const.LpStatusNotSolved)
        #     self.assertEqual(prob.sol_status, const.LpSolutionNoSolutionFound)

        def test_invalid_var_names(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("a")
            w = prob.add_variable("b")
            y = prob.add_variable("g", -1, 1)
            z = prob.add_variable("End")
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            if self.solver.name not in [
                "GUROBI_CMD",  # end is a key-word for LP files
                "SCIP_CMD",  # not sure why it returns a wrong result
                "FSCIP_CMD",  # not sure why it returns a wrong result
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
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            customers = [1, 2, 3]
            agents = ["A", "B", "C"]

            # explicit param creates a dict of type LpVariable
            assign_vars = prob.add_variable_dicts(
                name="test", indices=(customers, agents)
            )
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # param by position creates a dict of type LpVariable
            assign_vars = prob.add_variable_dicts("test", (customers, agents))
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # explicit param creates list of LpVariable
            assign_vars_matrix = prob.add_variable_matrix(
                name="test", indices=(customers, agents)
            )
            for a in assign_vars_matrix:
                for b in a:
                    self.assertIsInstance(b, LpVariable)

            # param by position creates list of list of LpVariable
            assign_vars_matrix = prob.add_variable_matrix("test", (customers, agents))
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
            assign_vars = prob.add_variable_dicts(
                name="test", indices=(customers, agents)
            )
            for k, v in assign_vars.items():
                for a, b in v.items():
                    self.assertIsInstance(b, LpVariable)

            # explicit param creates list of list of LpVariable
            assign_vars_matrix = prob.add_variable_matrix(
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
            _, _, reducedCosts, shadowPrices, _, _ = solvers.CPLEX_CMD.readsol(
                solution_file
            )

            # Because mipopt solutions have no `reducedCost` fields
            # it should be all None
            self.assertTrue(all(c is None for c in reducedCosts.values()))

            # Because mipopt solutions have no `shadowPrices` fields
            # it should be all None
            self.assertTrue(all(c is None for c in shadowPrices.values()))

        def test_options_parsing_SCIP_HIGHS(self):
            name = self._testMethodName
            prob = LpProblem(name, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            # CHOCO has issues when given a time limit
            if self.solver.name in ["SCIP_CMD", "FSCIP_CMD"]:
                self.solver.options = ["limits/time", 20]
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )
            elif self.solver.name in ["HiGHS_CMD"]:
                self.solver.options = ["time_limit", 20]
                pulpTestCheck(
                    prob,
                    self.solver,
                    [const.LpStatusOptimal],
                    {x: 4, y: -1, z: 6, w: 0},
                )

        def test_sum_nan_values(self):
            import math

            prob = LpProblem(self._testMethodName, const.LpMinimize)
            a = math.nan
            x = prob.add_variable("x")
            with self.assertRaises(PulpError):
                x + a

        def test_multiply_nan_values(self):
            import math

            prob = LpProblem(self._testMethodName, const.LpMinimize)
            a = math.nan
            x = prob.add_variable("x")
            with self.assertRaises(PulpError):
                x * a

        def test_constraint_copy(self) -> None:
            """
            Comparison operators return LpAffineExpression with sense.
            copy() preserves terms, constant, and sense.
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            expr: LpAffineExpression = x + y + 1
            self.assertIsInstance(expr, LpAffineExpression)
            self.assertEqual(expr.constant, 1)

            c = expr <= 5
            self.assertIsInstance(c, LpAffineExpression)
            self.assertIsNotNone(c.sense)
            self.assertEqual(c.constant, -4)

            c2 = c.copy()
            self.assertIsInstance(c2, LpAffineExpression)
            self.assertEqual(c2.constant, -4)
            self.assertIsNotNone(c2.sense)
            self.assertEqual(str(c), str(c2))
            self.assertEqual(repr(c), repr(c2))

        def test_constraint_add(self) -> None:
            """
            __add__ operator on LpAffineExpression with sense (pending constraint)
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            expr: LpAffineExpression = x + y + 1
            self.assertIsInstance(expr, LpAffineExpression)
            self.assertEqual(expr.constant, 1)

            c1 = x + y <= 5
            self.assertIsInstance(c1, LpAffineExpression)
            self.assertIsNotNone(c1.sense)
            self.assertEqual(c1.constant, -5)
            self.assertEqual(str(c1), "x + y <= 5.0")
            self.assertEqual(repr(c1), "1.0*x + 1.0*y + -5.0 <= 0")

            c1_int = c1 + 2
            self.assertIsInstance(c1_int, LpAffineExpression)
            self.assertEqual(c1_int.constant, -3)
            self.assertEqual(str(c1_int), "x + y <= 3.0")
            self.assertEqual(repr(c1_int), "1.0*x + 1.0*y + -3.0 <= 0")

            c1_variable = c1 + x
            self.assertIsInstance(c1_variable, LpAffineExpression)
            self.assertEqual(str(c1_variable), str(2 * x + y <= 5))
            self.assertEqual(repr(c1_variable), repr(2 * x + y <= 5))

            expr = x + 1
            self.assertIsInstance(expr, LpAffineExpression)
            self.assertEqual(expr.constant, 1)
            self.assertEqual(str(expr), "x + 1")

            c1_expr = c1 + expr
            self.assertIsInstance(c1_expr, LpAffineExpression)
            self.assertEqual(c1_expr.constant, -4)
            self.assertEqual(str(c1_expr), str(2 * x + y <= 4))
            self.assertEqual(repr(c1_expr), repr(2 * x + y <= 4))

            constraint = x <= 1
            self.assertIsInstance(constraint, LpAffineExpression)
            c1_constraint = c1 + constraint
            self.assertEqual(str(c1_constraint), str(2 * x + y <= 6))
            self.assertEqual(repr(c1_constraint), repr(2 * x + y <= 6))

            constraint = x + 1 <= 2
            self.assertIsInstance(constraint, LpAffineExpression)
            self.assertEqual(constraint.constant, -1)
            c1_constraint = c1 + constraint
            self.assertEqual(str(c1_constraint), str(2 * x + y <= 6))
            self.assertEqual(repr(c1_constraint), repr(2 * x + y <= 6))

        def test_constraint_neg(self) -> None:
            """
            __neg__ operator on LpAffineExpression with sense
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            c1 = x + y <= 5
            self.assertIsInstance(c1, LpAffineExpression)
            self.assertEqual(c1.constant, -5)

            c1_neg = -c1
            self.assertIsInstance(c1_neg, LpAffineExpression)
            self.assertEqual(c1_neg.constant, 5)
            self.assertEqual(str(c1_neg), str(-x + -y <= -5))
            self.assertEqual(repr(c1_neg), repr(-x + -y <= -5))

        def test_constraint_sub(self) -> None:
            """
            __sub__ operator on LpAffineExpression with sense
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            expr0: LpAffineExpression = 0 * x
            self.assertIsInstance(expr0, LpAffineExpression)
            self.assertTrue(expr0.isNumericalConstant())

            c1 = x + y <= 5
            self.assertIsInstance(c1, LpAffineExpression)
            self.assertEqual(c1.constant, -5)

            c1_int = c1 - 2
            self.assertIsInstance(c1_int, LpAffineExpression)
            self.assertEqual(c1_int.constant, -7)

            c1_variable = c1 - x
            self.assertIsInstance(c1_variable, LpAffineExpression)
            self.assertEqual(str(c1_variable), "0*x + y <= 5.0")
            self.assertEqual(repr(c1_variable), "0.0*x + 1.0*y + -5.0 <= 0")

            expr: LpAffineExpression = x + 1
            self.assertIsInstance(expr, LpAffineExpression)
            c1_expr = c1 - expr
            self.assertIsInstance(c1_expr, LpAffineExpression)
            self.assertEqual(str(c1_expr), "0*x + y <= 6.0")
            self.assertEqual(repr(c1_expr), "0.0*x + 1.0*y + -6.0 <= 0")

            constraint = x <= 1
            self.assertIsInstance(constraint, LpAffineExpression)
            c1_constraint = c1 - constraint
            self.assertEqual(str(c1_constraint), "0*x + y <= 4.0")
            self.assertEqual(repr(c1_constraint), "0.0*x + 1.0*y + -4.0 <= 0")

            constraint = x + 1 <= 2
            self.assertIsInstance(constraint, LpAffineExpression)
            c1_constraint = c1 - constraint
            self.assertEqual(str(c1_constraint), "0*x + y <= 4.0")
            self.assertEqual(repr(c1_constraint), "0.0*x + 1.0*y + -4.0 <= 0")

        def test_constraint_mul(self) -> None:
            """
            __mul__ operator on LpAffineExpression with sense
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            c1 = x + y <= 5
            self.assertIsInstance(c1, LpAffineExpression)
            self.assertEqual(c1.constant, -5)

            c2 = y <= 5
            self.assertIsInstance(c2, LpAffineExpression)
            self.assertEqual(c2.constant, -5)

            c1_int = c1 * 2
            self.assertIsInstance(c1_int, LpAffineExpression)
            self.assertEqual(c1_int.constant, -10)
            self.assertEqual(str(c1_int), "2*x + 2*y <= 10.0")
            self.assertEqual(repr(c1_int), "2.0*x + 2.0*y + -10.0 <= 0")

            c1_const_expr = c1 * LpAffineExpression.from_constant(2)
            self.assertIsInstance(c1_const_expr, LpAffineExpression)
            self.assertEqual(c1_const_expr.constant, -10)
            self.assertEqual(str(c1_int), "2*x + 2*y <= 10.0")
            self.assertEqual(repr(c1_int), "2.0*x + 2.0*y + -10.0 <= 0")

            with self.assertRaises(TypeError):
                c1 * x

            with self.assertRaises(TypeError):
                c2 * x

            with self.assertRaises(TypeError):
                c1 * (x + 1)

            with self.assertRaises(TypeError):
                c2 * (x + 1)

        def test_constraint_div(self) -> None:
            """
            __div__ operator on LpAffineExpression with sense
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            y = prob.add_variable("y")

            c1 = x + y <= 5
            self.assertIsInstance(c1, LpAffineExpression)
            self.assertEqual(c1.constant, -5)

            c2 = y <= 5
            self.assertIsInstance(c2, LpAffineExpression)
            self.assertEqual(c2.constant, -5)

            c1_int = c1 / 2.0
            self.assertIsInstance(c1_int, LpAffineExpression)
            self.assertEqual(c1_int.constant, -2.5)
            self.assertEqual(str(c1_int), "0.5*x + 0.5*y <= 2.5")
            self.assertEqual(repr(c1_int), "0.5*x + 0.5*y + -2.5 <= 0")

            c1_const_expr = c1 / LpAffineExpression.from_constant(2)
            self.assertIsInstance(c1_const_expr, LpAffineExpression)
            self.assertEqual(c1_const_expr.constant, -2.5)
            self.assertEqual(str(c1_const_expr), "0.5*x + 0.5*y <= 2.5")
            self.assertEqual(repr(c1_const_expr), "0.5*x + 0.5*y + -2.5 <= 0")

            with self.assertRaises(TypeError):
                c1 / x

            with self.assertRaises(TypeError):
                c2 / x

            with self.assertRaises(TypeError):
                c1 / (x + 1)

            with self.assertRaises(TypeError):
                c2 / (x + 1)

        def test_variable_div(self):
            """
            __div__ operator on LpVariable
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x")
            x_div = x / 2
            self.assertIsInstance(x_div, LpAffineExpression)
            self.assertEqual(x_div[x], 0.5)

            self.assertEqual(str(x_div), "0.5*x")

        def test_regression_794(self) -> None:
            # See: https://github.com/coin-or/pulp/issues/794#issuecomment-2671682768

            initial_stock = 8  # s_0
            demands = [5, 4, 8, 10, 4, 2, 1]  # demands[t] = d_t
            max_periods = len(demands) - 1  # T
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            # Create decision variables.
            supply: list[LpVariable] = []  # supply[t] = x_t
            for t in range(1, max_periods + 1):
                variable = prob.add_variable(f"x_{t}", cat="Integer", lowBound=0)
                supply.append(variable)

            stock: list[Union[LpVariable, int]] = [initial_stock]  # stock[t] = s_t
            for t in range(1, max_periods + 1):
                variable = prob.add_variable(f"s_{t}", cat="Integer", lowBound=0)
                stock.append(variable)

            # Create the constraints.
            for t in range(1, max_periods + 1):
                lhs = stock[t]
                rhs = stock[t - 1] + supply[t - 1] - demands[t - 1]
                expr = lhs == rhs

                self.assertIsInstance(lhs, LpVariable)
                self.assertEqual(str(lhs), f"s_{t}")

                self.assertIsInstance(rhs, LpAffineExpression)
                self.assertIsInstance(expr, LpAffineExpression)
                self.assertIsNotNone(expr.sense)

                if t == 1:
                    self.assertEqual(
                        str(rhs), f"x_{t} + {stock[t - 1] - demands[t - 1]}"
                    )
                    self.assertEqual(expr.constant, -rhs.constant + lhs)
                else:
                    self.assertEqual(str(rhs), f"s_{t - 1} + x_{t} - {demands[t - 1]}")
                    self.assertEqual(expr.constant, -rhs.constant)

        def test_regression_805(self):
            # See: https://github.com/coin-or/pulp/issues/805

            e = LpAffineExpression.from_constant(1)
            self.assertIsNone(e.name)

            e2 = e.copy()
            e2.name = "Test2"
            self.assertEqual(e2.name, "Test2")
            self.assertIsNone(e.name)

            e = LpAffineExpression.from_constant(1, name="Test1")
            self.assertEqual(e.name, "Test1")

            e2 = e.copy()
            e2.name = "Test2"
            self.assertEqual(e2.name, "Test2")
            self.assertEqual(e.name, "Test1")

        def test_decimal_815_addinplace(self):
            # See: https://github.com/coin-or/pulp/issues/815
            m1 = 3
            m2 = Decimal("8.1")
            extra = 5
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", lowBound=0, upBound=50, cat=const.LpContinuous)
            y = prob.add_variable(
                "y", lowBound=0, upBound=Decimal("32.24"), cat=const.LpContinuous
            )
            include_extra = prob.add_variable("include_extra1", cat=const.LpBinary)

            expression = LpAffineExpression.empty()
            expression += x * m1 + include_extra * extra - y
            self.assertEqual(str(expression), "5*include_extra1 + 3*x - y")

            second_expression = LpAffineExpression.empty()
            second_expression += x * m2 - 6 - y
            self.assertEqual(str(second_expression), "8.1*x - y - 6")

            second_expression = LpAffineExpression.from_constant(0.0)
            second_expression += x * m2 - 6 - y
            self.assertEqual(str(second_expression), "8.1*x - y - 6")

            second_expression_2 = x * m2 - 6 - y
            self.assertEqual(str(second_expression_2), "8.1*x - y - 6")

        def test_mps_output_unbounded_variable(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", lowBound=0, upBound=None)
            y = prob.add_variable("y", lowBound=None, upBound=10)
            prob += x + y, "obj"
            prob += x + y >= 1, "c1"
            with tempfile.NamedTemporaryFile(
                mode="r", suffix=".mps", delete=False
            ) as f:
                mps_path = f.name
            try:
                prob.writeMPS(mps_path)
                with open(mps_path) as f:
                    content = f.read()
                self.assertNotIn(" inf", content.lower())
                self.assertNotIn("-inf", content.lower())
            finally:
                try:
                    os.remove(mps_path)
                except OSError:
                    pass

        def test_numpy_float(self):
            try:
                import numpy as np
            except ImportError:
                self.skipTest("numpy not available")

            model = LpProblem("float_test", sense=const.LpMinimize)

            var = model.add_variable(name="var", lowBound=0, cat=const.LpContinuous)
            model += np.float64(34.5) >= var
            model += var <= np.float64(34.5)

            model.solve()

        def test_decimal_815(self):
            # See: https://github.com/coin-or/pulp/issues/815
            # Will not run on other solvers due to how results are updated
            m1 = 3
            m2 = Decimal("8.1")
            extra = 5
            prob = LpProblem("graph", const.LpMaximize)

            x = prob.add_variable("x", lowBound=0, upBound=50, cat=const.LpContinuous)
            y = prob.add_variable(
                "y", lowBound=0, upBound=Decimal("32.24"), cat=const.LpContinuous
            )
            include_extra = prob.add_variable("include_extra1", cat=const.LpBinary)

            prob += y

            # y = 3x + 5 | y = 3x
            e1 = x * m1 + include_extra * extra - y
            c1 = e1 == 0
            prob += c1

            # y = 8.1x - 6
            e2 = x * m2 - 6 - y
            c2 = e2 == 0
            prob += c2

            # This generates two possible systems of equations,
            # y = 3x + 5
            # y = 8.1x - 6
            # this intersects at ~(11/5, 58/5)

            # OR
            # y = 3x
            # y = 8.1x-6
            # this intersects at ~(6/5, 18/5)
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 2.15686, y: 11.4706},
            )


class COIN_CMD_CBCOptionsTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COIN_CMD

    @staticmethod
    def read_command_line_from_log_file(logPath):
        """
        Read from log file the command line executed.
        """
        with open(logPath) as fp:
            for row in fp.readlines():
                if row.startswith("command line "):
                    return row
        raise ValueError(f"Unable to find the command line in {logPath}")

    @staticmethod
    def extract_option_from_command_line(
        command_line, option, prefix="-", grp_pattern="[a-zA-Z]+"
    ):
        """
        Extract option value from command line string.

        :param command_line: str that we extract the option value from
        :param option: str representing the option name (e.g., presolve, sec, etc)
        :param prefix: str (default: '-')
        :param grp_pattern: str (default: '[a-zA-Z]+') - regex to capture option value

        :return: option value captured (str); otherwise, None

        example:

        >>> cmd = "cbc model.mps -presolve off -timeMode elapsed -branch"
        >>> COIN_CMD_CBCOptionsTest.extract_option_from_command_line(cmd, "presolve")
        'off'

        >>> cmd = "cbc model.mps -strong 101 -timeMode elapsed -branch"
        >>> COIN_CMD_CBCOptionsTest.extract_option_from_command_line(cmd, "strong", grp_pattern="\\d+")
        '101'
        """
        pattern = re.compile(rf"{prefix}{option}\s+({grp_pattern})\s*")
        m = pattern.search(command_line)
        if not m:
            print(f"{option} not found in {command_line}")
            return None
        option_value = m.groups()[0]
        return option_value

    def test_presolve_off(self):
        """
        Test if setting presolve=False in COIN_CMD adds presolve off to the
        command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["presolve"] = False
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
        # Extract option_value from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="presolve"
        )
        self.assertEqual("off", option_value)

    def test_cuts_on(self):
        """
        Test if setting cuts=True in COIN_CMD adds "gomory on knapsack on
        probing on" to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["cuts"] = True
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
        # Extract option values from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        gomory_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="gomory"
        )
        knapsack_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="knapsack", prefix=""
        )
        probing_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="probing", prefix=""
        )
        self.assertListEqual(
            ["on", "on", "on"], [gomory_value, knapsack_value, probing_value]
        )

    def test_cuts_off(self):
        """
        Test if setting cuts=False adds cuts off to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["cuts"] = False
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
        # Extract option value from the command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="cuts"
        )
        self.assertEqual("off", option_value)

    def test_strong(self):
        """
        Test if setting strong=10 adds strong 10 to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["strong"] = 10
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
        # Extract option value from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="strong", grp_pattern="\\d+"
        )
        self.assertEqual("10", option_value)


class CPLEX_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CPLEX_CMD


class CPLEX_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CPLEX_PY

    def _build(self, **kwargs):
        """
        Builds and returns a solver instance after creating and initializing a bin packing problem.
        """
        problem = create_bin_packing_problem(bins=40, seed=99)
        solver = self.solveInst(**kwargs)
        solver.buildSolverModel(lp=problem)
        return solver

    def test_search_param_without_solver_model(self):
        """
        Tests the behavior of the `search_param` method when invoked without a `solverModel`
        initialized. Validates that an appropriate error is raised under these conditions.
        """
        solver = self.solveInst()
        with self.assertRaises(PulpSolverError):
            solver.search_param("barrier.algorithm")

    def test_get_param(self):
        """
        Tests the `get_param` method of the solver instance to ensure the correct
        value is returned for a given parameter key.
        """
        solver = self._build()
        self.assertEqual(solver.get_param("barrier.algorithm"), 0)

    def test_get_param_with_full_path(self):
        """
        Test case for accessing a solver's parameter by its full hierarchical path.
        """
        solver = self._build()
        self.assertEqual(solver.get_param("parameters.barrier.algorithm"), 0)

    def test_set_param(self):
        """
        Tests the functionality for setting a parameter in the solver.
        """
        param = "barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(solver.get_param(name=param), 100)

    def test_set_param_with_full_path(self):
        """
        Tests the functionality for setting a parameter using its full hierarchical path in the solver.
        """
        param = "parameters.barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(solver.get_param(name=param), 100)

    def test_changed_param(self):
        param = "parameters.barrier.limits.iteration"
        solver = self._build(**{param: 100})
        self.assertEqual(len(solver.get_changed_params()), 1)

    def test_callback(self):
        from cplex.callbacks import (
            IncumbentCallback,  # type: ignore[import-not-found, import-untyped]
        )

        counter = 0

        class Callback(IncumbentCallback):
            def __call__(self):
                nonlocal counter
                counter += 1

        problem = create_bin_packing_problem(bins=5, seed=55)
        pulpTestCheck(
            problem, self.solver, [const.LpStatusOptimal], callback=[Callback]
        )
        self.assertGreaterEqual(counter, 1)


class XPRESS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.XPRESS_CMD


class XPRESS_PyTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.XPRESS_PY


class COIN_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COIN_CMD

    def test_add_variable_dicts_tuple_indices_mps_path(self):
        """Tuple keys from a list of indices build names with punctuation/spaces; CBC MPS path must run."""
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        keys = [(0, 0), (0, 1), (1, 0)]
        x = prob.add_variable_dicts("flow", keys, lowBound=0, cat=const.LpContinuous)
        prob += lpSum(x[k] for k in keys)
        prob += lpSum(x[k] for k in keys) >= 1, "cover"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpStatusOptimal],
            {
                x[(0, 0)]: 1.0,
                x[(0, 1)]: 0.0,
                x[(1, 0)]: 0.0,
            },
            objective=1.0,
        )

    def test_add_variable_dicts_tuple_indices_mip_mps_path(self):
        """Integer variables with tuple-index dicts use MPS integer markers; COIN_CMD must accept."""
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        keys = [(1, "east"), (2, "west")]
        y = prob.add_variable_dicts("open", keys, cat=const.LpBinary)
        prob += y[(1, "east")] + 2 * y[(2, "west")]
        prob += y[(1, "east")] + y[(2, "west")] >= 1, "pick_one"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpStatusOptimal],
            {y[(1, "east")]: 1.0, y[(2, "west")]: 0.0},
            objective=1.0,
        )


class COINMP_DLLTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COINMP_DLL


class GLPK_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GLPK_CMD

    def test_issue814_rounding_mip(self):
        """
        Test there is no rounding issue for MIP problems as described in #814
        """

        # bounds and constraints are formatted as .12g
        # see pulp.py asCplexLpVariable / asCplexLpConstraint methods
        ub = 999999999999

        assert int(format(ub, ".12g")) == ub
        assert float(format(ub + 2, ".12g")) != float(ub + 2)

        model = LpProblem("mip-814", const.LpMaximize)
        Q = model.add_variable("Q", cat="Integer", lowBound=0, upBound=ub)
        model += Q
        model += Q >= 0
        model.solve(self.solver)
        assert Q.value() == ub

    def test_issue814_rounding_lp(self):
        """
        Test there is no rounding issue for LP (simplex method) problems as described in #814
        """
        ub = 999999999999.0
        assert float(format(ub, ".12g")) == ub
        assert float(format(ub + 0.1, ".12g")) != ub + 0.1

        for simplex in ["primal", "dual"]:
            model = LpProblem(f"lp-814-{simplex}", const.LpMaximize)
            Q = model.add_variable("Q", lowBound=0, upBound=ub)
            model += Q
            model += Q >= 0
            self.solver.options.append("--" + simplex)
            model.solve(self.solver)
            self.solver.options = self.solver.options[:-1]
            assert Q.value() == ub

    def test_issue814_rounding_ipt(self):
        """
        Test there is no rounding issue for LP (interior point method) problems as described in #814
        """
        # this one is limited by GLPK int pt feasibility, not formatting
        ub = 12345678999.0

        model = LpProblem("ipt-814", const.LpMaximize)
        Q = model.add_variable("Q", lowBound=0, upBound=ub)
        model += Q
        model += Q >= 0
        self.solver.options.append("--interior")
        model.solve(self.solver)
        self.solver.options = self.solver.options[:-1]
        assert abs(Q.value() - ub) / ub < 1e-9


class GUROBITest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI


class GUROBI_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.GUROBI_CMD


class PYGLPKTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.PYGLPK


class YAPOSIBTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.YAPOSIB


class CHOCO_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CHOCO_CMD


class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.MIPCL_CMD


class MOSEKTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.MOSEK


class SCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.SCIP_CMD


class FSCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.FSCIP_CMD


class SCIP_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.SCIP_PY


class HiGHS_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.HiGHS

    def test_callback(self):
        prob = create_bin_packing_problem(bins=40, seed=99)

        # we pass a list as data to the tuple, so we can edit it.
        # then we count the number of calls and stop the solving
        # for more information on the callback, see: github.com/ERGO-Code/HiGHS @ examples/call_highs_from_python
        def user_callback(
            callback_type, message, data_out, data_in, user_callback_data
        ):
            #
            if (
                callback_type
                == solvers.HiGHS.hscb.HighsCallbackType.kCallbackMipInterrupt
            ):
                print(
                    f"userInterruptCallback(type {callback_type}); "
                    f"data {user_callback_data};"
                    f"message: {message};"
                    f"objective {data_out.objective_function_value:.4g};"
                )
                print(f"Dual bound = {data_out.mip_dual_bound:.4g}")
                print(f"Primal bound = {data_out.mip_primal_bound:.4g}")
                print(f"Gap = {data_out.mip_gap:.4g}")
                if isinstance(user_callback_data, list):
                    user_callback_data.append(1)
                    data_in.user_interrupt = len(user_callback_data) > 5

        solver = solvers.HiGHS(
            callbackTuple=(user_callback, []),
            callbacksToActivate=[
                solvers.HiGHS.hscb.HighsCallbackType.kCallbackMipInterrupt
            ],
        )
        prob.solve(solver)


class HiGHS_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.HiGHS_CMD

    @unittest.skipIf(sys.platform == "win32", "Windows fails for whatever reason")
    def test_relaxed_mip(self):
        super().test_relaxed_mip()


class COPTTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COPT


class CUOPTTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CUOPT


class SASTest:
    def test_sas_with_option(self):
        prob = LpProblem("test", const.LpMinimize)
        X = prob.add_variable_dicts("x", [1, 2, 3], lowBound=0.0, cat="Integer")
        prob += 2 * X[1] - 3 * X[2] - 4 * X[3], "obj"
        prob += -2 * X[2] - 3 * X[3] >= -5, "R1"
        prob += X[1] + X[2] + 2 * X[3] <= 4, "R2"
        prob += X[1] + 2 * X[2] + 3 * X[3] <= 7, "R3"
        self.solver.optionsDict["with"] = "lp"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpStatusOptimal],
            {X[1]: 0.0, X[2]: 2.5, X[3]: 0.0},
        )


class SAS94Test(BaseSolverTest.PuLPTest, SASTest):
    solveInst = solvers.SAS94


class SASCASTest(BaseSolverTest.PuLPTest, SASTest):
    solveInst = solvers.SASCAS


# class CyLPTest(BaseSolverTest.PuLPTest):
#     solveInst = CYLP


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
            if v.varValue is not None and abs(v.varValue - x) > eps:
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
            c = _constraint_named(prob, cname)
            if abs(c.pi - p) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nconstraint.pi {} == {} != {}".format(
                        solver, cname, c.pi, p
                    )
                )
    if slacks:
        for cname, slack in slacks.items():
            c = _constraint_named(prob, cname)
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


def _affine_keyed(expr: LpAffineExpression) -> tuple[float, list[tuple[str, float]]]:
    return (
        float(expr.constant),
        sorted((v.name, float(expr[v])) for v in expr),
    )


class TestLpSumVars(unittest.TestCase):
    def test_lpSum_vars_matches_lpSum(self) -> None:
        prob = LpProblem("t")
        x = prob.add_variable("x")
        y = prob.add_variable("y")
        a = lpSum([x, y])
        b = lpSum_vars([x, y])
        self.assertEqual(_affine_keyed(a), _affine_keyed(b))

    def test_lpSum_vars_empty(self) -> None:
        e = lpSum_vars([])
        self.assertEqual(len(e), 0)
        self.assertEqual(e.constant, 0)

    def test_lpSum_vars_coefs_matches_lpSum(self) -> None:
        prob = LpProblem("t")
        x = prob.add_variable("x")
        y = prob.add_variable("y")
        ref = lpSum([2 * x, 3 * y])
        got = lpSum_vars_coefs([(x, 2.0), (y, 3.0)])
        self.assertEqual(_affine_keyed(ref), _affine_keyed(got))

    def test_lpSum_vars_coefs_empty(self) -> None:
        e = lpSum_vars_coefs([])
        self.assertEqual(len(e), 0)
        self.assertEqual(e.constant, 0)

    def test_add_term_ids_coeffs_bad_id(self) -> None:
        prob = LpProblem("t")
        prob.add_variable("x")
        v = prob.add_variable("y")
        model = v._var.containing_model()
        e = LpAffineExpression.empty()
        ids = array.array("Q", [99])
        coeffs = array.array("d", [1.0])
        with self.assertRaises(ValueError):
            e._expr.add_term_ids_coeffs(model, ids, coeffs)

    def test_lpSum_vars_mixed_model(self) -> None:
        p1 = LpProblem("p1")
        p2 = LpProblem("p2")
        x = p1.add_variable("x")
        y = p2.add_variable("y")
        with self.assertRaises(PulpError):
            lpSum_vars([x, y])

    def test_lpSum_vars_coefs_nonfinite(self) -> None:
        prob = LpProblem("t")
        x = prob.add_variable("x")
        with self.assertRaises(PulpError):
            lpSum_vars_coefs([(x, float("nan"))])


def getSortedDict(prob, keyCons="name", keyVars="name"):
    _dict = prob.toDict()
    # Support None names; use str() so we never compare str vs float
    _dict["constraints"].sort(
        key=lambda v: (v.get(keyCons) is None, str(v.get(keyCons, "")))
    )
    _dict["variables"].sort(
        key=lambda v: (v.get(keyVars) is None, str(v.get(keyVars, "")))
    )
    return _dict


if __name__ == "__main__":
    unittest.main()
