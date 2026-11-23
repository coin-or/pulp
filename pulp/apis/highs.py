# PuLP : Python LP Modeler
# Version 2.4.1
from __future__ import annotations

import os
import subprocess
import warnings
from math import isfinite
from typing import TYPE_CHECKING, Any

from .. import _rustcore, constants
from .core import (
    LpSolver_API,
    LpSolver_CMD,
    PulpSolverError,
    _row_bounds,
    clocks,
    import_optional,
    requires,
)

if TYPE_CHECKING:
    import highspy as highspy_t

    from ..core.lp_problem import LpProblem
    from ..core.lp_stats import LpSolveStats

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

# Modified by Sam Mathew (@samiit on Github)
# Users would need to install HiGHS on their machine and provide the path to the executable. Please look at this thread: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-894852288
# More instructions on: https://www.highs.dev


class HiGHS_CMD(LpSolver_CMD):
    """The HiGHS_CMD solver"""

    name: str = "HiGHS_CMD"

    SOLUTION_STYLE: int = 0

    def __init__(
        self,
        path=None,
        keepFiles=False,
        mip=True,
        msg=True,
        options=None,
        timeLimit=None,
        gapRel=None,
        gapAbs=None,
        threads=None,
        logPath=None,
        warmStart=False,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param list[str] options: list of additional options to pass to solver
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary (you can get binaries for your platform from https://github.com/JuliaBinaryWrappers/HiGHS_jll.jl/releases, or else compile from source - https://highs.dev)
        :param int threads: sets the maximum number of threads
        :param str logPath: path to the log file
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        """
        LpSolver_CMD.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            gapRel=gapRel,
            gapAbs=gapAbs,
            options=options,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            logPath=logPath,
            warmStart=warmStart,
        )

    def defaultPath(self):
        return self.executableExtension("highs")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """Solve a well formulated lp problem."""
        start = clocks()
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        lp.checkDuplicateVars()
        lp.checkDuplicateConstraints()

        tmpMps, tmpSol, tmpOptions, tmpLog, tmpMst = self.create_tmp_files(
            lp.name, "mps", "sol", "HiGHS", "HiGHS_log", "mst"
        )
        lp.writeMPS(tmpMps, with_objsense=True)

        file_options: list[str] = []
        file_options.append(f"solution_file={tmpSol}")
        file_options.append("write_solution_to_file=true")
        file_options.append(f"write_solution_style={HiGHS_CMD.SOLUTION_STYLE}")
        if not self.msg:
            file_options.append("log_to_console=false")
        if "threads" in self.optionsDict:
            file_options.append(f"threads={self.optionsDict['threads']}")
        if "gapRel" in self.optionsDict:
            file_options.append(f"mip_rel_gap={self.optionsDict['gapRel']}")
        if "gapAbs" in self.optionsDict:
            file_options.append(f"mip_abs_gap={self.optionsDict['gapAbs']}")
        if "logPath" in self.optionsDict:
            highs_log_file = self.optionsDict["logPath"]
        else:
            highs_log_file = tmpLog
        file_options.append(f"log_file={highs_log_file}")

        command: list[str] = []
        command.append(self.path)
        command.append(tmpMps)
        command.append(f"--options_file={tmpOptions}")
        if self.timeLimit is not None:
            command.append(f"--time_limit={self.timeLimit}")
        if not self.mip:
            command.append("--solver=simplex")
        if "threads" in self.optionsDict:
            command.append("--parallel=on")
        if self.optionsDict.get("warmStart", False):
            self.writesol(tmpMst, lp)
            command.append(f"--read_solution_file={tmpMst}")

        options = iter(self.options)
        for option in options:
            # assumption: all cli and file options require an argument which is provided after the equal sign (=)
            if "=" not in option:
                option += f"={next(options)}"

            # identify cli options by a leading dash (-) and treat other options as file options
            if option.startswith("-"):
                command.append(option)
            else:
                file_options.append(option)

        with open(tmpOptions, "w") as options_file:
            options_file.write("\n".join(file_options))

        pipe = self.get_pipe()

        process = subprocess.Popen(command, stdout=pipe, stderr=pipe)

        # HiGHS return code semantics (see: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-946575028)
        # - -1: error
        # -  0: success
        # -  1: warning

        if process.wait() == -1:
            raise PulpSolverError(
                "Pulp: Error while executing HiGHS, use msg=True for more details"
                + self.path
            )
        if pipe is not None:
            pipe.close()
        with open(highs_log_file, "r") as log_file:
            lines = log_file.readlines()
        lines = [line.strip().split() for line in lines]

        # LP
        model_line = [line for line in lines if line[:2] == ["Model", "status"]]
        if len(model_line) > 0:
            model_status = " ".join(model_line[0][3:])  # Model status: ...
        else:
            # ILP
            model_line = [line for line in lines if "Status" in line][0]
            model_status = " ".join(model_line[1:])
        sol_line = [line for line in lines if line[:2] == ["Solution", "status"]]
        sol_line = sol_line[0] if len(sol_line) > 0 else ["Not solved"]
        sol_status = sol_line[-1]
        S = constants.LpSolveStatus
        model_statuses = {
            "optimal": S.Optimal,
            "infeasible": S.Infeasible,
            "unbounded": S.Unbounded,
            "primal infeasible or unbounded": S.Undefined,
            "bound on objective reached": S.GapLimit,
            "target for objective reached": S.GapLimit,
            "time limit reached": S.TimeLimit,
            "iteration limit reached": S.IterationLimit,
            "solution limit reached": S.SolutionLimit,
            "interrupted by user": S.Interrupted,
            "memory limit reached": S.MemoryLimit,
        }
        status = model_statuses.get(model_status.lower())
        has_solution = status == S.Optimal or sol_status.lower() == "feasible"
        if status is None:
            status = S.Stopped if has_solution else S.NotSolved

        if not os.path.exists(tmpSol) or os.stat(tmpSol).st_size == 0:
            has_solution = False
        values = self.readsol(tmpSol) if has_solution else None

        self.delete_tmp_files(tmpMps, tmpSol, tmpOptions, tmpLog, tmpMst)
        if values is not None:
            lp.assignVarsVals(values)

        return self.buildStats(lp, status, has_solution, start=start)

    def writesol(self, filename, lp):
        """Writes a HiGHS solution file"""

        variable_rows = []
        for var in lp.exported_variables():
            variable_rows.append(f"{var.name} {var.varValue or 0}")

        # Required preamble for HiGHS to accept a solution
        all_rows = [
            "Model status",
            "None",
            "",
            "# Primal solution values",
            "Feasible",
            "",
            f"# Columns {len(variable_rows)}",
        ]
        all_rows.extend(variable_rows)

        with open(filename, "w") as file:
            file.write("\n".join(all_rows))

    def readsol(self, filename):
        """Read a HiGHS solution file"""
        with open(filename) as file:
            lines = file.readlines()

        begin, end = None, None
        for index, line in enumerate(lines):
            if begin is None and line.startswith("# Columns"):
                begin = index + 1
            if end is None and line.startswith("# Rows"):
                end = index
        if begin is None or end is None:
            raise PulpSolverError("Cannot read HiGHS solver output")

        values = {}
        for line in lines[begin:end]:
            name, value = line.split()
            values[name] = float(value)
        return values


highspy_mod = import_optional("highspy")
np = import_optional("numpy")


def _check(status, what):
    # HiGHS rejects a whole batch on an error, e.g. a coefficient of at least
    # large_matrix_value, and would then solve the model without it
    if status == highspy_mod.HighsStatus.kError:
        raise PulpSolverError(
            f"HiGHS: cannot add the {what}, check for very large coefficients"
        )


class HiGHS(LpSolver_API):
    name = "HiGHS"

    hscb = highspy_mod.cb if highspy_mod is not None else None

    def __init__(
        self,
        mip=True,
        msg=True,
        callbackTuple=None,
        gapAbs=None,
        gapRel=None,
        threads=None,
        timeLimit=None,
        logPath=None,
        warmStart=False,
        callbacksToActivate: list[highspy_t.cb.HighsCallbackType] | None = None,
        **solverParams,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param tuple callbackTuple: Tuple of callback function and callbackValue (see tests for an example)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param str logPath: path to the log file
        :param float timeLimit: maximum time for solver (in seconds)
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param dict solverParams: list of named options to pass directly to the HiGHS solver
        :param callbacksToActivate: list of callback types to start
        """
        super().__init__(
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            logPath=logPath,
            warmStart=warmStart,
            **solverParams,
        )
        self.callbackTuple = callbackTuple
        self.callbacksToActivate = callbacksToActivate
        self.gapAbs = gapAbs
        self.gapRel = gapRel
        self.threads = threads

    def available(self):
        return highspy_mod is not None and np is not None

    def callSolver(self, lp, *, changes=None, **kwargs):
        lp.solverModel.run()

    def canUpdate(self, lp):
        return True

    def configureSolver(self, lp):
        """Apply the solver options to ``lp.solverModel``, again on every
        resolve so that options changed in between take effect."""
        solverModel = lp.solverModel
        logPath = self.optionsDict.get("logPath")
        if not self.msg:
            solverModel.setOptionValue("log_to_console", False)

        if self.gapRel is not None:
            solverModel.setOptionValue("mip_rel_gap", self.gapRel)

        if self.gapAbs is not None:
            solverModel.setOptionValue("mip_abs_gap", self.gapAbs)

        if self.threads is not None:
            solverModel.setOptionValue("threads", self.threads)

        if self.timeLimit is not None:
            solverModel.setOptionValue("time_limit", float(self.timeLimit))

        if logPath is not None:
            solverModel.setOptionValue("log_file", logPath)

        # set remaining parameter values
        for key, value in self.optionsDict.items():
            if key in ("warmStart", "logPath"):
                continue
            # highspy reports an unknown option or a bad value by its status
            # alone: raise, as other solvers' libraries do
            status = solverModel.setOptionValue(key, value)
            if status != highspy_mod.HighsStatus.kOk:
                raise PulpSolverError(f"HiGHS: cannot set option {key!r} to {value!r}")

    @requires("highspy", "numpy")
    def buildSolverModel(self, lp):
        lp.solverModel = highspy_mod.Highs()

        if self.callbackTuple:
            lp.solverModel.setCallback(*self.callbackTuple)

        if self.callbacksToActivate:
            for cb_type in self.callbacksToActivate:
                lp.solverModel.startCallback(cb_type)

        # configured first, so that msg=False also silences the model loading
        self.configureSolver(lp)

        inf = highspy_mod.kHighsInf

        # every variable is a column, used or not: column j is the variable with
        # id j (as row i is the constraint with id i), so a resolve only appends
        variables = lp.variables()

        # one addCols and one addRows call: per-column and per-row calls cost more
        # than the solve itself on models that resolve in a few milliseconds, and the
        # objective and constraint lookups are done once rather than once per column
        cost = np.zeros(len(variables))
        for var, coefficient in lp.objective.items():
            cost[var.id] = coefficient
        lower = np.array([var.lowBound for var in variables], dtype=np.float64)
        upper = np.array([var.upBound for var in variables], dtype=np.float64)

        empty = np.zeros(0, dtype=np.int32)
        _check(
            lp.solverModel.addCols(
                len(variables), cost, lower, upper, 0, empty, empty, np.zeros(0)
            ),
            "variables",
        )

        if self.mip:
            integer = np.fromiter(
                (var.id for var in variables if var.cat == constants.LpInteger),
                dtype=np.int32,
            )
            if len(integer):
                lp.solverModel.changeColsIntegrality(
                    len(integer),
                    integer,
                    np.full(len(integer), highspy_mod.HighsVarType.kInteger),
                )

        if lp.sense == constants.LpMaximize:
            lp.solverModel.changeObjectiveSense(highspy_mod.ObjSense.kMaximize)
        lp.solverModel.changeObjectiveOffset(lp.objective.constant)

        constraints = lp.constraints()
        starts: list[int] = []
        indices: list[int] = []
        coefficients: list[float] = []
        row_lower: list[float] = []
        row_upper: list[float] = []
        for constraint in constraints:
            starts.append(len(indices))
            for var, coefficient in constraint.items():
                if coefficient != 0:
                    indices.append(var.id)
                    coefficients.append(coefficient)
            lb = constraint.getLb()
            ub = constraint.getUb()
            row_lower.append(-inf if lb is None else lb)
            row_upper.append(inf if ub is None else ub)

        _check(
            lp.solverModel.addRows(
                len(constraints),
                np.array(row_lower, dtype=np.float64),
                np.array(row_upper, dtype=np.float64),
                len(indices),
                np.array(starts, dtype=np.int32),
                np.array(indices, dtype=np.int32),
                np.array(coefficients, dtype=np.float64),
            ),
            "constraints",
        )
        self._start_tracking(lp)
        if self.optionsDict.get("warmStart", False):
            indices: list[int] = []
            values: list[float] = []
            for var in variables:
                if var.varValue is not None:
                    indices.append(var.id)
                    values.append(var.varValue)
            if not indices:
                warnings.warn("No variable with value found: warmStart aborted")
                return
            lp.solverModel.setSolution(len(indices), indices, values)

    @requires("highspy", "numpy")
    def applyChanges(self, lp, changes):
        """Update ``lp.solverModel`` with the edits made to ``lp`` since it was
        last solved (``changes``, from :meth:`_take_changes`), keeping the basis.

        Columns are variable ids and rows constraint ids, so new variables and
        constraints are appended in id order.
        """
        h = lp.solverModel
        model = lp._model
        inf = highspy_mod.kHighsInf
        kInteger = highspy_mod.HighsVarType.kInteger
        kContinuous = highspy_mod.HighsVarType.kContinuous

        if changes.sense_changed:
            h.changeObjectiveSense(
                highspy_mod.ObjSense.kMaximize
                if lp.sense == constants.LpMaximize
                else highspy_mod.ObjSense.kMinimize
            )

        new_cols = changes.new_cols
        # entries of new columns in existing rows go with the columns, the others
        # are changed one by one
        old_entries, columns = self._split_coefficients(lp, changes, h.getNumCol())

        if new_cols:
            rvars = [model.get_variable(j) for j in new_cols]
            starts: list[int] = []
            indices: list[int] = []
            coefficients: list[float] = []
            for j in new_cols:
                starts.append(len(indices))
                rows, values = columns.get(j, ([], []))
                indices.extend(rows)
                coefficients.extend(values)
            _check(
                h.addCols(
                    len(new_cols),
                    np.array(model.objective_coefficients(new_cols), dtype=np.float64),
                    np.array([v.lb for v in rvars], dtype=np.float64),
                    np.array([v.ub for v in rvars], dtype=np.float64),
                    len(indices),
                    np.array(starts, dtype=np.int32),
                    np.array(indices, dtype=np.int32),
                    np.array(coefficients, dtype=np.float64),
                ),
                "variables",
            )
            if self.mip:
                integer = np.array(
                    [v.id() for v in rvars if v.category == _rustcore.Category.Integer],
                    dtype=np.int32,
                )
                if len(integer):
                    h.changeColsIntegrality(
                        len(integer), integer, np.full(len(integer), kInteger)
                    )

        if changes.new_rows:
            starts = []
            indices = []
            coefficients = []
            row_lower: list[float] = []
            row_upper: list[float] = []
            for i in changes.new_rows:
                rconstr = model.get_constraint(i)
                starts.append(len(indices))
                for rvar, coefficient in rconstr.items():
                    if coefficient != 0:
                        indices.append(rvar.id())
                        coefficients.append(coefficient)
                lb, ub = _row_bounds(rconstr, inf)
                row_lower.append(lb)
                row_upper.append(ub)
            _check(
                h.addRows(
                    len(changes.new_rows),
                    np.array(row_lower, dtype=np.float64),
                    np.array(row_upper, dtype=np.float64),
                    len(indices),
                    np.array(starts, dtype=np.int32),
                    np.array(indices, dtype=np.int32),
                    np.array(coefficients, dtype=np.float64),
                ),
                "constraints",
            )

        for i, j, value in old_entries:
            _check(h.changeCoeff(i, j, value), "constraints")

        if changes.row_bounds:
            bounds = [
                _row_bounds(model.get_constraint(i), inf) for i in changes.row_bounds
            ]
            h.changeRowsBounds(
                len(bounds),
                np.array(changes.row_bounds, dtype=np.int32),
                np.array([lb for lb, _ in bounds], dtype=np.float64),
                np.array([ub for _, ub in bounds], dtype=np.float64),
            )

        if changes.var_bounds:
            rvars = [model.get_variable(j) for j in changes.var_bounds]
            h.changeColsBounds(
                len(rvars),
                np.array(changes.var_bounds, dtype=np.int32),
                np.array([v.lb for v in rvars], dtype=np.float64),
                np.array([v.ub for v in rvars], dtype=np.float64),
            )

        if changes.var_category and self.mip:
            rvars = [model.get_variable(j) for j in changes.var_category]
            h.changeColsIntegrality(
                len(rvars),
                np.array(changes.var_category, dtype=np.int32),
                np.array(
                    [
                        kInteger
                        if v.category == _rustcore.Category.Integer
                        else kContinuous
                        for v in rvars
                    ]
                ),
            )

        if changes.objective_replaced:
            cols = list(range(h.getNumCol()))
            objective = lp.objective
            h.changeObjectiveOffset(0.0 if objective is None else objective.constant)
        else:
            cols = changes.obj_coeffs
        if cols:
            h.changeColsCost(
                len(cols),
                np.array(cols, dtype=np.int32),
                np.array(model.objective_coefficients(cols), dtype=np.float64),
            )

    def findSolutionValues(self, lp, result=None):
        status = lp.solverModel.getModelStatus()
        obj_value = lp.solverModel.getObjectiveValue()
        solution = lp.solverModel.getSolution()
        HighsModelStatus = highspy_mod.HighsModelStatus

        S = constants.LpSolveStatus
        status_dict = {
            HighsModelStatus.kNotset: S.NotSolved,
            HighsModelStatus.kLoadError: S.Undefined,
            HighsModelStatus.kModelError: S.Undefined,
            HighsModelStatus.kPresolveError: S.Undefined,
            HighsModelStatus.kSolveError: S.Undefined,
            HighsModelStatus.kPostsolveError: S.Undefined,
            HighsModelStatus.kModelEmpty: S.NotSolved,
            HighsModelStatus.kOptimal: S.Optimal,
            HighsModelStatus.kInfeasible: S.Infeasible,
            HighsModelStatus.kUnboundedOrInfeasible: S.Undefined,
            HighsModelStatus.kUnbounded: S.Unbounded,
            HighsModelStatus.kObjectiveBound: S.GapLimit,
            HighsModelStatus.kObjectiveTarget: S.GapLimit,
            HighsModelStatus.kInterrupt: S.Interrupted,
            HighsModelStatus.kTimeLimit: S.TimeLimit,
            HighsModelStatus.kIterationLimit: S.IterationLimit,
            HighsModelStatus.kSolutionLimit: S.SolutionLimit,
            HighsModelStatus.kMemoryLimit: S.MemoryLimit,
            HighsModelStatus.kUnknown: S.Undefined,
        }
        stopped_early = (
            HighsModelStatus.kObjectiveBound,
            HighsModelStatus.kObjectiveTarget,
            HighsModelStatus.kInterrupt,
            HighsModelStatus.kTimeLimit,
            HighsModelStatus.kIterationLimit,
            HighsModelStatus.kSolutionLimit,
            HighsModelStatus.kMemoryLimit,
        )

        # column j is the variable with id j
        lp._model.set_variable_values(list(enumerate(solution.col_value)))
        lp._model.set_variable_djs(list(enumerate(solution.col_dual)))

        row_values = list(solution.row_value)
        row_duals = list(solution.row_dual)
        for constraint in lp.constraints():
            # PuLP returns LpConstraint.constant as if it were on the
            # left-hand side, which means the signs on the following line
            # are correct
            # We need to flip the sign for slacks for LE constraints
            row_idx = constraint.id
            constraint.slack = constraint.constant + row_values[row_idx]
            if constraint.sense == constants.LpConstraintLE:
                constraint.slack *= -1.0
            constraint.pi = row_duals[row_idx]

        # a solver that stopped early without an incumbent reports an infinite objective
        has_solution = status == HighsModelStatus.kOptimal or (
            status in stopped_early and isfinite(obj_value)
        )
        return status_dict.get(status, S.Undefined), has_solution

    def findBestBound(self, lp: LpProblem) -> float | None:
        """The best bound HiGHS proved on a MIP, in the problem's sense, or None."""
        if not (lp.isMIP() and self.mip):
            return None
        bound = lp.solverModel.getInfo().mip_dual_bound
        return bound if isfinite(bound) else None
