"""``LpProblem.resolve``: solvers that hold the model in memory update it with
the edits made since the last solve instead of building it again, and restart
from the previous basis (column generation, cutting planes, branching)."""

import itertools
import unittest
from typing import Any

import pulp
from pulp import LpProblem, _rustcore, const


def _base() -> LpProblem:
    """min 2x + 3y + 4w  s.t.  c1: x + y + w >= 4,  c2: x - y <= 1,  c3: y + 2w >= 3.

    Optimum x = 2, y = w = 1 (objective 11)."""
    prob = LpProblem("base", const.LpMinimize)
    x = prob.add_variable("x", 0, 10)
    y = prob.add_variable("y", 0, 10)
    w = prob.add_variable("w", 0, 10)
    prob += 2 * x + 3 * y + 4 * w
    prob += x + y + w >= 4, "c1"
    prob += x - y <= 1, "c2"
    prob += y + 2 * w >= 3, "c3"
    return prob


def _num(value: float | None) -> float:
    """``value``, which the solve must have set."""
    assert value is not None
    return value


def _best_pattern(widths, duals, roll):
    """The pattern (count of each width in one roll) with the largest dual value."""
    ranges = [range(roll // width + 1) for width in widths]
    best, best_value = None, 0.0
    for counts in itertools.product(*ranges):
        if sum(c * w for c, w in zip(counts, widths)) <= roll:
            value = sum(c * d for c, d in zip(counts, duals))
            if value > best_value:
                best, best_value = counts, value
    return best, best_value


class ResolveTests:
    """Wrapper so that unittest does not collect the abstract base class."""

    class Base(unittest.TestCase):
        solver_name: str
        presolve_off: dict[str, Any]
        # edits that this solver replays by building the model again
        rebuilds_coefficient_edits = False
        rebuilds_mip = False

        def setUp(self):
            self.solver = self.make_solver()
            if not self.solver.available():
                self.skipTest(f"{self.solver_name} not available")

        def make_solver(self, presolve: bool = True) -> pulp.LpSolver:
            options = {} if presolve else self.presolve_off
            return pulp.getSolver(self.solver_name, msg=False, **options)

        def iterations(self, prob: LpProblem) -> float:
            """Simplex iterations of the last solve of ``prob.solverModel``."""
            raise NotImplementedError

        def assert_matches_cold(self, prob: LpProblem) -> None:
            """``prob``, just resolved, is optimal: feasible, with the objective
            value of a solve from scratch and, for an LP, duals and reduced
            costs that prove it (see :meth:`assert_dual_certificate`)."""
            cold = prob.copy()
            stats = cold.solve(self.make_solver())
            self.assertIs(stats.status, const.LpSolveStatus.Optimal)
            assert prob.objective is not None and cold.objective is not None
            self.assertAlmostEqual(
                _num(prob.objective.value()), _num(cold.objective.value())
            )
            self.assertTrue(prob.valid(1e-7))
            if not prob.isMIP():
                self.assert_dual_certificate(prob)

        def assert_dual_certificate(self, prob: LpProblem, eps: float = 1e-7) -> None:
            """The duals and reduced costs of ``prob`` prove its solution optimal.

            A degenerate LP has several optimal bases and dual solutions, and a
            resolve from the old basis need not end at the one a cold solve
            finds, so they are checked on their own rather than compared:
            ``dj = c - A'pi``, the signs fit the senses and bounds, and a row
            that is not tight has no dual (complementary slackness).
            """
            sign = 1 if prob.sense == const.LpMinimize else -1
            assert prob.objective is not None
            cost = {v.id: a for v, a in prob.objective.items()}
            priced = dict.fromkeys(cost, 0.0)
            for c in prob.constraints():
                # activity - rhs, from the values: solvers disagree on slacks
                pi, gap = c.pi, c.value()
                assert pi is not None and gap is not None, c.name
                if c.sense == const.LpConstraintGE:
                    self.assertGreaterEqual(sign * pi, -eps, c.name)
                elif c.sense == const.LpConstraintLE:
                    self.assertLessEqual(sign * pi, eps, c.name)
                if abs(gap) > 1e-6:
                    self.assertAlmostEqual(pi, 0, msg=c.name)
                for v, a in c.items():
                    priced[v.id] = priced.get(v.id, 0.0) + pi * a
            for v in prob.variables():
                if v.id not in priced:
                    continue  # in no row and not in the objective
                dj, value = v.dj, v.varValue
                assert dj is not None and value is not None, v.name
                self.assertAlmostEqual(
                    dj, cost.get(v.id, 0.0) - priced[v.id], msg=v.name
                )
                if value > v.lowBound + eps:
                    self.assertLessEqual(sign * dj, eps, v.name)
                if value < v.upBound - eps:
                    self.assertGreaterEqual(sign * dj, -eps, v.name)

        def solve_then_resolve(self, prob: LpProblem, edit, in_place=True) -> None:
            """Solve ``prob``, ``edit`` it, resolve it and check the result.

            :param in_place: the solver must update its model rather than
                build it again
            """
            prob.solve(self.solver)
            model = prob.solverModel
            edit(prob)
            stats = prob.resolve()
            self.assertIs(stats.status, const.LpSolveStatus.Optimal)
            if in_place:
                self.assertIs(prob.solverModel, model, "the model was built again")
            self.assert_matches_cold(prob)

        # hot start

        def test_resolve_without_changes_is_free(self):
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            stats = prob.resolve()
            self.assertIs(stats.status, const.LpSolveStatus.Optimal)
            self.assertIs(prob.solverModel, model)
            self.assertEqual(self.iterations(prob), 0)
            self.assert_matches_cold(prob)

        def test_non_improving_column_needs_no_pivots(self):
            # without presolve a solve from scratch needs pivots; a resolve that
            # keeps the basis needs none, as the old optimum is still optimal
            self.solver = self.make_solver(presolve=False)
            prob = _base()
            prob.solve(self.solver)
            c1 = prob.constraints()[0]
            assert c1.pi is not None
            # reduced cost: (pi + 1) - pi = 1 > 0
            prob.add_column("v", 0, 10, obj=c1.pi + 1, coefficients={c1: 1})
            prob.resolve()
            self.assertEqual(self.iterations(prob), 0)
            cold = prob.copy()
            cold.solve(self.make_solver(presolve=False))
            self.assertGreater(self.iterations(cold), 0)
            self.assert_matches_cold(prob)

        def test_column_generation_cutting_stock(self):
            roll, widths, demands = 100, [45, 36, 31, 14], [97, 610, 395, 211]
            prob = LpProblem("cutting_stock", const.LpMinimize)
            rows = []
            patterns = []
            for i, (width, demand) in enumerate(zip(widths, demands)):
                # one pattern per width to start with: as many of it as fit
                x = prob.add_variable(f"p{i}", 0)
                rows.append(prob.addConstraint((roll // width) * x >= demand, f"d{i}"))
                patterns.append(x)
            prob += pulp.lpSum(patterns)
            prob.solve(self.solver)
            model = prob.solverModel
            for _ in range(50):
                duals = [c.pi for c in rows]
                counts, value = _best_pattern(widths, duals, roll)
                if value <= 1 + 1e-9:
                    break
                assert counts is not None
                prob.add_column(
                    f"p{len(patterns)}",
                    0,
                    obj=1,
                    coefficients={c: n for c, n in zip(rows, counts) if n},
                )
                patterns.append(prob.variables()[-1])
                stats = prob.resolve()
                self.assertIs(stats.status, const.LpSolveStatus.Optimal)
                self.assertIs(prob.solverModel, model)
                self.assert_matches_cold(prob)
            else:
                self.fail("column generation did not converge")
            assert prob.objective is not None
            self.assertAlmostEqual(_num(prob.objective.value()), 452.25)

        # each kind of edit

        def test_add_constraint(self):
            def edit(prob):
                x, y, _ = prob.variables()
                prob += x + y <= 3, "cut"

            self.solve_then_resolve(_base(), edit)

        def test_add_column(self):
            def edit(prob):
                c1, _, c3 = prob.constraints()
                prob.add_column("v", 0, 10, obj=2.5, coefficients={c1: 1, c3: 1})

            self.solve_then_resolve(_base(), edit)

        def test_unused_variable_becomes_used(self):
            # created before the first solve but not used by it: its column was
            # empty, and its value must still land on it
            prob = _base()
            unused = prob.add_variable("unused", 0, 10)
            prob.add_variable("after", 0, 10)

            def edit(prob):
                c1 = prob.constraints()[0]
                c1.set_coefficient(unused, 1)
                prob.objective = prob.objective + 1.5 * unused

            self.solve_then_resolve(
                prob, edit, in_place=not self.rebuilds_coefficient_edits
            )
            # the optimum is unique: w = 1.5 covers c3 and unused = 2.5 the rest of c1
            self.assertAlmostEqual(_num(unused.varValue), 2.5)

        def test_new_variable_in_new_constraint(self):
            def edit(prob):
                x = prob.variables()[0]
                s = prob.add_variable("s", 0, 1)
                prob += x - s >= 2, "lift"

            self.solve_then_resolve(_base(), edit)

        def test_coefficient_rhs_and_sense_edits(self):
            def edit(prob):
                x, y, w = prob.variables()
                c1, c2, c3 = prob.constraints()
                c1.set_coefficient(x, 2)
                c3.set_coefficient(w, 0)
                c3.set_coefficient(x, 1)
                c2.changeRHS(0.5)
                c2.sense = const.LpConstraintGE

            self.solve_then_resolve(
                _base(), edit, in_place=not self.rebuilds_coefficient_edits
            )

        def test_rhs_and_sense_edits(self):
            def edit(prob):
                c1, c2, c3 = prob.constraints()
                c1.changeRHS(5)
                c2.sense = const.LpConstraintGE
                c3.changeRHS(1)

            self.solve_then_resolve(_base(), edit)

        def test_replace_constraint_expression(self):
            def edit(prob):
                x, y, w = prob.variables()
                c3 = prob.constraints()[2]
                c3[x] = 1
                del c3[y]
                c3.constant = -5

            self.solve_then_resolve(
                _base(), edit, in_place=not self.rebuilds_coefficient_edits
            )

        def test_variable_bounds(self):
            def edit(prob):
                x, y, w = prob.variables()
                x.upBound = 0.5
                w.lowBound = 1

            self.solve_then_resolve(_base(), edit)

        def test_objective_replaced(self):
            def edit(prob):
                x, y, w = prob.variables()
                prob.objective = 3 * x + 2 * y + 4 * w + 7

            self.solve_then_resolve(_base(), edit)

        def test_objective_sense_flip(self):
            def edit(prob):
                x, y, w = prob.variables()
                prob.sense = const.LpMaximize
                prob.objective = -2 * x - 3 * y - 4 * w

            self.solve_then_resolve(_base(), edit)

        def test_remove_variables_then_put_back(self):
            prob = _base()
            x, y, w = prob.variables()
            self.solve_then_resolve(
                prob,
                lambda prob: prob.remove_variables([y]),
                in_place=not self.rebuilds_coefficient_edits,
            )
            self.assertEqual(prob.constraints()[0].items(), [(x, 1.0), (w, 1.0)])

            def put_back(prob):
                prob.constraints()[0].set_coefficient(y, 1)
                prob.objective = prob.objective + 3 * y

            put_back(prob)
            prob.resolve()
            self.assert_matches_cold(prob)

        def test_mip_branching(self):
            prob = LpProblem("mip", const.LpMaximize)
            x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
            y = prob.add_variable("y", 0, 10, cat=const.LpInteger)
            prob += 5 * x + 4 * y
            prob += 6 * x + 4 * y <= 24, "a"
            prob += x + 2 * y <= 6, "b"

            def branch(prob):
                x.upBound = 2
                prob += x + y <= 4.5, "cut"

            self.solve_then_resolve(prob, branch, in_place=not self.rebuilds_mip)
            self.assertEqual((x.varValue, y.varValue), (2, 2))

        def test_relax_then_restore_integrality(self):
            prob = LpProblem("relax", const.LpMaximize)
            x = prob.add_variable("x", 0, 10, cat=const.LpInteger)
            prob += x
            prob += 2 * x <= 5, "a"
            prob.solve(self.solver)
            self.assertEqual(x.varValue, 2)
            x.cat = const.LpContinuous
            prob.resolve()
            self.assertAlmostEqual(_num(x.varValue), 2.5)
            x.cat = const.LpInteger
            prob.resolve()
            self.assertAlmostEqual(_num(x.varValue), 2)

        def test_constant_objective(self):
            # solving adds a dummy column for a constant objective, and removes
            # it from the objective afterwards
            prob = LpProblem("feasibility", const.LpMinimize)
            x = prob.add_variable("x", 0, 10)
            prob += x >= 2, "c"
            prob.solve(self.solver)
            model = prob.solverModel
            prob += x <= 3, "d"
            stats = prob.resolve()
            self.assertIs(stats.status, const.LpSolveStatus.Optimal)
            self.assertIs(prob.solverModel, model)
            self.assertIsNone(prob.objective)
            assert x.varValue is not None
            self.assertTrue(2 - 1e-9 <= x.varValue <= 3 + 1e-9)

        # when the model is built again

        def test_resolve_before_first_solve(self):
            prob = _base()
            prob.setSolver(self.solver)
            stats = prob.resolve()
            self.assertIs(stats.status, const.LpSolveStatus.Optimal)
            self.assert_matches_cold(prob)

        def test_solve_rebuilds(self):
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            prob.solve(self.solver)
            self.assertIsNot(prob.solverModel, model)
            self.assert_matches_cold(prob)

        def test_copy_builds_its_own_model(self):
            prob = _base()
            prob.solve(self.solver)
            copy = prob.copy()
            copy.add_column("v", 0, 10, obj=1, coefficients={copy.constraints()[0]: 1})
            copy.resolve(self.make_solver())
            self.assertIsNot(copy.solverModel, prob.solverModel)
            self.assert_matches_cold(copy)
            # the original still resolves in place, without the copy's column
            model = prob.solverModel
            prob += prob.variables()[0] <= 1, "cut"
            prob.resolve(self.solver)
            self.assertIs(prob.solverModel, model)
            self.assert_matches_cold(prob)

        def test_sos_edit_rebuilds(self):
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            x, y, _ = prob.variables()
            prob.add_sos_group(_rustcore.SosKind.Sos1, "s", {x: 1, y: 2})
            prob.resolve()
            self.assertIsNot(prob.solverModel, model)

        def test_other_solver_rebuilds(self):
            prob = _base()
            prob.solve(self.solver)
            first = prob.solverModel
            other = self.make_solver()
            prob += prob.variables()[0] <= 1, "cut"
            prob.resolve(other)
            self.assertIsNot(prob.solverModel, first)
            self.assert_matches_cold(prob)
            # back to the first solver: it did not build the current model
            second = prob.solverModel
            prob += prob.variables()[1] <= 3, "cut2"
            prob.resolve(self.solver)
            self.assertIsNot(prob.solverModel, second)
            self.assert_matches_cold(prob)

        def test_set_solver_rebuilds(self):
            # another solver cannot update the model this one built
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            prob.setSolver(self.make_solver())
            prob.resolve()
            self.assertIsNot(prob.solverModel, model)
            self.assert_matches_cold(prob)

        def test_assigning_solver_rebuilds(self):
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            prob.solver = self.make_solver()
            prob.resolve()
            self.assertIsNot(prob.solverModel, model)
            self.assert_matches_cold(prob)

        def test_direct_solver_solve_then_resolve(self):
            # solved through the solver, not the problem: the problem still
            # learns which solver holds its model
            prob = _base()
            self.solver.solve(prob)
            self.assertIs(prob.solver, self.solver)
            model = prob.solverModel
            prob += prob.variables()[0] <= 1, "cut"
            prob.resolve()
            self.assertIs(prob.solverModel, model)
            self.assert_matches_cold(prob)

        def test_resolve_sets_solver(self):
            prob = _base()
            prob.solve(self.solver)
            other = self.make_solver()
            prob.resolve(other)
            self.assertIs(prob.solver, other)
            # a solver that always rebuilds is remembered too
            cmd = pulp.getSolver("COIN_CMD", msg=False)
            if cmd.available():
                prob.resolve(cmd)
                self.assertIs(prob.solver, cmd)

        def test_failed_update_rebuilds_next_time(self):
            prob = _base()
            prob.solve(self.solver)
            model = prob.solverModel
            solver: Any = self.solver

            def fail(*args):
                raise RuntimeError("update failed")

            solver.applyChanges = fail
            prob += prob.variables()[0] <= 1, "cut"
            with self.assertRaises(RuntimeError):
                prob.resolve()
            del solver.applyChanges
            prob.resolve()
            self.assertIsNot(prob.solverModel, model)
            self.assert_matches_cold(prob)


class HiGHSResolveTest(ResolveTests.Base):
    solver_name = "HiGHS"
    presolve_off = {"presolve": "off"}

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.getInfo().simplex_iteration_count


class GurobiResolveTest(ResolveTests.Base):
    solver_name = "GUROBI"
    presolve_off = {"Presolve": 0}

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.IterCount


class XpressResolveTest(ResolveTests.Base):
    solver_name = "XPRESS_PY"
    presolve_off = {"preSolve": 0}

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.attributes.simplexiter

    def test_sos_edit_rebuilds(self):
        # xpress.sos(), used to build SOS groups, takes other arguments since
        # Xpress 9.5: XPRESS_PY cannot solve a problem with SOS groups
        self.skipTest("XPRESS_PY cannot build SOS groups with this Xpress")


class CoptResolveTest(ResolveTests.Base):
    solver_name = "COPT"
    presolve_off = {"Presolve": 0}

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.getAttr("SimplexIter")


class GlpkResolveTest(ResolveTests.Base):
    solver_name = "PYGLPK"
    # GLPK's simplex runs without presolve unless asked for
    presolve_off: dict[str, Any] = {}

    def iterations(self, prob: LpProblem) -> float:
        import swiglpk

        return swiglpk.glp_get_it_cnt(prob.solverModel)


class CylpResolveTest(ResolveTests.Base):
    solver_name = "CyLP"
    presolve_off = {"presolve": False}
    # Clp cannot change an entry of its matrix, and MIPs are solved by Cbc
    rebuilds_coefficient_edits = True
    rebuilds_mip = True

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.iteration


class CplexResolveTest(ResolveTests.Base):
    solver_name = "CPLEX_PY"
    presolve_off = {"preprocessing.presolve": 0}

    def iterations(self, prob: LpProblem) -> float:
        assert prob.solverModel is not None
        return prob.solverModel.solution.progress.get_num_iterations()


if __name__ == "__main__":
    unittest.main()
