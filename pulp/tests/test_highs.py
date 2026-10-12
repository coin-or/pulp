"""Unit tests for highs solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp import LpMaximize, LpProblem, const
from pulp.tests.bin_packing_problem import create_bin_packing_problem
from pulp.tests.solver_common import (
    ALLOW_REPEATED_VAR_NAMES,
    BaseSolverTest,
    PulpTestConfig,
)


class HiGHS_PYTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.HiGHS
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_repeated_name": ALLOW_REPEATED_VAR_NAMES,
        "test_initial_value": PulpTestConfig(warm_start=True),
    }

    def test_model_arrays(self):
        # the model HiGHS holds, column by column and row by row: a maximisation is
        # negated, missing bounds are infinite and a zero coefficient is not an entry
        import highspy

        prob = LpProblem("arrays", LpMaximize)
        x = prob.add_variable("x", 0, 4, cat=const.LpInteger)
        y = prob.add_variable("y", None, None)
        prob += 3 * x - 2 * y + 1, "obj"
        prob += x + 0 * y <= 7, "c1"
        prob += 2 * x - y >= -3, "c2"
        prob += y == 5, "c3"
        solver = solvers.HiGHS(msg=False)
        prob.solverModel = highspy.Highs()
        solver.buildSolverModel(prob)
        lp = prob.solverModel.getLp()
        inf = highspy.kHighsInf

        self.assertEqual(lp.num_col_, 2)
        self.assertEqual(lp.num_row_, 3)
        self.assertEqual(list(lp.col_cost_), [-3, 2])
        self.assertEqual(list(lp.col_lower_), [0, -inf])
        self.assertEqual(list(lp.col_upper_), [4, inf])
        self.assertEqual(
            list(lp.integrality_),
            [highspy.HighsVarType.kInteger, highspy.HighsVarType.kContinuous],
        )
        self.assertEqual(list(lp.row_lower_), [-inf, -3, 5])
        self.assertEqual(list(lp.row_upper_), [7, inf, 5])
        self.assertEqual(list(lp.a_matrix_.start_), [0, 1, 3, 4])
        self.assertEqual(list(lp.a_matrix_.index_), [0, 0, 1, 1])
        self.assertEqual(list(lp.a_matrix_.value_), [1, 2, -1, 1])

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
                == solvers.HiGHS.hscb.HighsCallbackType.kCallbackMipInterrupt  # ty: ignore[unresolved-attribute]
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
                solvers.HiGHS.hscb.HighsCallbackType.kCallbackMipInterrupt  # ty: ignore[unresolved-attribute]
            ],
        )
        prob.solve(solver)
