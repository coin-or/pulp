from __future__ import annotations

import dataclasses
import datetime
import math
import sys
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import _rustcore, constants
from .core import (
    LpSolver,
    LpSolver_API,
    PulpSolverError,
    _RebuildNeeded,
    _row_bounds,
    import_optional,
    log,
    requires,
)

if TYPE_CHECKING:
    from .. import _rustcore
    from ..core.lp_problem import LpProblem

cp_model_mod = import_optional("ortools.sat.python.cp_model")
mathopt_mod = import_optional("ortools.math_opt.python.mathopt")
model_pb2_mod = import_optional("ortools.math_opt.model_pb2")
glop_parameters_pb2_mod = import_optional("ortools.glop.parameters_pb2")


def _decimal_places(value: float) -> int:
    text = format(value, ".15f").rstrip("0")
    if "." not in text:
        return 0
    return len(text.split(".")[1])


def _integer_scale(values: list[float]) -> int:
    places = max((_decimal_places(v) for v in values), default=0)
    return 10**places


def _scale_to_int(value: float, scale: int) -> int:
    return int(round(value * scale))


class CPSAT(LpSolver_API):
    """
    The OR-Tools CP-SAT solver (via its Python API).

    CP-SAT requires finite lower and upper bounds on every variable.
    Continuous variables are converted to integer variables on
    ``[ceil(lowBound), floor(upBound)]``.

    The CP-SAT model is available (after a solve) in ``prob.solverModel``.
    """

    name = "CPSAT"

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        warmStart=False,
        logPath=None,
        **solverParams,
    ):
        """
        :param bool mip: ignored; CP-SAT always solves as a discrete model
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param bool warmStart: if True, pass current variable values as hints
        :param str logPath: path to write the search log to
        :param dict solverParams: ``threads`` or additional parameters for
            ``CpSolver.parameters``
        """
        LpSolver.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            warmStart=warmStart,
            logPath=logPath,
            **solverParams,
        )

    def available(self) -> bool:
        """True if the solver is available"""
        return cp_model_mod is not None

    @requires("ortools.sat.python.cp_model")
    def buildSolverModel(self, lp: LpProblem) -> None:
        """
        Takes the pulp lp model and translates it into a CP-SAT model.

        The CP-SAT variable with index ``j`` is ``lp.exported_variables()[j]``.
        """
        if not self.mip:
            warnings.warn(
                "CPSAT always solves as a discrete model; mip=False is ignored"
            )

        exported_vars = list(lp.exported_variables())
        if len({var.name for var in exported_vars}) != len(exported_vars):
            raise PulpSolverError("Variables must have unique names for CPSAT solver")

        id_to_col = {v.id: j for j, v in enumerate(exported_vars)}
        var_handles: list[Any] = []

        log.debug("create the CP-SAT model")
        model = lp.solverModel = cp_model_mod.CpModel()

        log.debug("add the variables to the problem")
        for var in exported_vars:
            if not math.isfinite(var.lowBound):
                raise PulpSolverError(
                    f"Variable {var.name!r} has no finite lower bound; "
                    "CPSAT requires finite bounds"
                )
            if not math.isfinite(var.upBound):
                raise PulpSolverError(
                    f"Variable {var.name!r} has no finite upper bound; "
                    "CPSAT requires finite bounds"
                )

            if var.cat == constants.LpBinary:
                cp_var = model.NewBoolVar(var.name)
            elif var.cat == constants.LpInteger:
                lb = int(var.lowBound)
                ub = int(var.upBound)
                cp_var = model.NewIntVar(lb, ub, var.name)
            elif var.cat == constants.LpContinuous:
                lb = math.ceil(var.lowBound)
                ub = math.floor(var.upBound)
                if lb > ub:
                    raise PulpSolverError(
                        f"Variable {var.name!r} has empty integer domain after "
                        f"converting continuous bounds [{var.lowBound}, {var.upBound}]"
                    )
                cp_var = model.NewIntVar(lb, ub, var.name)
            else:
                raise PulpSolverError(f"Unsupported variable category for {var.name!r}")

            var_handles.append(cp_var)

        if self.optionsDict.get("warmStart", False):
            hinted = False
            for j, var in enumerate(exported_vars):
                if var.varValue is not None:
                    hinted = True
                    hint_value = var.varValue
                    if var.cat == constants.LpBinary:
                        model.AddHint(var_handles[j], bool(round(hint_value)))
                    else:
                        model.AddHint(var_handles[j], int(round(hint_value)))
            if not hinted:
                warnings.warn("No variable with value found: warmStart aborted")

        log.debug("add the objective to the problem")
        if lp.objective is not None:
            obj_terms = []
            for var, coeff in lp.objective.items():
                coeff_f = float(0.0 if coeff is None else coeff)
                if coeff_f == 0.0:
                    continue
                obj_terms.append(coeff_f * var_handles[id_to_col[var.id]])
            if obj_terms:
                obj_expr = obj_terms[0] if len(obj_terms) == 1 else sum(obj_terms)
                if lp.sense == constants.LpMaximize:
                    model.Maximize(obj_expr)
                else:
                    model.Minimize(obj_expr)

        log.debug("add the Constraints to the problem")
        for constraint in lp.constraints():
            items = constraint.items()
            coeffs = [float(c) for _, c in items]
            rhs = float(-constraint.constant)
            scale = _integer_scale(coeffs + [rhs])
            int_coeffs = [_scale_to_int(c, scale) for c in coeffs]
            int_rhs = _scale_to_int(rhs, scale)

            terms = [
                int_coeffs[i] * var_handles[id_to_col[var.id]]
                for i, (var, _) in enumerate(items)
                if int_coeffs[i] != 0
            ]
            if terms:
                expr = terms[0] if len(terms) == 1 else sum(terms)
            else:
                expr = 0

            if constraint.sense == constants.LpConstraintLE:
                model.Add(expr <= int_rhs)
            elif constraint.sense == constants.LpConstraintGE:
                model.Add(expr >= int_rhs)
            elif constraint.sense == constants.LpConstraintEQ:
                model.Add(expr == int_rhs)
            else:
                raise PulpSolverError("Detected an invalid constraint type")

    @requires("ortools.sat.python.cp_model")
    def callSolver(
        self,
        lp: LpProblem,
        *,
        changes: _rustcore.ModelChanges | None = None,
        **kwargs: Any,
    ) -> tuple[Any, Any]:
        """Solves the problem with CP-SAT and returns the solver and status."""
        solver = cp_model_mod.CpSolver()
        solver.parameters.log_search_progress = bool(self.msg)
        # CP-SAT has no log file parameter, so a logPath is served by appending each
        # line of the search log to the file as the callback receives it.
        log_path = self.optionsDict.get("logPath")
        log_file = open(log_path, "w") if log_path else None
        if log_file is not None:
            solver.parameters.log_search_progress = True
            try:
                solver.parameters.log_to_stdout = bool(self.msg)
            except AttributeError:  # older ortools versions
                pass

            def write_log(line: str) -> None:
                log_file.write(line + "\n")
                log_file.flush()

            solver.log_callback = write_log
        if self.timeLimit is not None:
            solver.parameters.max_time_in_seconds = float(self.timeLimit)
        if "threads" in self.optionsDict:
            solver.parameters.num_search_workers = int(self.optionsDict["threads"])
        for param, value in self.optionsDict.items():
            try:
                setattr(solver.parameters, param, value)
            except AttributeError:  # not a CP-SAT parameter
                pass

        try:
            status = solver.Solve(lp.solverModel)
        finally:
            if log_file is not None:
                log_file.close()
        return solver, status

    @requires("ortools.sat.python.cp_model")
    def findSolutionValues(
        self, lp: LpProblem, result: Any = None
    ) -> tuple[constants.LpSolveStatus, bool]:
        """:param result: the ``(solver, status)`` that :meth:`callSolver` returned"""
        solver, status_code = result
        exported_vars = list(lp.exported_variables())
        # CP-SAT does not say which limit stopped it, only whether it has a solution
        cp_status = {
            cp_model_mod.OPTIMAL: constants.LpSolveStatus.Optimal,
            cp_model_mod.FEASIBLE: constants.LpSolveStatus.Stopped,
            cp_model_mod.INFEASIBLE: constants.LpSolveStatus.Infeasible,
            cp_model_mod.UNKNOWN: constants.LpSolveStatus.Stopped,
            cp_model_mod.MODEL_INVALID: constants.LpSolveStatus.Undefined,
        }
        status = cp_status.get(status_code, constants.LpSolveStatus.Undefined)
        has_solution = status_code in (cp_model_mod.OPTIMAL, cp_model_mod.FEASIBLE)

        if has_solution:
            values = {
                var.name: solver.Value(lp.solverModel.GetIntVarFromProtoIndex(j))
                for j, var in enumerate(exported_vars)
            }
            lp.assignVarsVals(values)

        return status, has_solution


@dataclasses.dataclass
class GlopModel:
    """What :class:`GLOP` keeps in ``lp.solverModel``.

    :ivar model: the MathOpt ``Model``; its variable ``j`` and linear
        constraint ``i`` have the ids of the pulp variable and constraint
    :ivar solver: the MathOpt ``IncrementalSolver`` running GLOP, which keeps
        its basis from one solve to the next
    :ivar params: the ``SolveParameters`` of the next solve
    :ivar result: the ``SolveResult`` of the last solve (termination, solve
        statistics, basis...), None before the first one
    """

    model: Any
    solver: Any
    params: Any = None
    result: Any = None


# solver parameters given by name that MathOpt takes as an enum
_GLOP_ENUM_PARAMS = {
    "lp_algorithm": "LPAlgorithm",
    "presolve": "Emphasis",
    "scaling": "Emphasis",
}


def _glop_error(err: Exception) -> PulpSolverError:
    """The error GLOP reported, as a :class:`PulpSolverError`.

    ortools 9.15 fails while converting the solver's own error (a
    ``StatusNotOk``) and raises an ``AttributeError`` instead: its message is
    in the error being handled then.
    """
    cause: BaseException = err
    if isinstance(err, AttributeError) and err.__context__ is not None:
        cause = err.__context__
    return PulpSolverError(f"GLOP: {cause}")


def _bound_status(status: Any, lb: float, ub: float) -> Any:
    """``status`` of a variable or constraint in a basis, unless it names a
    bound that ``[lb, ub]`` does not have (or is None, for a new variable):
    then the bound a nonbasic entry sits at."""
    BasisStatus = mathopt_mod.BasisStatus
    if (
        status == BasisStatus.BASIC
        or (status == BasisStatus.AT_LOWER_BOUND and math.isfinite(lb))
        or (status == BasisStatus.AT_UPPER_BOUND and math.isfinite(ub))
        or (status == BasisStatus.FIXED_VALUE and lb == ub)
        or (
            status == BasisStatus.FREE
            and not math.isfinite(lb)
            and not math.isfinite(ub)
        )
    ):
        return status
    if math.isfinite(lb):
        return BasisStatus.AT_LOWER_BOUND
    if math.isfinite(ub):
        return BasisStatus.AT_UPPER_BOUND
    return BasisStatus.FREE


def _warm_basis(glop: GlopModel) -> Any:
    """The basis of the last solve of ``glop``, completed for its current
    model, or None if there is none (first solve, or no basis came back).

    MathOpt's incremental GLOP drops most of its basis once rows are added, so
    a resolve hands it back explicitly: new variables nonbasic at a bound and
    new constraints basic, which keeps one basic entry per row.
    """
    result = glop.result
    if result is None or not result.solutions or result.solutions[0].basis is None:
        return None
    old = result.solutions[0].basis
    basis = mathopt_mod.Basis()
    for var in glop.model.variables():
        basis.variable_status[var] = _bound_status(
            old.variable_status.get(var), var.lower_bound, var.upper_bound
        )
    for constraint in glop.model.linear_constraints():
        basis.constraint_status[constraint] = _bound_status(
            old.constraint_status.get(constraint, mathopt_mod.BasisStatus.BASIC),
            constraint.lower_bound,
            constraint.upper_bound,
        )
    return basis


class GLOP(LpSolver_API):
    """
    The OR-Tools GLOP simplex LP solver (via the MathOpt Python API).

    GLOP solves linear programs only: a problem with integer variables needs
    ``mip=False``, which solves its LP relaxation.

    The model is kept between solves, so :meth:`~pulp.LpProblem.resolve`
    updates it and restarts from the previous basis. ``prob.solverModel`` is
    a :class:`GlopModel`: the MathOpt model, its incremental solver and the
    result of the last solve.
    """

    name = "GLOP"

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        threads=None,
        logPath=None,
        warmStart=False,
        msgCallback: Callable[[list[str]], None] | None = None,
        interrupter: Any = None,
        **solverParams,
    ):
        """
        :param bool mip: if False, integer variables are relaxed to continuous
            ones; if True, a problem with integer variables cannot be solved
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param int threads: sets the maximum number of threads
        :param str logPath: path to write the solver log to
        :param bool warmStart: ignored, GLOP takes no starting solution; use
            ``prob.resolve`` to restart from the previous basis
        :param msgCallback: called with each batch of log lines (a list of
            str) as the solver writes them. GLOP has no other callbacks.
        :param interrupter: an ``ortools.util.python.solve_interrupter.SolveInterrupter``;
            calling its ``interrupt()`` (e.g. from another thread or from
            ``msgCallback``) stops the solve
        :param dict solverParams: fields of MathOpt's ``SolveParameters``
            (e.g. ``iteration_limit``, ``presolve=False``,
            ``lp_algorithm="dual_simplex"``) or of ``GlopParameters`` (e.g.
            ``use_dual_simplex``, ``primal_feasibility_tolerance``)
        """
        LpSolver.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            threads=threads,
            logPath=logPath,
            warmStart=warmStart,
            **solverParams,
        )
        self.msgCallback = msgCallback
        self.interrupter = interrupter

    def available(self) -> bool:
        """True if the solver is available"""
        return mathopt_mod is not None

    def canUpdate(self, lp: LpProblem) -> bool:
        return isinstance(lp.solverModel, GlopModel)

    @requires("ortools.math_opt.python.mathopt")
    def buildSolverModel(self, lp: LpProblem) -> None:
        """
        Takes the pulp lp model and translates it into a MathOpt model solved
        by GLOP.

        The whole model is written as one ``ModelProto``: adding the variables,
        constraints and coefficients one by one costs far more.
        """
        if self.mip and (lp.isMIP() or lp.has_sos()):
            raise PulpSolverError(
                "GLOP is an LP solver: pass mip=False to solve the LP relaxation"
            )
        if self.optionsDict.get("warmStart", False):
            warnings.warn("GLOP takes no starting solution: warmStart ignored")

        log.debug("create the MathOpt model")
        proto = model_pb2_mod.ModelProto(name=lp.name)
        variables = lp.variables()
        proto_vars = proto.variables
        proto_vars.ids.extend(var.id for var in variables)
        proto_vars.lower_bounds.extend(var.lowBound for var in variables)
        proto_vars.upper_bounds.extend(var.upBound for var in variables)
        proto_vars.integers.extend(False for _ in variables)
        proto_vars.names.extend(var.name for var in variables)

        objective = proto.objective
        objective.maximize = lp.sense == constants.LpMaximize
        objective.offset = lp.objective.constant
        terms = sorted(
            (var.id, coefficient)
            for var, coefficient in lp.objective.items()
            if coefficient != 0
        )
        objective.linear_coefficients.ids.extend(j for j, _ in terms)
        objective.linear_coefficients.values.extend(a for _, a in terms)

        constraints = sorted(lp.constraints(), key=lambda c: c.id)
        proto_rows = proto.linear_constraints
        matrix = proto.linear_constraint_matrix
        for constraint in constraints:
            lb = constraint.getLb()
            ub = constraint.getUb()
            proto_rows.ids.append(constraint.id)
            proto_rows.lower_bounds.append(-math.inf if lb is None else lb)
            proto_rows.upper_bounds.append(math.inf if ub is None else ub)
            proto_rows.names.append(constraint.name)
            row = sorted(
                (var.id, coefficient)
                for var, coefficient in constraint.items()
                if coefficient != 0
            )
            matrix.row_ids.extend(constraint.id for _ in row)
            matrix.column_ids.extend(j for j, _ in row)
            matrix.coefficients.extend(a for _, a in row)

        try:
            model = mathopt_mod.Model.from_model_proto(proto)
            solver = mathopt_mod.IncrementalSolver(model, mathopt_mod.SolverType.GLOP)
        except (AttributeError, RuntimeError, ValueError) as err:
            raise _glop_error(err) from None
        lp.solverModel = GlopModel(model, solver)
        self.configureSolver(lp)
        self._start_tracking(lp)

    @requires("ortools.math_opt.python.mathopt")
    def configureSolver(self, lp: LpProblem) -> None:
        """Set the ``SolveParameters`` of ``lp.solverModel`` from the options,
        again on every resolve so that options changed in between take effect."""
        params = mathopt_mod.SolveParameters(enable_output=bool(self.msg))
        if self.timeLimit is not None:
            params.time_limit = datetime.timedelta(seconds=self.timeLimit)
        param_fields = {field.name for field in dataclasses.fields(params)}
        glop_fields = glop_parameters_pb2_mod.GlopParameters.DESCRIPTOR.fields_by_name
        for key, value in self.optionsDict.items():
            if key in ("warmStart", "logPath"):
                continue
            if key in _GLOP_ENUM_PARAMS:
                enum = getattr(mathopt_mod, _GLOP_ENUM_PARAMS[key])
                if isinstance(value, bool):
                    # True leaves the solver's default
                    value = None if value else mathopt_mod.Emphasis.OFF
                elif isinstance(value, str):
                    value = enum[value.upper()]
            if key in param_fields:
                setattr(params, key, value)
            elif key in glop_fields:
                setattr(params.glop, key, value)
            else:
                raise PulpSolverError(f"GLOP: unknown parameter {key!r}")
        glop = lp.solverModel
        assert glop is not None
        glop.params = params

    @requires("ortools.math_opt.python.mathopt")
    def callSolver(
        self,
        lp: LpProblem,
        *,
        changes: _rustcore.ModelChanges | None = None,
        **kwargs: Any,
    ) -> None:
        """Solves the problem with GLOP; the result is kept in ``lp.solverModel``."""
        glop = lp.solverModel
        assert glop is not None
        log_path = self.optionsDict.get("logPath")
        log_file = open(log_path, "w") if log_path else None
        msg_cb = None
        # the solver stops printing its log once it is handed a message
        # callback, which then prints it with msg=True
        if log_file is not None or self.msgCallback is not None:

            def msg_cb(lines: list[str]) -> None:
                if log_file is not None:
                    log_file.writelines(line + "\n" for line in lines)
                if self.msg:
                    sys.stdout.writelines(line + "\n" for line in lines)
                if self.msgCallback is not None:
                    self.msgCallback(lines)

        # a model just built has no result yet, so it starts without a basis
        basis = _warm_basis(glop)
        model_params = (
            None
            if basis is None
            else mathopt_mod.ModelSolveParameters(initial_basis=basis)
        )
        try:
            glop.result = glop.solver.solve(
                params=glop.params,
                model_params=model_params,
                msg_cb=msg_cb,
                interrupter=self.interrupter,
            )
        except (AttributeError, RuntimeError, ValueError) as err:
            raise _glop_error(err) from None
        finally:
            if log_file is not None:
                log_file.close()

    @requires("ortools.math_opt.python.mathopt")
    def applyChanges(self, lp: LpProblem, changes: _rustcore.ModelChanges) -> None:
        """Update ``lp.solverModel`` with the edits made to ``lp`` since it was
        last solved (``changes``, from :meth:`_take_changes`). The incremental
        solver hands them to GLOP, which keeps its basis.

        Variables and constraints keep their pulp ids in the MathOpt model.
        """
        model = lp.solverModel.model
        rmodel = lp._model
        new_cols = changes.new_cols
        new_rows = changes.new_rows
        if self.mip and any(
            rmodel.get_variable(j).category == _rustcore.Category.Integer
            for j in [*new_cols, *changes.var_category]
        ):
            # the rebuild says GLOP cannot solve it
            raise _RebuildNeeded
        if (new_cols and min(new_cols) < model.get_next_variable_id()) or (
            new_rows and min(new_rows) < model.get_next_linear_constraint_id()
        ):
            raise _RebuildNeeded

        def variable(j: int) -> Any:
            return model.get_variable(j, validate=False)

        def row(i: int) -> Any:
            return model.get_linear_constraint(i, validate=False)

        if changes.sense_changed:
            model.objective.is_maximize = lp.sense == constants.LpMaximize

        # entries of new columns in existing rows go with the columns
        old_entries, columns = self._split_coefficients(
            lp, changes, model.get_next_variable_id()
        )
        for j in new_cols:
            rvar = rmodel.get_variable(j)
            model.ensure_next_variable_id_at_least(j)
            var = model.add_variable(lb=rvar.lb, ub=rvar.ub, name=rvar.name)
            for i, value in zip(*columns.get(j, ([], []))):
                row(i).set_coefficient(var, value)

        for i in new_rows:
            rconstr = rmodel.get_constraint(i)
            lb, ub = _row_bounds(rconstr)
            model.ensure_next_linear_constraint_id_at_least(i)
            constraint = model.add_linear_constraint(lb=lb, ub=ub, name=rconstr.name)
            for rvar, coefficient in rconstr.items():
                if coefficient != 0:
                    constraint.set_coefficient(variable(rvar.id()), coefficient)

        for i, j, value in old_entries:
            row(i).set_coefficient(variable(j), value)

        for i in changes.row_bounds:
            constraint = row(i)
            constraint.lower_bound, constraint.upper_bound = _row_bounds(
                rmodel.get_constraint(i)
            )

        for j in changes.var_bounds:
            rvar = rmodel.get_variable(j)
            var = variable(j)
            var.lower_bound = rvar.lb
            var.upper_bound = rvar.ub

        if changes.objective_replaced:
            cols = list(range(model.get_next_variable_id()))
            objective = lp.objective
            model.objective.offset = 0.0 if objective is None else objective.constant
        else:
            cols = [*changes.obj_coeffs, *new_cols]
        for j, cost in zip(cols, rmodel.objective_coefficients(cols)):
            model.objective.set_linear_coefficient(variable(j), cost)

    @requires("ortools.math_opt.python.mathopt")
    def findSolutionValues(
        self, lp: LpProblem, result: Any = None
    ) -> tuple[constants.LpSolveStatus, bool]:
        """Reads the result of the last solve from ``lp.solverModel``."""
        result = lp.solverModel.result
        termination = result.termination
        reason = termination.reason
        TR = mathopt_mod.TerminationReason
        Limit = mathopt_mod.Limit
        S = constants.LpSolveStatus
        if reason in (TR.FEASIBLE, TR.NO_SOLUTION_FOUND):
            limit = termination.limit
            if limit == Limit.UNDETERMINED:
                # GLOP does not say which limit stopped it: the one that was reached
                params = lp.solverModel.params
                stats = result.solve_stats
                if (
                    params.iteration_limit is not None
                    and stats.simplex_iterations >= params.iteration_limit
                ):
                    limit = Limit.ITERATION
                elif (
                    params.time_limit is not None
                    and stats.solve_time >= params.time_limit
                ):
                    limit = Limit.TIME
            status = {
                Limit.TIME: S.TimeLimit,
                Limit.ITERATION: S.IterationLimit,
                Limit.INTERRUPTED: S.Interrupted,
                Limit.OBJECTIVE: S.GapLimit,
            }.get(limit, S.Stopped)
        elif reason == TR.INFEASIBLE_OR_UNBOUNDED:
            # presolve may not tell them apart, the feasibility statuses may
            problem = termination.problem_status
            Feasibility = mathopt_mod.FeasibilityStatus
            if problem.primal_status == Feasibility.INFEASIBLE:
                status = S.Infeasible
            elif (
                problem.primal_status == Feasibility.FEASIBLE
                and problem.dual_status == Feasibility.INFEASIBLE
            ):
                status = S.Unbounded
            else:
                status = S.Undefined
        else:
            status = {
                TR.OPTIMAL: S.Optimal,
                TR.INFEASIBLE: S.Infeasible,
                TR.UNBOUNDED: S.Unbounded,
            }.get(reason, S.Undefined)

        # variable j and constraint i of the MathOpt model have the pulp ids
        has_solution = result.has_primal_feasible_solution()
        if has_solution:
            lp._model.set_variable_values(
                [(var.id, value) for var, value in result.variable_values().items()]
            )
            lp._model.set_constraint_slacks(
                [(c.id, -(c.value() or 0.0)) for c in lp.constraints()]
            )
        if result.has_dual_feasible_solution():
            lp._model.set_variable_djs(
                [(var.id, value) for var, value in result.reduced_costs().items()]
            )
            lp._model.set_constraint_pis(
                [(c.id, value) for c, value in result.dual_values().items()]
            )
        return status, has_solution and status != S.Unbounded
