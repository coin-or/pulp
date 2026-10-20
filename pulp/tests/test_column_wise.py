"""Column-wise modeling: ``LpProblem.add_column``, ``LpConstraint.set_coefficient``
and ``LpProblem.remove_variables`` (column generation grows one problem), and
editing constraints already in a problem through their ``LpConstraint``."""

import os
import tempfile
import unittest
import warnings

import pulp
from pulp import LpProblem, _rustcore, const
from pulp.constants import PulpError


def _row_wise() -> LpProblem:
    """min x + 2y + 3z  s.t.  c1: x + y >= 1,  c2: y + z >= 1,  c3: x + z <= 1."""
    prob = LpProblem("row_wise", const.LpMinimize)
    x = prob.add_variable("x", 0, 1)
    y = prob.add_variable("y", 0, 1)
    z = prob.add_variable("z", 0, 1)
    prob += x + 2 * y + 3 * z
    prob += x + y >= 1, "c1"
    prob += y + z >= 1, "c2"
    prob += x + z <= 1, "c3"
    return prob


def _column_wise() -> LpProblem:
    """The same problem, its rows created empty and filled one column at a time."""
    prob = LpProblem("row_wise", const.LpMinimize)
    x = prob.add_variable("x", 0, 1)
    prob += x
    prob += x >= 1, "c1"
    prob += x >= 1, "c2"
    prob += x <= 1, "c3"
    c1, c2, c3 = prob.constraints()
    c2.set_coefficient(x, 0)  # x is not in c2
    prob.add_column("y", 0, 1, obj=2, coefficients={c1: 1, c2: 1})
    prob.add_column("z", 0, 1, obj=3, coefficients={c2: 1, c3: 1})
    return prob


def _objective(prob: LpProblem) -> dict[str, float]:
    assert prob.objective is not None
    return {v.name: a for v, a in prob.objective.items()}


def _lp_solver() -> pulp.LpSolver | None:
    available = pulp.listSolvers(onlyAvailable=True)
    for name in ("HiGHS", "COIN_CMD", "PULP_CBC_CMD", "GLPK_CMD"):
        if name in available:
            return pulp.getSolver(name, msg=False)
    return None


class ColumnWiseModelTest(unittest.TestCase):
    def test_add_column_fills_rows_and_objective(self):
        prob = _column_wise()
        rows = {c.name: {v.name: a for v, a in c.items()} for c in prob.constraints()}
        self.assertEqual(rows["c1"], {"x": 1.0, "y": 1.0})
        self.assertEqual(rows["c2"], {"y": 1.0, "z": 1.0})
        self.assertEqual(rows["c3"], {"x": 1.0, "z": 1.0})
        self.assertEqual(_objective(prob), {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_add_column_without_objective_creates_none(self):
        prob = LpProblem("no_objective", const.LpMinimize)
        x = prob.add_variable("x", 0, 1)
        prob += x >= 0, "c"
        (c,) = prob.constraints()
        y = prob.add_column("y", 0, 1, coefficients={c: 2})
        self.assertIsNone(prob.objective)
        prob.add_column("z", 0, 1, obj=1.5)
        self.assertEqual(_objective(prob), {"z": 1.5})
        self.assertEqual(c.items(), [(x, 1.0), (y, 2.0)])

    def test_add_column_binary_and_bounds(self):
        prob = LpProblem("bounds", const.LpMinimize)
        b = prob.add_column("b", cat=const.LpBinary)
        self.assertEqual((b.lowBound, b.upBound, b.cat), (0, 1, const.LpInteger))
        with self.assertRaises(PulpError):
            prob.add_column("bad", lowBound=float("inf"))

    def test_add_column_rejects_bad_input_without_changing_the_model(self):
        prob = LpProblem("bad", const.LpMinimize)
        x = prob.add_variable("x", 0, 1)
        prob += x >= 0, "c"
        (c,) = prob.constraints()
        with self.assertRaises(ValueError):
            prob.add_column("y", 0, 1, coefficients={c: float("nan")})
        with self.assertRaises(ValueError):
            prob.add_column("y", 0, 1, obj=float("inf"))
        self.assertEqual(prob.numVariables(), 1)
        self.assertEqual(c.items(), [(x, 1.0)])

    def test_add_constraint_returns_the_stored_constraint(self):
        prob = LpProblem("handle", const.LpMinimize)
        x = prob.add_variable("x", 0, 1)
        c = prob.addConstraint(x <= 1, "c")
        self.assertEqual((c.name, c.id), ("c", 0))
        y = prob.add_column("y", 0, 1, coefficients={c: 3})
        self.assertEqual(prob.constraints()[0].items(), [(x, 1.0), (y, 3.0)])

    def test_category_setter(self):
        prob = LpProblem("cat", const.LpMinimize)
        x = prob.add_variable("x", 0, 5)
        x.cat = const.LpInteger
        self.assertEqual((x.cat, x.lowBound, x.upBound), (const.LpInteger, 0, 5))
        x.cat = const.LpContinuous
        self.assertEqual(x.cat, const.LpContinuous)
        x.cat = const.LpBinary
        self.assertEqual((x.cat, x.lowBound, x.upBound), (const.LpInteger, 0, 1))
        # A copy relaxed or made integer leaves the original as it was.
        copy = prob.copy()
        copy.variables()[0].cat = const.LpContinuous
        self.assertEqual(x.cat, const.LpInteger)

    def test_set_coefficient_updates_and_removes_terms(self):
        prob = _row_wise()
        x, y, z = prob.variables()
        c1 = prob.constraints()[0]
        c1.set_coefficient(x, 5)
        c1.set_coefficient(z, -1)
        self.assertEqual(c1.items(), [(x, 5.0), (y, 1.0), (z, -1.0)])
        c1.set_coefficient(y, 0)
        self.assertEqual(c1.items(), [(x, 5.0), (z, -1.0)])
        with self.assertRaises(PulpError):
            c1.set_coefficient(x, float("inf"))
        other = LpProblem("other", const.LpMinimize).add_variable("w", 0, 1)
        with self.assertRaises(PulpError):
            c1.set_coefficient(other, 1)

    def test_remove_variables_detaches_them(self):
        prob = _row_wise()
        x, y, z = prob.variables()
        prob.remove_variables([y])
        rows = {c.name: [v.name for v, _ in c.items()] for c in prob.constraints()}
        self.assertEqual(rows, {"c1": ["x"], "c2": ["z"], "c3": ["x", "z"]})
        self.assertEqual(list(_objective(prob)), ["x", "z"])
        self.assertEqual([v.name for v in prob.exported_variables()], ["x", "z"])
        # The handle stays valid and can be put back column-wise.
        self.assertEqual(y.name, "y")
        prob.constraints()[0].set_coefficient(y, 1)
        self.assertIn("y", [v.name for v in prob.exported_variables()])

    def test_remove_variables_also_leaves_sos_groups(self):
        prob = _row_wise()
        x, y, z = prob.variables()
        prob.add_sos_group(_rustcore.SosKind.Sos1, "s", {x: 1, y: 2, z: 3})
        prob.remove_variables([y])
        groups = prob._model.sos_export()
        self.assertEqual(
            [[vid for vid, _ in pairs] for _, _, pairs in groups], [[0, 2]]
        )

    def test_written_files_match_the_row_wise_problem(self):
        for suffix, write in ((".lp", "writeLP"), (".mps", "writeMPS")):
            texts = []
            for prob in (_row_wise(), _column_wise()):
                with tempfile.TemporaryDirectory() as tmp:
                    path = os.path.join(tmp, "model" + suffix)
                    getattr(prob, write)(path)
                    with open(path) as f:
                        texts.append(f.read())
            self.assertEqual(texts[0], texts[1], suffix)


class EditAddedConstraintTest(unittest.TestCase):
    """Constraints in a problem are edited through ``LpConstraint``; editing the
    expression they were added from only warns (issue #933)."""

    def test_lp_constraint_edits_reach_the_problem(self):
        prob = _row_wise()
        x, y, z = prob.variables()
        c1 = prob.get_constraint_by_name("c1")
        assert c1 is not None
        c1[z] = 3
        del c1[y]
        c1.changeRHS(2)
        self.assertEqual(prob.constraints()[0].items(), [(x, 1.0), (z, 3.0)])
        self.assertEqual(prob.constraints()[0].getLb(), 2)
        c3 = prob.constraints()[2]
        c3.sense = const.LpConstraintGE
        c3.constant = -0.5
        self.assertEqual(str(prob.constraints()[2]), "x + z >= 0.5")

    def test_lp_constraint_in_place_add_and_subtract(self):
        prob = LpProblem("iadd", const.LpMinimize)
        x = prob.add_variable("x", 0, 5)
        y = prob.add_variable("y", 0, 5)
        c = prob.addConstraint(x <= 2, "c")
        c += 2 * y
        c -= 1
        c -= x
        self.assertEqual(c.items(), [(y, 2.0)])
        self.assertEqual((c.sense, c.getUb(), c.name), (const.LpConstraintLE, 3, "c"))
        self.assertEqual(str(prob.constraints()[0]), "2*y <= 3")

    def test_edited_rows_are_written(self):
        edited, expected = _row_wise(), _row_wise()
        c1 = edited.constraints()[0]
        c1[edited.variables()[2]] = 4
        c1.changeRHS(2)
        expected_c1 = expected.constraints()[0]
        expected_c1.set_coefficient(expected.variables()[2], 4)
        expected_c1.changeRHS(2)
        self.assertIn("c1: x + y + 4 z >= 2", self._lp_text(edited))
        self.assertEqual(self._lp_text(edited), self._lp_text(expected))

    def test_invalid_edits_raise_and_leave_the_row(self):
        prob = _row_wise()
        x, y, _ = prob.variables()
        c1 = prob.constraints()[0]
        with self.assertRaises(PulpError):
            c1[x] = float("inf")
        with self.assertRaises(PulpError):
            c1.changeRHS(float("nan"))
        with self.assertRaises(PulpError):
            c1 += float("inf") * x
        with self.assertRaises(PulpError):
            setattr(c1, "sense", None)
        self.assertEqual(c1.items(), [(x, 1.0), (y, 1.0)])
        self.assertEqual((c1.sense, c1.getLb()), (const.LpConstraintGE, 1))

    def test_editing_the_added_expression_warns_and_leaves_the_problem(self):
        prob = LpProblem("issue_933", const.LpMinimize)
        x = prob.add_variable("x", 0, 5)
        y = prob.add_variable("y", 0, 5)
        constr = x <= 2
        prob += constr, "c"
        edits = [
            lambda: constr.__setitem__(x, 2),
            lambda: constr.addterm(y, 1),
            lambda: constr.__iadd__(y),
            lambda: constr.__isub__(1),
            lambda: constr.addInPlace({"a": y, "b": [y, 1]}),
            lambda: constr.changeRHS(4),
            lambda: setattr(constr, "constant", 1),
            lambda: setattr(constr, "sense", const.LpConstraintGE),
        ]
        for edit in edits:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                edit()
            self.assertEqual(len(caught), 1)
            message = str(caught[0].message)
            self.assertIn("LpConstraint", message)
            self.assertIn("get_constraint_by_name", message)
            self.assertEqual(caught[0].filename, __file__)
        self.assertEqual(str(prob.constraints()[0]), "x <= 2")

    def test_building_expressions_does_not_warn(self):
        prob = LpProblem("quiet", const.LpMinimize)
        x = prob.add_variable("x", 0, 5)
        y = prob.add_variable("y", 0, 5)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            obj = x + y
            obj += 2 * x
            obj[y] = 3
            obj.constant = 1
            prob += obj
            c = x + y <= 2
            c = (x <= 2) + y
            c = -(x >= 1)
            c = c.copy() - 1
            c = 2 <= x
            prob += x + y == 1, "eq"
            prob += c, "c"
            str(c)
            repr(c)
            c.asCplexLpAffineExpression("c", override_constant=3)
            prob.writeLP(os.devnull)

    def test_duals_survive_edits(self):
        prob = _row_wise()
        prob.variables()[0].varValue = 1.0
        c1 = prob.constraints()[0]
        c1.pi, c1.slack = 0.5, 0.25
        c1[prob.variables()[2]] = 2
        c1.changeRHS(2)
        c1 += 1
        self.assertEqual((c1.pi, c1.slack), (0.5, 0.25))

    @staticmethod
    def _lp_text(prob: LpProblem) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "model.lp")
            prob.writeLP(path)
            with open(path) as f:
                return f.read()


class ColumnWiseSolveTest(unittest.TestCase):
    def setUp(self):
        self.solver = _lp_solver()
        if self.solver is None:
            self.skipTest("no LP solver available")

    def test_grown_problem_solves_like_the_row_wise_one(self):
        results = []
        for prob in (_row_wise(), _column_wise()):
            stats = prob.solve(self.solver)
            self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
            results.append(
                (
                    pulp.value(prob.objective),
                    {v.name: v.varValue for v in prob.variables()},
                    {c.name: c.pi for c in prob.constraints()},
                )
            )
        self.assertEqual(results[0], results[1])

    def test_removed_variable_is_left_out_of_the_solve(self):
        """Only y covers both c1 and c2 within c3; without it the problem is
        infeasible."""
        prob = _row_wise()
        _, y, _ = prob.variables()
        self.assertAlmostEqual(prob.solve(self.solver).objective or 0.0, 2.0)
        prob.remove_variables([y])
        stats = prob.solve(self.solver)
        self.assertEqual(stats.status, const.LpSolveStatus.Infeasible)

    def test_edited_constraint_changes_the_solution(self):
        """Dropping y from c2 and relaxing c3 makes z (cost 3) and x feasible."""
        prob = _row_wise()
        _, y, _ = prob.variables()
        self.assertAlmostEqual(prob.solve(self.solver).objective or 0.0, 2.0)
        c2 = prob.get_constraint_by_name("c2")
        c3 = prob.get_constraint_by_name("c3")
        assert c2 is not None and c3 is not None
        del c2[y]
        c3.changeRHS(2)
        self.assertAlmostEqual(prob.solve(self.solver).objective or 0.0, 4.0)


if __name__ == "__main__":
    unittest.main()
