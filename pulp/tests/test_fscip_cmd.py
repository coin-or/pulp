"""Unit tests for fscip_cmd solver."""

import os
import tempfile
import unittest
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class FSCIPLogTest(unittest.TestCase):
    def test_merge_rank_logs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_prefix = os.path.join(tmp_dir, "fscip.log.")
            log_path = os.path.join(tmp_dir, "fscip.log")

            with open(log_path, "wb") as log_file:
                log_file.write(b"existing\n")
            for rank, content in [
                (10, b"rank 10\n"),
                (0, b"rank 0\n"),
                (2, b"rank 2\n"),
            ]:
                with open(f"{log_prefix}{rank}", "wb") as rank_log:
                    rank_log.write(content)

            solvers.FSCIP_CMD._merge_log_files(log_prefix, log_path)

            with open(log_path, "rb") as log_file:
                self.assertEqual(
                    log_file.read(),
                    b"existing\nrank 0\nrank 2\nrank 10\n",
                )
            for rank in (0, 2, 10):
                self.assertFalse(os.path.exists(f"{log_prefix}{rank}"))


class FSCIP_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.FSCIP_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible_2": PulpTestConfig(okstatus=_status("LpStatusNotSolved")),
        "test_infeasible_problem__is_not_valid": PulpTestConfig(
            okstatus=_status(
                "LpStatusNotSolved", "LpStatusInfeasible", "LpStatusUndefined"
            )
        ),
        "test_integer_infeasible": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved")
        ),
        "test_integer_infeasible_2": PulpTestConfig(
            okstatus=_status("LpStatusNotSolved", "LpStatusUndefined")
        ),
        "test_invalid_var_names": PulpTestConfig(skip=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
        "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=False),
        "test_unbounded": PulpTestConfig(
            skip=True,
            skip_reason="FSCIP_CMD unbounded handling is inconsistent",
        ),
    }

    def test_relaxed_mip(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0, None, const.LpInteger)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7.5, "c3"
        self.solver.mip = False
        self._apply_pulp_check(prob, sol={x: 3.0, y: -0.5, z: 7})
