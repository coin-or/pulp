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
    LpSolver_API,
    LpSolver_CMD,
    PulpSolverError,
    clocks,
    import_optional,
    log,
    requires,
    subprocess,
)

if TYPE_CHECKING:
    from ..core.lp_problem import LpProblem
    from ..core.lp_stats import LpSolveStats

import warnings

gurobipy_mod = import_optional("gurobipy")
# optional: used to add all the rows of a model in one call
np = import_optional("numpy")
sparse = import_optional("scipy.sparse")


class GUROBI(LpSolver_API):
    """
    The Gurobi LP/MIP solver (via its python interface)

    The Gurobi variables are available (after a solve) in var.solverVar
    Constraints in constraint.solverConstraint
    and the Model is in prob.solverModel
    """

    name = "GUROBI"
    # no logPathSilencesMsg: msg=False sets OutputFlag=0, which empties the log file
    # as well as the console
    env = None

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        gapRel=None,
        gapAbs=None,
        warmStart=False,
        logPath=None,
        env=None,
        envOptions=None,
        manageEnv=False,
        **solverParams,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param str logPath: path to the log file
        :param gp.Env env: Gurobi environment to use. Default None.
        :param dict envOptions: environment options.
        :param bool manageEnv: if False, assume the environment is handled by the user.


        If ``manageEnv`` is set to True, the ``GUROBI`` object creates a
        local Gurobi environment and manages all associated Gurobi
        resources. Importantly, this enables Gurobi licenses to be freed
        and connections terminated when the ``.close()`` function is called
        (this function always disposes of the Gurobi model, and the
        environment)::

            solver = GUROBI(manageEnv=True)
            prob.solve(solver)
            solver.close() # Must be called to free Gurobi resources.
            # All Gurobi models and environments are freed

        ``manageEnv=True`` is required when setting license or connection
        parameters. The ``envOptions`` argument is used to pass parameters
        to the Gurobi environment. For example, to connect to a Gurobi
        Cluster Manager::

            options = {
                "CSManager": "<url>",
                "CSAPIAccessID": "<access-id>",
                "CSAPISecret": "<api-key>",
            }
            solver = GUROBI(manageEnv=True, envOptions=options)
            solver.close()
            # Compute server connection terminated

        Alternatively, one can also pass a ``gp.Env`` object. In this case,
        to be safe, one should still call ``.close()`` to dispose of the
        model::

            with gp.Env(params=options) as env:
                # Pass environment as a parameter
                solver = GUROBI(env=env)
                prob.solve(solver)
                solver.close()
                # Still call `close` as this disposes the model which is required to correctly free env

        If ``manageEnv`` is set to False (the default), the ``GUROBI``
        object uses the global default Gurobi environment which will be
        freed once the object is deleted. In this case, one can still call
        ``.close()`` to dispose of the model::

            solver = GUROBI()
            prob.solve(solver)
            # The global default environment and model remain active
            solver.close()
            # Only the global default environment remains active
        """
        self.env = env
        self.env_options = envOptions if envOptions else {}
        self.manage_env = False if self.env is not None else manageEnv
        self.solver_params = solverParams

        self.model = None
        self.init_gurobi = False  # whether env and model have been initialised

        LpSolver.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            gapRel=gapRel,
            gapAbs=gapAbs,
            logPath=logPath,
            warmStart=warmStart,
        )

        # set the output of gurobi
        if not self.msg:
            self.env_options["OutputFlag"] = 0

            if not self.manage_env:
                self.solver_params["OutputFlag"] = 0

    def __del__(self):
        self.close()

    def close(self):
        """
        Must be called when internal Gurobi model and/or environment
        requires disposing. The environment (default or otherwise) will be
        disposed only if ``manageEnv`` is set to True.
        """
        if not self.init_gurobi:
            return
        self.model.dispose()
        if self.manage_env:
            self.env.dispose()

    def findSolutionValues(self, lp: LpProblem, result: Any = None):
        model = lp.solverModel
        solutionStatus = model.Status
        GRB = gurobipy_mod.GRB
        S = constants.LpSolveStatus
        # looked up by name: older gurobipy versions lack some codes
        status_names = {
            "LOADED": S.NotSolved,
            "INPROGRESS": S.NotSolved,
            "OPTIMAL": S.Optimal,
            "LOCALLY_OPTIMAL": S.Optimal,
            "INFEASIBLE": S.Infeasible,
            "LOCALLY_INFEASIBLE": S.Infeasible,
            "INF_OR_UNBD": S.Undefined,
            "UNBOUNDED": S.Unbounded,
            "CUTOFF": S.GapLimit,
            "USER_OBJ_LIMIT": S.GapLimit,
            "ITERATION_LIMIT": S.IterationLimit,
            "NODE_LIMIT": S.NodeLimit,
            "TIME_LIMIT": S.TimeLimit,
            "WORK_LIMIT": S.TimeLimit,
            "SOLUTION_LIMIT": S.SolutionLimit,
            "MEM_LIMIT": S.MemoryLimit,
            "INTERRUPTED": S.Interrupted,
            "NUMERIC": S.NumericalError,
            "SUBOPTIMAL": S.NumericalError,
        }
        gurobiLpStatus = {
            getattr(GRB.Status, name): status
            for name, status in status_names.items()
            if hasattr(GRB.Status, name)
        }
        if self.msg:
            print("Gurobi status=", solutionStatus)
        status = gurobiLpStatus.get(solutionStatus, S.Undefined)
        has_solution = model.SolCount >= 1
        if has_solution:
            # column j is the variable with id j, row i the constraint with id i
            gvars = model.getVars()
            gconstrs = model.getConstrs()
            lp._model.set_variable_values(
                list(enumerate(model.getAttr(GRB.Attr.X, gvars)))
            )
            lp._model.set_constraint_slacks(
                list(enumerate(model.getAttr(GRB.Attr.Slack, gconstrs)))
            )
            # put pi and slack variables against the constraints
            if not model.IsMIP:
                lp._model.set_variable_djs(
                    list(enumerate(model.getAttr(GRB.Attr.RC, gvars)))
                )
                lp._model.set_constraint_pis(
                    list(enumerate(model.getAttr(GRB.Attr.Pi, gconstrs)))
                )
        return status, has_solution

    def available(self):
        """True if the solver is available"""
        if gurobipy_mod is None:
            return False
        try:
            with gurobipy_mod.Env(params=self.env_options):
                pass
        except gurobipy_mod.GurobiError as e:
            warnings.warn(f"GUROBI error: {e}.")
            return False
        return True

    def initGurobi(self):
        if self.init_gurobi:
            return
        else:
            self.init_gurobi = True
        try:
            if self.manage_env:
                self.env = gurobipy_mod.Env(params=self.env_options)
                self.model = gurobipy_mod.Model(env=self.env)
            # Environment handled by user or default Env
            else:
                self.model = gurobipy_mod.Model(env=self.env)
            # Set solver parameters
            for param, value in self.solver_params.items():
                self.model.setParam(param, value)
        except gurobipy_mod.GurobiError as e:
            raise e

    def callSolver(self, lp, *, changes=None, **kwargs):
        """Solves the problem with gurobi, with the ``callback`` given to solve"""
        lp.solverModel.optimize(callback=kwargs.get("callback"))

    def canUpdate(self, lp: LpProblem) -> bool:
        # this solver keeps a single model: solving another problem replaced it
        return self.model is lp.solverModel

    def _silence(self, solverModel):
        """Apply ``msg=False``, without also emptying the log file.

        ``OutputFlag=0`` turns off every kind of logging, the file included, and
        ``__init__`` already put it on the environment. When a log file was asked
        for, turn logging back on at the model level and silence the console
        alone, so ``msg=False`` still leaves something to parse.
        """
        if self.msg:
            return
        if self.optionsDict.get("logPath"):
            # silence the console first: doing it the other way round briefly
            # enables output and Gurobi echoes the parameter change
            solverModel.setParam("LogToConsole", 0)
            solverModel.setParam("OutputFlag", 1)
        else:
            solverModel.setParam("OutputFlag", 0)

    def _set_log_file(self, solverModel, logPath):
        """Point Gurobi at a log file without echoing the path to the console."""
        console = solverModel.Params.LogToConsole
        if console:
            solverModel.setParam("LogToConsole", 0)
        solverModel.setParam("LogFile", logPath)
        if console:
            solverModel.setParam("LogToConsole", console)

    def configureSolver(self, lp: LpProblem) -> None:
        """Apply msg, the time limit, gap tolerances and log file to the model."""
        solverModel = lp.solverModel
        self._silence(solverModel)
        if self.timeLimit:
            solverModel.setParam("TimeLimit", self.timeLimit)
        for option, param in [("gapRel", "MIPGap"), ("gapAbs", "MIPGapAbs")]:
            if (value := self.optionsDict.get(option)) is not None:
                solverModel.setParam(param, value)
        logPath = self.optionsDict.get("logPath")
        if logPath is not None:
            self._set_log_file(solverModel, str(logPath))

    @requires("gurobipy")
    def buildSolverModel(self, lp: LpProblem):
        """
        Takes the pulp lp model and translates it into a gurobi model
        """
        log.debug("create the gurobi model")
        self.initGurobi()
        assert self.model is not None
        self.model.ModelName = lp.name
        lp.solverModel = self.model
        log.debug("set the sense of the problem")
        if lp.sense == constants.LpMaximize:
            lp.solverModel.setAttr("ModelSense", -1)

        log.debug("add the variables to the problem")
        lp.solverModel.update()
        nvars = lp.solverModel.NumVars
        if nvars > 0:
            # the model holds another problem (or an older version of this one)
            lp.solverModel.dispose()
            self.init_gurobi = False
            self.initGurobi()
            assert self.model is not None
            self.model.ModelName = lp.name
            lp.solverModel = self.model
            if lp.sense == constants.LpMaximize:
                lp.solverModel.setAttr("ModelSense", -1)

        m = lp.solverModel
        # every variable is a column, used or not: column j is the variable with
        # id j (as row i is the constraint with id i), so a resolve only appends.
        # Columns and rows are added in one call each: one call per column or row
        # costs more than the solve itself on large, easy models
        variables = lp.variables()
        obj = [0.0] * len(variables)
        for var, coefficient in lp.objective.items():
            obj[var.id] = coefficient
        var_handles: list[Any] = list(
            m.addVars(
                len(variables),
                lb=[_bound(var.lowBound) for var in variables],
                ub=[_bound(var.upBound) for var in variables],
                obj=obj,
                vtype=[
                    self._vtype(var.cat == constants.LpInteger) for var in variables
                ],
                name=[var.name for var in variables],
            ).values()
        )
        if self.optionsDict.get("warmStart", False):
            started = [var for var in variables if var.varValue is not None]
            if started:
                m.setAttr(
                    "Start",
                    [var_handles[var.id] for var in started],
                    [var.varValue for var in started],
                )

        log.debug("add the Constraints to the problem")
        constraints = lp.constraints()
        if constraints:
            self._add_rows(m, var_handles, constraints)
        m.update()
        self.configureSolver(lp)
        self._start_tracking(lp)

    def _add_rows(self, m: Any, var_handles: list[Any], constraints: list) -> None:
        """Add the constraints to the Gurobi model, in one ``addMConstr`` call if
        numpy and scipy are installed, else with one ``addLConstr`` call per row."""
        senses = {
            constants.LpConstraintLE: gurobipy_mod.GRB.LESS_EQUAL,
            constants.LpConstraintGE: gurobipy_mod.GRB.GREATER_EQUAL,
            constants.LpConstraintEQ: gurobipy_mod.GRB.EQUAL,
        }
        sense: list[str] = []
        rhs: list[float] = []
        names: list[str] = []
        indptr = [0]
        indices: list[int] = []
        data: list[float] = []
        for constraint in constraints:
            try:
                sense.append(senses[constraint.sense])
            except KeyError:
                raise PulpSolverError("Detected an invalid constraint type") from None
            rhs.append(-constraint.constant)
            names.append(constraint.name)
            for var, coefficient in constraint.items():
                if coefficient != 0:
                    indices.append(var.id)
                    data.append(coefficient)
            indptr.append(len(indices))

        if np is None or sparse is None:
            LinExpr = gurobipy_mod.LinExpr
            for i, name in enumerate(names):
                start, end = indptr[i], indptr[i + 1]
                expr = LinExpr(
                    data[start:end], [var_handles[j] for j in indices[start:end]]
                )
                m.addLConstr(expr, sense[i], rhs[i], name=name)
            return

        A = sparse.csr_matrix(
            (
                np.array(data, dtype=np.float64),
                np.array(indices, dtype=np.int64),
                np.array(indptr, dtype=np.int64),
            ),
            shape=(len(names), len(var_handles)),
        )
        x = gurobipy_mod.MVar.fromlist(var_handles)
        constrs = m.addMConstr(A, x, np.array(sense), np.array(rhs, dtype=np.float64))
        m.update()
        m.setAttr("ConstrName", constrs.tolist(), names)

    def _vtype(self, integer: bool) -> str:
        GRB = gurobipy_mod.GRB
        return GRB.INTEGER if integer and self.mip else GRB.CONTINUOUS

    @requires("gurobipy")
    def applyChanges(self, lp: LpProblem, changes: _rustcore.ModelChanges) -> None:
        """Update ``lp.solverModel`` with the edits made to ``lp`` since it was
        last solved (``changes``, from :meth:`_take_changes`), keeping the basis.

        Columns are variable ids and rows constraint ids, so new variables and
        constraints are appended in id order.
        """
        m: Any = lp.solverModel
        model = lp._model
        GRB = gurobipy_mod.GRB
        is_integer = _rustcore.Category.Integer

        if changes.sense_changed:
            m.ModelSense = -1 if lp.sense == constants.LpMaximize else 1

        gvars = m.getVars()
        gconstrs = m.getConstrs()
        # entries of new columns in existing rows go with the columns, the others
        # are changed one by one
        old_entries, columns = self._split_coefficients(lp, changes, len(gvars))

        if changes.new_cols:
            costs = model.objective_coefficients(changes.new_cols)
            for j, cost in zip(changes.new_cols, costs):
                rvar = model.get_variable(j)
                rows, coefficients = columns.get(j, ([], []))
                gvars.append(
                    m.addVar(
                        _bound(rvar.lb),
                        _bound(rvar.ub),
                        obj=cost,
                        vtype=self._vtype(rvar.category == is_integer),
                        name=rvar.name,
                        column=gurobipy_mod.Column(
                            coefficients, [gconstrs[i] for i in rows]
                        ),
                    )
                )

        for i in changes.new_rows:
            rconstr = model.get_constraint(i)
            items = rconstr.items()
            expr = gurobipy_mod.LinExpr(
                [coefficient for _, coefficient in items],
                [gvars[rvar.id()] for rvar, _ in items],
            )
            m.addLConstr(expr, _sense(rconstr.sense), rconstr.rhs, name=rconstr.name)

        for i, j, value in old_entries:
            m.chgCoeff(gconstrs[i], gvars[j], value)

        if changes.row_bounds:
            rconstrs = [model.get_constraint(i) for i in changes.row_bounds]
            constrs = [gconstrs[i] for i in changes.row_bounds]
            m.setAttr(GRB.Attr.RHS, constrs, [c.rhs for c in rconstrs])
            m.setAttr(GRB.Attr.Sense, constrs, [_sense(c.sense) for c in rconstrs])

        if changes.var_bounds:
            rvars = [model.get_variable(j) for j in changes.var_bounds]
            handles = [gvars[j] for j in changes.var_bounds]
            m.setAttr(GRB.Attr.LB, handles, [_bound(v.lb) for v in rvars])
            m.setAttr(GRB.Attr.UB, handles, [_bound(v.ub) for v in rvars])

        if changes.var_category:
            rvars = [model.get_variable(j) for j in changes.var_category]
            m.setAttr(
                GRB.Attr.VType,
                [gvars[j] for j in changes.var_category],
                [self._vtype(v.category == is_integer) for v in rvars],
            )

        if changes.objective_replaced:
            cols = list(range(len(gvars)))
            objective = lp.objective
            m.ObjCon = 0.0 if objective is None else objective.constant
        else:
            cols = changes.obj_coeffs
        if cols:
            m.setAttr(
                GRB.Attr.Obj,
                [gvars[j] for j in cols],
                model.objective_coefficients(cols),
            )
        m.update()


def _bound(value: float) -> float:
    """A pulp bound as Gurobi takes it: infinite bounds as ``GRB.INFINITY``."""
    if math.isfinite(value):
        return value
    return gurobipy_mod.GRB.INFINITY if value > 0 else -gurobipy_mod.GRB.INFINITY


def _sense(sense: _rustcore.Sense) -> str:
    """The Gurobi sense character of a constraint of the Rust model."""
    GRB = gurobipy_mod.GRB
    if sense == _rustcore.Sense.LessEqual:
        return GRB.LESS_EQUAL
    if sense == _rustcore.Sense.GreaterEqual:
        return GRB.GREATER_EQUAL
    return GRB.EQUAL


class GUROBI_CMD(LpSolver_CMD):
    """The GUROBI_CMD solver"""

    name = "GUROBI_CMD"

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        gapRel=None,
        gapAbs=None,
        options=None,
        warmStart=False,
        keepFiles=False,
        path=None,
        threads=None,
        logPath=None,
        mip_start=False,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param list options: list of additional options to pass to solver
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary
        :param str logPath: path to the log file
        """
        LpSolver_CMD.__init__(
            self,
            gapRel=gapRel,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            warmStart=warmStart,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            gapAbs=gapAbs,
            logPath=logPath,
        )

    def defaultPath(self):
        return self.executableExtension("gurobi_cl")

    def available(self):
        """True if the solver is available"""
        if not self.executable(self.path):
            return False
        # we execute gurobi once to check the return code.
        # this is to test that the license is active
        result = subprocess.Popen(
            self.path, stdout=subprocess.PIPE, universal_newlines=True
        )
        out, err = result.communicate()
        if result.returncode == 0:
            # normal execution
            return True
        # error: we display the gurobi message
        if self.msg:
            warnings.warn(f"GUROBI error: {out}.")
        return False

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """Solve a well formulated lp problem."""
        start = clocks()
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpMst = self.create_tmp_files(lp.name, "lp", "sol", "mst")
        vs = lp.writeLP(tmpLp, writeSOS=1)
        try:
            os.remove(tmpSol)
        except Exception:
            pass
        cmd = self.path
        options = self.options + self.getOptions()
        if self.timeLimit is not None:
            options.append(("TimeLimit", self.timeLimit))
        cmd += " " + " ".join([f"{key}={value}" for key, value in options])
        cmd += f" ResultFile={tmpSol}"
        if self.optionsDict.get("warmStart", False):
            self.writesol(filename=tmpMst, vs=vs)
            cmd += f" InputFile={tmpMst}"

        if lp.isMIP():
            if not self.mip:
                warnings.warn("GUROBI_CMD does not allow a problem to be relaxed")
        cmd += f" {tmpLp}"
        pipe = self.get_pipe()

        return_code = subprocess.call(cmd.split(), stdout=pipe, stderr=pipe)

        # Close the pipe now if we used it.
        if pipe is not None:
            pipe.close()

        if return_code != 0:
            raise PulpSolverError("PuLP: Error while trying to execute " + self.path)
        if not os.path.exists(tmpSol):
            # TODO: the status should be infeasible here, I think
            status = constants.LpSolveStatus.NotSolved
            values = reducedCosts = shadowPrices = slacks = None
        else:
            # TODO: the status should be infeasible here, I think
            status, values, reducedCosts, shadowPrices, slacks = self.readsol(tmpSol)
        self.delete_tmp_files(tmpLp, tmpMst, tmpSol, "gurobi.log")
        has_solution = bool(values)
        if has_solution:
            if values is not None:
                lp.assignVarsVals(values)
            if reducedCosts is not None:
                lp.assignVarsDj(reducedCosts)
            if shadowPrices is not None:
                lp.assignConsPi(shadowPrices)
            if slacks is not None:
                lp.assignConsSlack(slacks)
        return self.buildStats(lp, status, has_solution, start=start)

    def readsol(self, filename):
        """Read a Gurobi solution file"""
        with open(filename) as my_file:
            try:
                next(my_file)  # skip the objective value
            except StopIteration:
                # Empty file not solved
                status = constants.LpSolveStatus.NotSolved
                return status, {}, {}, {}, {}
            # We have no idea what the status is assume optimal
            # TODO: check status for Integer Feasible
            status = constants.LpSolveStatus.Optimal

            shadowPrices = {}
            slacks = {}
            shadowPrices = {}
            slacks = {}
            values = {}
            reducedCosts = {}
            for line in my_file:
                if line[0] != "#":  # skip comments
                    name, value = line.split()
                    values[name] = float(value)
        return status, values, reducedCosts, shadowPrices, slacks

    def writesol(self, filename, vs):
        """Writes a GUROBI solution file"""

        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        rows = []
        for name, value in values:
            rows.append(f"{name} {value}")
        with open(filename, "w") as f:
            f.write("\n".join(rows))
        return True

    def getOptions(self):
        # GUROBI parameters: http://www.gurobi.com/documentation/7.5/refman/parameters.html#sec:Parameters
        params_eq = dict(
            logPath="LogFile",
            gapRel="MIPGap",
            gapAbs="MIPGapAbs",
            threads="Threads",
        )
        return [
            (v, self.optionsDict[k])
            for k, v in params_eq.items()
            if k in self.optionsDict and self.optionsDict[k] is not None
        ]
