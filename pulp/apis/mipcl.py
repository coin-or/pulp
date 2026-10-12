# PuLP : Python LP Modeler
# Version 1.4.2

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id:solvers.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

from __future__ import annotations

import os
import subprocess
import warnings
from typing import TYPE_CHECKING, Any

from .. import constants
from .core import LpSolver_CMD, PulpSolverError, clocks

if TYPE_CHECKING:
    from ..core.lp_problem import LpProblem
    from ..core.lp_stats import LpSolveStats


class MIPCL_CMD(LpSolver_CMD):
    """The MIPCL_CMD solver"""

    name = "MIPCL_CMD"

    def __init__(
        self,
        path: str | None = None,
        keepFiles: bool = False,
        mip: bool = True,
        msg: bool = True,
        options: list[str] | None = None,
        timeLimit: float | None = None,
    ) -> None:
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param list options: list of additional options to pass to solver
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary
        """
        LpSolver_CMD.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            path=path,
            keepFiles=keepFiles,
        )

    def defaultPath(self) -> str:
        return self.executableExtension("mps_mipcl")

    def available(self) -> bool:
        """True if the solver is available"""
        return self.executable(self.path) is not None

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """Solve a well formulated lp problem."""
        start = clocks()
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpMps, tmpSol = self.create_tmp_files(lp.name, "mps", "sol")
        if lp.sense == constants.LpMaximize:
            # we swap the objectives
            # because it does not handle maximization.
            if lp.objective is None:
                raise PulpSolverError("MIPCL_CMD: no objective set")
            warnings.warn(
                "MIPCL_CMD does not allow maximization, "
                "we will minimize the inverse of the objective function."
            )
            lp += -lp.objective
        lp.checkDuplicateVars()
        lp.checkDuplicateConstraints()
        lp.checkLengthVars(52)
        lp.writeMPS(tmpMps, mpsSense=lp.sense)

        # just to report duplicated variables:
        try:
            os.remove(tmpSol)
        except Exception:
            pass
        cmd = self.path
        cmd += f" {tmpMps}"
        cmd += f" -solfile {tmpSol}"
        if self.timeLimit is not None:
            cmd += f" -time {self.timeLimit}"
        for option in self.options:
            cmd += " " + option
        if lp.isMIP():
            if not self.mip:
                warnings.warn("MIPCL_CMD cannot solve the relaxation of a problem")
        if self.msg:
            pipe = None
        else:
            pipe = open(os.devnull, "w")

        return_code = subprocess.call(cmd.split(), stdout=pipe, stderr=pipe)
        # We need to undo the objective swap before finishing
        if lp.sense == constants.LpMaximize and lp.objective is not None:
            lp += -lp.objective
        if return_code != 0:
            raise PulpSolverError("PuLP: Error while trying to execute " + self.path)
        if not os.path.exists(tmpSol):
            status = constants.LpSolveStatus.NotSolved
            has_solution = False
            values = None
        else:
            status, values, has_solution = self.readsol(tmpSol)
        self.delete_tmp_files(tmpMps, tmpSol)
        if values is not None and has_solution:
            lp.assignVarsVals(values)

        return self.buildStats(lp, status, has_solution, start=start)

    @staticmethod
    def readsol(
        filename: str,
    ) -> tuple[constants.LpSolveStatus, dict[str, float], bool]:
        """Read a MIPCL solution file.

        Returns why MIPCL stopped, the variable values and whether it has a solution.
        """
        S = constants.LpSolveStatus
        with open(filename) as f:
            content = f.readlines()
        content = [line.strip() for line in content]
        values = {}
        if not len(content):
            return S.NotSolved, values, False
        first_line = content[0]
        if first_line == "=infeas=":
            return S.Infeasible, values, False
        objective, value = first_line.split()
        # this is a workaround.
        # Not sure if it always returns this limit when unbounded.
        if abs(float(value)) >= 9.999999995e10:
            return S.Unbounded, values, False
        for line in content[1:]:
            name, value = line.split()
            values[name] = float(value)
        # MIPCL's solution file does not say whether the solution is optimal
        return S.Stopped, values, True
