"""Unit tests for highs solver."""

from typing import ClassVar

import pulp.apis as solvers
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
