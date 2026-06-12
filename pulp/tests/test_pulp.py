"""
Tests for pulp
"""

import array
import os
import tempfile
import unittest
from decimal import Decimal

import pulp.apis as solvers
import pulp.mps_lp as mps_lp
from pulp import (
    LpAffineExpression,
    LpConstraint,
    LpProblem,
    LpVariable,
    lpSum,
    lpSum_vars,
    lpSum_vars_coefs,
)
from pulp import constants as const
from pulp.constants import PulpError
from pulp.tests.solver_common import (
    EXAMPLE_MPS_MI_BOUNDS,
    EXAMPLE_MPS_PL_BOUNDS,
    EXAMPLE_MPS_RHS56,
    _constraint_named,
    getSortedDict,
)
from pulp.utilities import makeDict

try:
    import gurobipy as gp  # type: ignore[import-not-found, import-untyped]
except ImportError:
    gp = None  # type: ignore[assignment]


# from: http://lpsolve.sourceforge.net/5.5/mps-format.htm
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

    def _make_prob(self, name: str | None = None) -> LpProblem:
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


class PuLPModelTest(unittest.TestCase):
    """Solver-independent model, I/O, and expression tests (run once)."""

    def _default_solver_available(self) -> bool:
        return solvers.COIN_CMD().available() or solvers.GLPK_CMD().available()

    def _solve_exported(self, prob: LpProblem) -> int:
        if not self._default_solver_available():
            self.skipTest("Default solver not available for export test validation")
        return prob.solve()

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

        def test_pulpTestAll(self):
            """
            Test the availability of the function pulpTestAll
            """

        def test_assignInvalidStatus(self):
            t = LpProblem("test")
            Invalid = -100
            self.assertRaises(const.PulpError, lambda: t.assignStatus(Invalid))
            self.assertRaises(const.PulpError, lambda: t.assignStatus(0, Invalid))

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

        def test_false_constraint(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)

            def add_const(prob):
                prob += 0 - 3 == 0

            self.assertRaises(TypeError, add_const, prob=prob)

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

            stock: list[LpVariable | int] = [initial_stock]  # stock[t] = s_t
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
        var1, prob1 = LpProblem.fromDict(prob.toDict())
        self.assertDictEqual(getSortedDict(prob), getSortedDict(prob1))
        x, y, z, w = (var1[n] for n in ["x", "y", "z", "w"])
        self.assertEqual(self._solve_exported(prob1), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), -1)
        self.assertAlmostEqual(z.value(), 6)
        self.assertAlmostEqual(w.value(), 0)

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
        var1, prob1 = LpProblem.fromDict(prob.toDict())
        self.assertDictEqual(getSortedDict(prob), getSortedDict(prob1))
        x, y, z, w = (var1[n] for n in ["x", "y", "z", "w"])
        self.assertEqual(self._solve_exported(prob1), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), 1)
        self.assertAlmostEqual(z.value(), 6)
        self.assertAlmostEqual(w.value(), 0)

    def test_export_json_LP(self):
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
        filename = name + ".json"
        prob.toJson(filename, indent=4)
        var1, prob1 = LpProblem.fromJson(filename)
        try:
            os.remove(filename)
        except OSError:
            pass
        self.assertDictEqual(getSortedDict(prob), getSortedDict(prob1))
        x, y, z, w = (var1[n] for n in ["x", "y", "z", "w"])
        self.assertEqual(self._solve_exported(prob1), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), -1)
        self.assertAlmostEqual(z.value(), 6)
        self.assertAlmostEqual(w.value(), 0)

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
        self.assertDictEqual(data, data_backup)
        self.assertDictEqual(getSortedDict(prob), getSortedDict(prob1))
        x, y, z = (var1[n] for n in ["x", "y", "z"])
        self.assertEqual(self._solve_exported(prob1), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 3)
        self.assertAlmostEqual(y.value(), -0.5)
        self.assertAlmostEqual(z.value(), 7)

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
        var1, prob1 = LpProblem.fromDict(prob.toDict())
        self.assertDictEqual(getSortedDict(prob), getSortedDict(prob1))
        x, y, z, w = (var1[n] for n in ["x", "y", "z", "w"])
        self.assertEqual(self._solve_exported(prob1), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), 1)
        self.assertAlmostEqual(z.value(), 8)
        self.assertAlmostEqual(w.value(), 0)

    def test_export_solver_dict_LP(self):
        if not solvers.COIN_CMD().available():
            self.skipTest("COIN_CMD not available for solver export test")
        ref_solver = solvers.COIN_CMD(msg=False)
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
        restored = solvers.getSolverFromDict(ref_solver.toDict())
        self.assertEqual(prob.solve(restored), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), -1)
        self.assertAlmostEqual(z.value(), 6)
        self.assertAlmostEqual(w.value(), 0)

    def test_export_solver_json(self):
        if not solvers.COIN_CMD().available():
            self.skipTest("COIN_CMD not available for solver export test")
        name = self._testMethodName
        ref_solver = solvers.COIN_CMD(msg=False)
        ref_solver.mip = True
        ref_solver.optionsDict = dict(gapRel=0.1, gapAbs=1, threads=1, warmStart=True)
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
        filename = name + ".json"
        ref_solver.toJson(filename, indent=4)
        restored = solvers.getSolverFromJson(filename)
        try:
            os.remove(filename)
        except OSError:
            pass
        self.assertEqual(prob.solve(restored), const.LpStatusOptimal)
        self.assertAlmostEqual(x.value(), 4)
        self.assertAlmostEqual(y.value(), -1)
        self.assertAlmostEqual(z.value(), 6)
        self.assertAlmostEqual(w.value(), 0)


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
