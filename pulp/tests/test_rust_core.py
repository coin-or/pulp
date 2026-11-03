import unittest

from pulp import LpProblem, _rustcore, const


class RustCoreSmokeTest(unittest.TestCase):
    def test_to_rust_model_available(self):
        prob = LpProblem("rust_smoke", const.LpMinimize)
        x = prob.add_variable("x", 0, 10)
        y = prob.add_variable("y", 0, 5)
        prob += x + y
        prob += x + 2 * y <= 7, "c1"

        self.assertTrue(hasattr(prob, "toRustModel"))

        model = prob.toRustModel()

        self.assertEqual(model.num_variables, 2)
        self.assertEqual(model.num_constraints, 1)
        summary = model.summary()
        self.assertIn("vars=2", summary)
        self.assertIn("constraints=1", summary)


def _tracked() -> LpProblem:
    """min x + y  s.t.  c: x + y >= 1, d: x <= 1, with its edits tracked."""
    prob = LpProblem("tracked", const.LpMinimize)
    x = prob.add_variable("x", 0, 1)
    y = prob.add_variable("y", 0, 1)
    prob += x + y
    prob += x + y >= 1, "c"
    prob += x <= 1, "d"
    prob._model.track_changes()
    return prob


class ChangeTrackingTest(unittest.TestCase):
    """``Model.track_changes`` / ``take_changes``: what a solver replays on resolve."""

    def test_off_by_default(self):
        prob = LpProblem("untracked", const.LpMinimize)
        prob.add_variable("x", 0, 1)
        self.assertFalse(prob._model.tracking_changes)
        with self.assertRaises(RuntimeError):
            prob._model.take_changes()

    def test_nothing_changed(self):
        prob = _tracked()
        self.assertTrue(prob._model.take_changes().is_empty())

    def test_new_columns_and_rows(self):
        prob = _tracked()
        c, d = prob.constraints()
        z = prob.add_column("z", 0, 1, obj=2, coefficients={c: 3})
        prob += z <= 1, "e"
        changes = prob._model.take_changes()
        self.assertEqual(changes.new_cols, [z.id])
        self.assertEqual(changes.new_rows, [2])
        # z's entry in an existing row; its entry in the new row "e" comes with the row
        self.assertEqual(changes.coeffs, [(c.id, z.id)])
        # the cost of a new column is read with the column
        self.assertEqual(changes.obj_coeffs, [])
        self.assertFalse(changes.objective_replaced)

    def test_edits_on_existing_rows_and_columns(self):
        prob = _tracked()
        x, y = prob.variables()
        c, d = prob.constraints()
        c.set_coefficient(x, 5)
        c.set_coefficient(x, 6)  # the same entry, recorded once
        d.changeRHS(2)
        c.sense = const.LpConstraintLE
        y.upBound = 3
        x.cat = const.LpInteger
        changes = prob._model.take_changes()
        self.assertEqual(changes.coeffs, [(c.id, x.id)])
        self.assertEqual(changes.row_bounds, [c.id, d.id])
        self.assertEqual(changes.var_bounds, [y.id])
        self.assertEqual(changes.var_category, [x.id])
        self.assertEqual(prob._model.coefficients_at(changes.coeffs), [6.0])

    def test_take_changes_starts_over(self):
        prob = _tracked()
        c = prob.constraints()[0]
        z = prob.add_column("z", 0, 1, coefficients={c: 1})
        prob._model.take_changes()
        # z is now an existing column: editing it is recorded
        z.upBound = 4
        prob._model.set_sense(_rustcore.ObjSense.Maximize)
        changes = prob._model.take_changes()
        self.assertEqual(changes.new_cols, [])
        self.assertEqual(changes.var_bounds, [z.id])
        self.assertTrue(changes.sense_changed)

    def test_edits_of_new_rows_are_not_recorded(self):
        prob = _tracked()
        x, _ = prob.variables()
        e = prob.addConstraint(x >= 0, "e")
        e.set_coefficient(x, 2)
        e.changeRHS(1)
        changes = prob._model.take_changes()
        self.assertEqual(changes.new_rows, [e.id])
        self.assertEqual(changes.coeffs, [])
        self.assertEqual(changes.row_bounds, [])

    def test_remove_variables_records_zeroed_entries(self):
        prob = _tracked()
        x, y = prob.variables()
        prob.remove_variables([y])
        changes = prob._model.take_changes()
        self.assertEqual(changes.coeffs, [(0, y.id)])
        self.assertEqual(changes.obj_coeffs, [y.id])
        self.assertEqual(prob._model.coefficients_at(changes.coeffs), [0.0])
        self.assertEqual(prob._model.objective_coefficients([x.id, y.id]), [1.0, 0.0])

    def test_objective_replaced(self):
        prob = _tracked()
        x, y = prob.variables()
        prob.objective = 2 * x
        self.assertTrue(prob._model.take_changes().objective_replaced)

    def test_sos_edits_are_unsupported(self):
        prob = _tracked()
        x, y = prob.variables()
        prob.add_sos_group(_rustcore.SosKind.Sos1, "s", {x: 1, y: 2})
        self.assertTrue(prob._model.take_changes().unsupported)

    def test_copy_does_not_track(self):
        prob = _tracked()
        copy = prob.copy()
        self.assertFalse(copy._model.tracking_changes)
        copy.add_variable("w", 0, 1)
        self.assertEqual(prob._model.take_changes().new_cols, [])

    def test_stop_tracking(self):
        prob = _tracked()
        prob._model.stop_tracking()
        self.assertFalse(prob._model.tracking_changes)


if __name__ == "__main__":
    unittest.main()
