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

import sys
from typing import Any

from .. import constants
from .core import (
    LpSolver_API,
    PulpSolverError,
    import_optional,
    requires,
)

mosek_mod = import_optional("mosek")


class MOSEK(LpSolver_API):
    """Mosek lp and mip solver (via Mosek Optimizer API)."""

    name = "MOSEK"
    env: Any = mosek_mod.Env() if mosek_mod is not None else None

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit: float | None = None,
        options: dict | None = None,
        task_file_name="",
        sol_type=None,
    ):
        """Initializes the Mosek solver.

        Keyword arguments:

        @param mip: If False, then solve MIP as LP.

        @param msg: Enable Mosek log output.

        @param float timeLimit: maximum time for solver (in seconds)

        @param options: Accepts a dictionary of Mosek solver parameters. Ignore to
                        use default parameter values. Eg: options = {mosek.dparam.mio_max_time:30}
                        sets the maximum time spent by the Mixed Integer optimizer to 30 seconds.
                        Equivalently, one could also write: options = {"MSK_DPAR_MIO_MAX_TIME":30}
                        which uses the generic parameter name as used within the solver, instead of
                        using an object from the Mosek Optimizer API (Python), as before.

        @param task_file_name: Writes a Mosek task file of the given name. By default,
                        no task file will be written. Eg: task_file_name = "eg1.opf".

        @param sol_type: Mosek supports three types of solutions: mosek.soltype.bas
                        (Basic solution, default), mosek.soltype.itr (Interior-point
                        solution) and mosek.soltype.itg (Integer solution).
                        Default None uses mosek.soltype.bas.

        For a full list of Mosek parameters (for the Mosek Optimizer API) and supported task file
        formats, please see https://docs.mosek.com/9.1/pythonapi/parameters.html#doc-all-parameter-list.
        """
        self.mip = mip
        self.msg = msg
        self.timeLimit = timeLimit
        self.task_file_name = task_file_name
        if sol_type is None and mosek_mod is not None:
            sol_type = mosek_mod.soltype.bas
        self.solution_type = sol_type
        if options is None:
            options = {}
        self.options: dict = options
        if self.timeLimit is not None:
            timeLimit_keys: set = {"MSK_DPAR_MIO_MAX_TIME"}
            if mosek_mod is not None:
                timeLimit_keys.add(mosek_mod.dparam.mio_max_time)
            if not timeLimit_keys.isdisjoint(self.options.keys()):
                raise ValueError(
                    "timeLimit parameter has been provided trough `timeLimit` and `options`."
                )
            self.options["MSK_DPAR_MIO_MAX_TIME"] = self.timeLimit

    def available(self):
        """True if Mosek is available."""
        return mosek_mod is not None

    def setOutStream(self, text):
        """Sets the log-output stream."""
        sys.stdout.write(text)
        sys.stdout.flush()

    @requires("mosek")
    def buildSolverModel(self, lp, inf=1e20):
        """Translate the problem into a Mosek task object, in ``lp.solverModel``."""
        cons = lp.constraints()
        numcons = len(cons)
        cons_dict = {constr.name: i for i, constr in enumerate(cons)}
        variables = list(lp.exported_variables())
        numvars = len(variables)
        var_dict = {}
        # Checking for repeated names
        lp.checkDuplicateVars()
        lp.checkDuplicateConstraints()
        task = lp.solverModel = MOSEK.env.Task()
        task.appendcons(numcons)
        task.appendvars(numvars)
        if self.msg:
            task.set_Stream(mosek_mod.streamtype.log, self.setOutStream)
        # Adding variables
        for i, var in enumerate(variables):
            var_dict[var.name] = i
            task.putvarname(i, var.name)
            # Variable type (Default: Continuous)
            if self.mip & (var.cat == constants.LpInteger):
                task.putvartype(i, mosek_mod.variabletype.type_int)
            # Variable bounds
            vbkey = mosek_mod.boundkey.fr
            vup = inf
            vlow = -inf
            if var.lowBound is not None:
                vlow = var.lowBound
                if var.upBound is not None:
                    vup = var.upBound
                    vbkey = mosek_mod.boundkey.ra
                else:
                    vbkey = mosek_mod.boundkey.lo
            elif var.upBound is not None:
                vup = var.upBound
                vbkey = mosek_mod.boundkey.up
            task.putvarbound(i, vbkey, vlow, vup)
            # Objective coefficient for the current variable.
            task.putcj(i, lp.objective.get(var, 0.0))
        # Coefficient matrix
        A_rows, A_cols, A_vals = zip(
            *[
                [cons_dict[row], var_dict[col], coeff]
                for col, row, coeff in lp.coefficients()
            ]
        )
        task.putaijlist(A_rows, A_cols, A_vals)
        # Constraints
        constraint_data_list = []
        for i, constr in enumerate(cons):
            cname = constr.name
            row_key = cname if cname is not None else ""
            if cname is not None:
                task.putconname(i, cname)
            else:
                task.putconname(i, row_key)
            csense = constr.sense
            cconst = -constr.constant
            clow = -inf
            cup = inf
            # Constraint bounds
            if csense == constants.LpConstraintEQ:
                cbkey = mosek_mod.boundkey.fx
                clow = cconst
                cup = cconst
            elif csense == constants.LpConstraintGE:
                cbkey = mosek_mod.boundkey.lo
                clow = cconst
            elif csense == constants.LpConstraintLE:
                cbkey = mosek_mod.boundkey.up
                cup = cconst
            else:
                raise PulpSolverError("Invalid constraint type.")
            constraint_data_list.append([i, cbkey, clow, cup])
        task.putconboundlist(*zip(*constraint_data_list))
        # Objective sense
        if lp.sense == constants.LpMaximize:
            task.putobjsense(mosek_mod.objsense.maximize)
        else:
            task.putobjsense(mosek_mod.objsense.minimize)
        self.configureSolver(lp)

    def configureSolver(self, lp):
        """Pass the solver parameters to the Mosek task ``lp.solverModel``."""
        for msk_par in self.options:
            self.putparam(lp.solverModel, msk_par, self.options[msk_par])

    def callSolver(self, lp, *, changes=None, **kwargs):
        """Solves the Mosek task and returns its termination code."""
        task = lp.solverModel
        # Task file
        if self.task_file_name:
            task.writedata(self.task_file_name)
        trmcode = task.optimize()
        # Mosek solver log (default: standard output stream)
        if self.msg:
            task.solutionsummary(mosek_mod.streamtype.msg)
        return trmcode

    def findSolutionValues(self, lp, result=None):
        """
        Read the solution values and status from the Mosek task object. Note: Since the status
        map from mosek.solsta to LpStatus is not exact, it is recommended that one enables the
        log output and then refer to Mosek documentation for a better understanding of the
        solution (especially in the case of mip problems).

        :param result: the termination code that :meth:`callSolver` returned
        """
        task = lp.solverModel
        variables = list(lp.exported_variables())
        constraints = lp.constraints()
        numvars = len(variables)
        numcons = len(constraints)
        solution_type = self.solution_type
        if task.getnumintvar() > 0:
            solution_type = mosek_mod.soltype.itg
        solsta = task.getsolsta(solution_type)
        S = constants.LpSolveStatus
        solution_status_dict = {
            mosek_mod.solsta.optimal: S.Optimal,
            mosek_mod.solsta.prim_infeas_cer: S.Infeasible,
            mosek_mod.solsta.dual_infeas_cer: S.Unbounded,
            mosek_mod.solsta.unknown: S.Undefined,
            mosek_mod.solsta.integer_optimal: S.Optimal,
            mosek_mod.solsta.prim_illposed_cer: S.NumericalError,
            mosek_mod.solsta.dual_illposed_cer: S.NumericalError,
            mosek_mod.solsta.prim_feas: S.Stopped,
            mosek_mod.solsta.dual_feas: S.Stopped,
            mosek_mod.solsta.prim_and_dual_feas: S.Stopped,
        }
        has_solution = solsta in (
            mosek_mod.solsta.optimal,
            mosek_mod.solsta.integer_optimal,
            mosek_mod.solsta.prim_feas,
            mosek_mod.solsta.prim_and_dual_feas,
        )
        # Variable values.
        try:
            xx = [0.0] * numvars
            task.getxx(solution_type, xx)
            for i, var in enumerate(variables):
                var.varValue = xx[i]
        except mosek_mod.Error:
            pass
        # Constraint slack variables.
        try:
            xc = [0.0] * numcons
            task.getxc(solution_type, xc)
            for i, constr in enumerate(constraints):
                constr.slack = -(constr.constant + xc[i])
        except mosek_mod.Error:
            pass
        # Reduced costs.
        if solution_type != mosek_mod.soltype.itg:
            try:
                x_rc = [0.0] * numvars
                task.getreducedcosts(solution_type, 0, numvars, x_rc)
                for i, var in enumerate(variables):
                    var.dj = x_rc[i]
            except mosek_mod.Error:
                pass
            # Constraint Pi variables.
            try:
                y = [0.0] * numcons
                task.gety(solution_type, y)
                for i, constr in enumerate(constraints):
                    constr.pi = y[i]
            except mosek_mod.Error:
                pass
        status = solution_status_dict.get(solsta, S.Undefined)
        if status in (S.Stopped, S.Undefined):
            status = self.termination_status(result, status)
        return status, has_solution

    @staticmethod
    def putparam(task, par, val):
        """
        Pass the values of valid parameters to the Mosek ``task``.
        """
        if isinstance(par, mosek_mod.dparam):
            task.putdouparam(par, val)
        elif isinstance(par, mosek_mod.iparam):
            task.putintparam(par, val)
        elif isinstance(par, mosek_mod.sparam):
            task.putstrparam(par, val)
        elif isinstance(par, str):
            if par.startswith("MSK_DPAR_"):
                task.putnadouparam(par, val)
            elif par.startswith("MSK_IPAR_"):
                task.putnaintparam(par, val)
            elif par.startswith("MSK_SPAR_"):
                task.putnastrparam(par, val)
            else:
                raise PulpSolverError(
                    "Invalid MOSEK parameter: '{}'. Check MOSEK documentation for a list of valid parameters.".format(
                        par
                    )
                )

    @staticmethod
    def termination_status(trmcode, default):
        """Why MOSEK stopped early, read off the termination code of optimize()."""
        S = constants.LpSolveStatus
        # looked up by name: not every MOSEK version defines every code
        trm_names = {
            "trm_max_time": S.TimeLimit,
            "trm_max_iterations": S.IterationLimit,
            "trm_mio_num_branches": S.NodeLimit,
            "trm_mio_num_relaxs": S.NodeLimit,
            "trm_num_max_num_int_solutions": S.SolutionLimit,
            "trm_mio_near_rel_gap": S.GapLimit,
            "trm_mio_near_abs_gap": S.GapLimit,
            "trm_objective_range": S.GapLimit,
            "trm_user_callback": S.Interrupted,
            "trm_numerical_problem": S.NumericalError,
            "trm_stall": S.NumericalError,
        }
        for name, status in trm_names.items():
            if trmcode == getattr(mosek_mod.rescode, name, None):
                return status
        return default
