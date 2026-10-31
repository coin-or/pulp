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

import math
import os
from typing import TYPE_CHECKING, Any

from .. import _rustcore, constants
from .core import (
    LpSolver,
    LpSolver_CMD,
    PulpSolverError,
    clock,
    clocks,
    import_optional,
    log,
    operating_system,
    requires,
    subprocess,
)

if TYPE_CHECKING:
    from ..core.lp_problem import LpProblem
    from ..core.lp_stats import LpSolveStats

glpk_path = "glpsol"


class GLPK_CMD(LpSolver_CMD):
    """The GLPK LP solver"""

    name = "GLPK_CMD"

    def __init__(
        self,
        path=None,
        keepFiles=False,
        mip=True,
        msg=True,
        options=None,
        timeLimit=None,
    ):
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

    def defaultPath(self):
        return self.executableExtension(glpk_path)

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """Solve a well formulated lp problem."""
        start = clocks()
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)

        # GLPK cannot handle empty problems:
        if not lp.numConstraints():
            return self.buildStats(
                lp, constants.LpSolveStatus.NotSolved, False, start=start
            )

        tmpLp, tmpOut, tmpSol = self.create_tmp_files(lp.name, "lp", "out", "sol")
        lp.writeLP(tmpLp, writeSOS=0)

        proc = ["glpsol", "--cpxlp", tmpLp, "-o", tmpOut, "-w", tmpSol]
        if self.timeLimit:
            proc.extend(["--tmlim", str(self.timeLimit)])
        if not self.mip:
            proc.append("--nomip")
        proc.extend(self.options)

        self.solution_time = clock()
        if not self.msg:
            proc[0] = self.path
            pipe = open(os.devnull, "w")
            if operating_system == "win":
                # Prevent flashing windows if used from a GUI application
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                rc = subprocess.call(
                    proc, stdout=pipe, stderr=pipe, startupinfo=startupinfo
                )
            else:
                rc = subprocess.call(proc, stdout=pipe, stderr=pipe)
            if rc:
                raise PulpSolverError(
                    "PuLP: Error while trying to execute " + self.path
                )
            pipe.close()
        else:
            if os.name != "nt":
                rc = os.spawnvp(os.P_WAIT, self.path, proc)
            else:
                exe = self.executable(self.path)
                if exe is None:
                    raise PulpSolverError(
                        "PuLP: Could not find executable for " + self.path
                    )
                rc = os.spawnv(os.P_WAIT, exe, proc)
            if rc == 127:
                raise PulpSolverError(
                    "PuLP: Error while trying to execute " + self.path
                )
        self.solution_time += clock()

        if not os.path.exists(tmpSol):
            raise PulpSolverError("PuLP: Error while executing " + self.path)

        status, values = self.readsol(tmpOut, tmpSol)

        vars = dict([(var.name, var) for var in lp.variables()])
        for name, value in values.items():
            if name not in vars:  # __dummy
                continue
            var = vars[name]
            if var.cat == constants.LpInteger and self.mip:
                values[name] = int(value)
            else:
                values[name] = float(value)

        lp.assignVarsVals(values)
        self.delete_tmp_files(tmpLp, tmpSol)
        has_solution = status in (
            constants.LpSolveStatus.Optimal,
            constants.LpSolveStatus.Stopped,
        )
        return self.buildStats(lp, status, has_solution, start=start)

    def readsol(self, outFile, solFile):
        """Read GLPK solution files"""

        # first determine status and column names
        with open(outFile) as f:
            f.readline()
            rows = int(f.readline().split()[1])
            cols = int(f.readline().split()[1])
            f.readline()
            statusString = f.readline()[12:-1]
            S = constants.LpSolveStatus
            glpkStatus = {
                "INTEGER OPTIMAL": S.Optimal,
                # a gap or time limit stopped the search; GLPK does not say which
                "INTEGER NON-OPTIMAL": S.Stopped,
                "OPTIMAL": S.Optimal,
                "INFEASIBLE (FINAL)": S.Infeasible,
                "INTEGER UNDEFINED": S.Undefined,
                "UNBOUNDED": S.Unbounded,
                "UNDEFINED": S.Undefined,
                "INTEGER EMPTY": S.Infeasible,
            }
            if statusString not in glpkStatus:
                raise PulpSolverError("Unknown status returned by GLPK")
            status = glpkStatus[statusString]
            names = []
            for i in range(4):
                f.readline()
            for i in range(rows):
                line = f.readline().split()
                if len(line) == 2:
                    f.readline()
            for i in range(3):
                f.readline()
            for i in range(cols):
                line = f.readline().split()
                name = line[1]
                if len(line) == 2:
                    f.readline()
                names.append(name)

        # now actually read column values
        with open(solFile) as f:
            values = []
            status2 = S.Undefined
            vpos = 2

            while True:
                ln = f.readline()
                elems = ln.split()
                if elems[0] == "c":
                    continue
                if elems[0] == "e":
                    break
                if elems[0] == "j":
                    values.append(elems[vpos])
                if elems[0] == "s":
                    # on "bas"/"ipt" lines this is the primal status, which is
                    # "f" (feasible) for an optimal LP as well
                    status2 = {
                        "o": S.Optimal,
                        "f": S.Stopped if elems[1] == "mip" else S.Optimal,
                        "n": S.Infeasible,
                        "u": S.Undefined,
                    }[elems[4]]
                    vpos = {"mip": 2, "bas": 3, "ipt": 2}[elems[1]]

            values = dict(zip(names, values))

            assert status == status2

            return status, values


GLPK = GLPK_CMD

swiglpk_mod = import_optional("swiglpk")


class PYGLPK(LpSolver):
    """
    The glpk LP/MIP solver (via its python interface)

    Copyright Christophe-Marie Duquesne 2012

    After calling solve, the model is in prob.solverModel. GLPK indices are
    1-based: column ``j + 1`` is the variable with id ``j`` and row ``i + 1``
    the constraint with id ``i``.
    """

    name = "PYGLPK"

    def __init__(self, mip=True, msg=True, timeLimit=None, gapRel=None, **solverParams):
        """
        Initializes the glpk solver.

        @param mip: if False the solver will solve a MIP as an LP
        @param msg: displays information from the solver to stdout
        @param timeLimit: not handled
        @param gapRel: not handled
        @param solverParams: not handled
        """
        LpSolver.__init__(self, mip, msg)
        if not self.msg and swiglpk_mod is not None:
            swiglpk_mod.glp_term_out(swiglpk_mod.GLP_OFF)

    def findSolutionValues(self, lp):
        prob = lp.solverModel
        is_mip = self.mip and self.hasMIPConstraints(lp.solverModel)
        if is_mip:
            solutionStatus = swiglpk_mod.glp_mip_status(prob)
        else:
            solutionStatus = swiglpk_mod.glp_get_status(prob)
        S = constants.LpSolveStatus
        glpkLpStatus = {
            swiglpk_mod.GLP_OPT: S.Optimal,
            swiglpk_mod.GLP_UNDEF: S.Undefined,
            swiglpk_mod.GLP_FEAS: S.Stopped,
            swiglpk_mod.GLP_INFEAS: S.Infeasible,
            swiglpk_mod.GLP_NOFEAS: S.Infeasible,
            swiglpk_mod.GLP_UNBND: S.Unbounded,
        }
        col_value = (
            swiglpk_mod.glp_mip_col_val if is_mip else swiglpk_mod.glp_get_col_prim
        )
        for var in lp.variables():
            col = var.id + 1
            var.varValue = col_value(prob, col)
            var.dj = swiglpk_mod.glp_get_col_dual(prob, col)
        # put pi and slack variables against the constraints
        row_value = (
            swiglpk_mod.glp_mip_row_val if is_mip else swiglpk_mod.glp_get_row_prim
        )
        for constr in lp.constraints():
            row = constr.id + 1
            constr.slack = -constr.constant - row_value(prob, row)
            constr.pi = swiglpk_mod.glp_get_row_dual(prob, row)
        status = glpkLpStatus.get(solutionStatus, S.Undefined)
        return status, solutionStatus in (swiglpk_mod.GLP_OPT, swiglpk_mod.GLP_FEAS)

    def available(self):
        """True if the solver is available"""
        return swiglpk_mod is not None

    def hasMIPConstraints(self, solverModel):
        return (
            swiglpk_mod.glp_get_num_int(solverModel) > 0
            or swiglpk_mod.glp_get_num_bin(solverModel) > 0
        )

    def callSolver(self, lp, callback=None, warm=False):
        """Solves the problem with glpk

        :param warm: start from the basis the model holds (on a resolve)
            instead of building an advanced one
        """
        self.solveTime = -clock()
        # GLPK counts iterations over the model's lifetime: count this solve's
        swiglpk_mod.glp_set_it_cnt(lp.solverModel, 0)
        if not warm:
            swiglpk_mod.glp_adv_basis(lp.solverModel, 0)
        if swiglpk_mod.glp_simplex(lp.solverModel, None) in (
            swiglpk_mod.GLP_EBADB,
            swiglpk_mod.GLP_ESING,
            swiglpk_mod.GLP_ECOND,
        ):
            # the edits left the basis invalid or singular: start over
            swiglpk_mod.glp_adv_basis(lp.solverModel, 0)
            swiglpk_mod.glp_simplex(lp.solverModel, None)
        if self.mip and self.hasMIPConstraints(lp.solverModel):
            status = swiglpk_mod.glp_get_status(lp.solverModel)
            if status in (
                swiglpk_mod.GLP_OPT,
                swiglpk_mod.GLP_UNDEF,
                swiglpk_mod.GLP_FEAS,
            ):
                swiglpk_mod.glp_intopt(lp.solverModel, None)
        self.solveTime += clock()

    @requires("swiglpk")
    def buildSolverModel(self, lp):
        """
        Takes the pulp lp model and translates it into a glpk model.

        Every variable is a column, used or not: column ``j + 1`` is the
        variable with id ``j`` (as row ``i + 1`` is the constraint with id
        ``i``), so that a resolve only appends.
        """
        log.debug("create the glpk model")
        prob = swiglpk_mod.glp_create_prob()
        swiglpk_mod.glp_set_prob_name(prob, lp.name)
        log.debug("set the sense of the problem")
        if lp.sense == constants.LpMaximize:
            swiglpk_mod.glp_set_obj_dir(prob, swiglpk_mod.GLP_MAX)
        log.debug("add the constraints to the problem")
        constraints = lp.constraints()
        if constraints:
            swiglpk_mod.glp_add_rows(prob, len(constraints))
        for constraint in constraints:
            row = constraint.id + 1
            swiglpk_mod.glp_set_row_name(prob, row, constraint.name)
            _set_row_bnds(prob, row, constraint._constr)
        log.debug("add the variables to the problem")
        variables = lp.variables()
        if variables:
            swiglpk_mod.glp_add_cols(prob, len(variables))
        for var in variables:
            _set_col(prob, var._var)
        log.debug("set the objective function")
        for var, value in lp.objective.items():
            if value:
                swiglpk_mod.glp_set_obj_coef(prob, var.id + 1, value)
        log.debug("set the problem matrix")
        for constraint in constraints:
            _set_mat_row(prob, constraint._constr)
        lp.solverModel = prob
        self._start_tracking(lp)

    @requires("swiglpk")
    def applyChanges(self, lp: LpProblem, changes: _rustcore.ModelChanges) -> None:
        """Update ``lp.solverModel`` with the edits made to ``lp`` since it was
        last solved (``changes``, from :meth:`_take_changes`), keeping the basis.

        Columns are variable ids and rows constraint ids, so new variables and
        constraints are appended in id order.
        """
        prob = lp.solverModel
        model = lp._model

        if changes.sense_changed:
            swiglpk_mod.glp_set_obj_dir(
                prob,
                swiglpk_mod.GLP_MAX
                if lp.sense == constants.LpMaximize
                else swiglpk_mod.GLP_MIN,
            )

        # entries of new columns in existing rows go with the columns; GLPK
        # changes a matrix entry only by setting its whole row
        old_entries, columns = self._split_coefficients(
            lp, changes, swiglpk_mod.glp_get_num_cols(prob)
        )

        if changes.new_cols:
            swiglpk_mod.glp_add_cols(prob, len(changes.new_cols))
            costs = model.objective_coefficients(changes.new_cols)
            for j, cost in zip(changes.new_cols, costs):
                _set_col(prob, model.get_variable(j))
                swiglpk_mod.glp_set_obj_coef(prob, j + 1, cost)
                rows, values = columns.get(j, ([], []))
                ind, val = _arrays([i + 1 for i in rows], values)
                swiglpk_mod.glp_set_mat_col(prob, j + 1, len(rows), ind, val)

        if changes.new_rows:
            swiglpk_mod.glp_add_rows(prob, len(changes.new_rows))
            for i in changes.new_rows:
                rconstr = model.get_constraint(i)
                swiglpk_mod.glp_set_row_name(prob, i + 1, rconstr.name)
                _set_row_bnds(prob, i + 1, rconstr)
                _set_mat_row(prob, rconstr)

        for i in sorted({i for i, _, _ in old_entries}):
            _set_mat_row(prob, model.get_constraint(i))

        for i in changes.row_bounds:
            _set_row_bnds(prob, i + 1, model.get_constraint(i))

        for j in sorted(set(changes.var_bounds) | set(changes.var_category)):
            _set_col(prob, model.get_variable(j))

        if changes.objective_replaced:
            cols = list(range(swiglpk_mod.glp_get_num_cols(prob)))
            objective = lp.objective
            swiglpk_mod.glp_set_obj_coef(
                prob, 0, 0.0 if objective is None else objective.constant
            )
        else:
            cols = changes.obj_coeffs
        for j, cost in zip(cols, model.objective_coefficients(cols)):
            swiglpk_mod.glp_set_obj_coef(prob, j + 1, cost)

    @requires("swiglpk")
    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """
        Solve a well formulated lp problem

        creates a glpk model, variables and constraints and attaches
        them to the lp model which it then solves
        """
        start = clocks()
        callback = kwargs.get("callback")
        self.buildSolverModel(lp)
        # set the initial solution
        log.debug("Solve the Model using glpk")
        self.callSolver(lp, callback=callback)
        # get the solution information
        status, has_solution = self.findSolutionValues(lp)
        return self.buildStats(lp, status, has_solution, start=start)

    @requires("swiglpk")
    def actualResolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """Update ``lp.solverModel`` with the edits made since the last solve
        and solve it again from its current basis; build it from scratch if it
        cannot be updated (see :meth:`LpSolver._take_changes`)."""
        changes = self._take_changes(lp)
        if changes is None:
            return self.actualSolve(lp, **kwargs)
        start = clocks()
        try:
            self.applyChanges(lp, changes)
        except Exception:
            # the solver model may be half updated: rebuild it next time
            self._stop_tracking(lp)
            raise
        self.callSolver(lp, callback=kwargs.get("callback"), warm=True)
        status, has_solution = self.findSolutionValues(lp)
        return self.buildStats(lp, status, has_solution, start=start)


def _arrays(indices: list[int], values: list[float]) -> tuple[Any, Any]:
    """GLPK (1-based) index and value arrays for ``indices`` and ``values``."""
    ind = swiglpk_mod.intArray(len(indices) + 1)
    val = swiglpk_mod.doubleArray(len(values) + 1)
    for k, (index, value) in enumerate(zip(indices, values), start=1):
        ind[k] = index
        val[k] = value
    return ind, val


def _set_col(prob: Any, rvar: _rustcore.Variable) -> None:
    """Set the name, bounds and kind of the column of a variable of the Rust model."""
    j = rvar.id() + 1
    swiglpk_mod.glp_set_col_name(prob, j, rvar.name)
    lb, ub = rvar.lb, rvar.ub
    if math.isfinite(lb) and math.isfinite(ub):
        t = swiglpk_mod.GLP_FX if lb == ub else swiglpk_mod.GLP_DB
    elif math.isfinite(lb):
        t, ub = swiglpk_mod.GLP_LO, 0.0
    elif math.isfinite(ub):
        t, lb = swiglpk_mod.GLP_UP, 0.0
    else:
        t, lb, ub = swiglpk_mod.GLP_FR, 0.0, 0.0
    swiglpk_mod.glp_set_col_bnds(prob, j, t, lb, ub)
    # GLPK reclassifies integer columns bounded to [0, 1] as GLP_BV (binary)
    integer = rvar.category == _rustcore.Category.Integer
    swiglpk_mod.glp_set_col_kind(
        prob, j, swiglpk_mod.GLP_IV if integer else swiglpk_mod.GLP_CV
    )


def _set_row_bnds(prob: Any, row: int, rconstr: _rustcore.Constraint) -> None:
    """Set the bounds of ``row`` from a constraint of the Rust model."""
    rhs = rconstr.rhs
    if rconstr.sense == _rustcore.Sense.LessEqual:
        swiglpk_mod.glp_set_row_bnds(prob, row, swiglpk_mod.GLP_UP, 0.0, rhs)
    elif rconstr.sense == _rustcore.Sense.GreaterEqual:
        swiglpk_mod.glp_set_row_bnds(prob, row, swiglpk_mod.GLP_LO, rhs, 0.0)
    else:
        swiglpk_mod.glp_set_row_bnds(prob, row, swiglpk_mod.GLP_FX, rhs, rhs)


def _set_mat_row(prob: Any, rconstr: _rustcore.Constraint) -> None:
    """Set the whole matrix row of a constraint of the Rust model."""
    items = rconstr.items()
    ind, val = _arrays([rvar.id() + 1 for rvar, _ in items], [a for _, a in items])
    swiglpk_mod.glp_set_mat_row(prob, rconstr.id() + 1, len(items), ind, val)
