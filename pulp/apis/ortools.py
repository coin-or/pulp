from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any

from .. import constants
from .core import LpSolver, PulpSolverError, clock, log

if TYPE_CHECKING:
    from ..core.lp_problem import LpProblem

_ORTOOLS_IMPORT_ERROR: BaseException | None = None
cp_model_mod = None
try:
    from ortools.sat.python import cp_model as cp_model_mod
except Exception as exc:
    _ORTOOLS_IMPORT_ERROR = exc


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


def check_ortools(func):
    """Decorator that checks if ortools is available."""

    def wrapper(self, *args, **kwargs):
        if cp_model_mod is None:
            raise PulpSolverError(f"CPSAT: Not Available:\n{_ORTOOLS_IMPORT_ERROR}")
        return func(self, *args, **kwargs)

    return wrapper


class CPSAT(LpSolver):
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
        **solverParams,
    ):
        """
        :param bool mip: ignored; CP-SAT always solves as a discrete model
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param bool warmStart: if True, pass current variable values as hints
        :param dict solverParams: additional parameters for ``CpSolver.parameters``
        """
        LpSolver.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            warmStart=warmStart,
        )
        self.solver_params = solverParams
        self.solverModel = None

    def available(self) -> bool:
        """True if the solver is available"""
        return cp_model_mod is not None

    @check_ortools
    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> int:
        """
        Solve a well formulated lp problem.

        Creates a CP-SAT model, variables and constraints, then solves it.
        """
        var_handles = self.buildSolverModel(lp)
        log.debug("Solve the Model using CP-SAT")
        solver, status = self.callSolver(lp)
        return self.findSolutionValues(lp, solver, var_handles, status)

    @check_ortools
    def buildSolverModel(self, lp: LpProblem) -> list[Any]:
        """
        Takes the pulp lp model and translates it into a CP-SAT model.

        Returns a list of CP-SAT variable handles aligned with
        ``lp.exported_variables()``.
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
        self.solverModel = lp.solverModel = cp_model_mod.CpModel()

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
                cp_var = self.solverModel.NewBoolVar(var.name)
            elif var.cat == constants.LpInteger:
                lb = int(var.lowBound)
                ub = int(var.upBound)
                cp_var = self.solverModel.NewIntVar(lb, ub, var.name)
            elif var.cat == constants.LpContinuous:
                lb = math.ceil(var.lowBound)
                ub = math.floor(var.upBound)
                if lb > ub:
                    raise PulpSolverError(
                        f"Variable {var.name!r} has empty integer domain after "
                        f"converting continuous bounds [{var.lowBound}, {var.upBound}]"
                    )
                cp_var = self.solverModel.NewIntVar(lb, ub, var.name)
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
                        self.solverModel.AddHint(
                            var_handles[j], bool(round(hint_value))
                        )
                    else:
                        self.solverModel.AddHint(var_handles[j], int(round(hint_value)))
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
                    self.solverModel.Maximize(obj_expr)
                else:
                    self.solverModel.Minimize(obj_expr)

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
                self.solverModel.Add(expr <= int_rhs)
            elif constraint.sense == constants.LpConstraintGE:
                self.solverModel.Add(expr >= int_rhs)
            elif constraint.sense == constants.LpConstraintEQ:
                self.solverModel.Add(expr == int_rhs)
            else:
                raise PulpSolverError("Detected an invalid constraint type")

        return var_handles

    @check_ortools
    def callSolver(self, lp: LpProblem) -> tuple[Any, Any]:
        """Solves the problem with CP-SAT and returns the solver and status."""
        solver = cp_model_mod.CpSolver()
        if not self.msg:
            solver.parameters.log_search_progress = False
        if self.timeLimit is not None:
            solver.parameters.max_time_in_seconds = float(self.timeLimit)
        for param, value in self.solver_params.items():
            if hasattr(solver.parameters, param):
                setattr(solver.parameters, param, value)

        self.solveTime = -clock()
        status = solver.Solve(self.solverModel)
        self.solveTime += clock()
        return solver, status

    @check_ortools
    def findSolutionValues(
        self,
        lp: LpProblem,
        solver: Any,
        var_handles: list[Any],
        status_code: Any,
    ) -> int:
        exported_vars = list(lp.exported_variables())
        cp_status = {
            cp_model_mod.OPTIMAL: constants.LpStatusOptimal,
            cp_model_mod.FEASIBLE: constants.LpStatusOptimal,
            cp_model_mod.INFEASIBLE: constants.LpStatusInfeasible,
            cp_model_mod.UNKNOWN: constants.LpStatusNotSolved,
            cp_model_mod.MODEL_INVALID: constants.LpStatusUndefined,
        }
        sol_status = {
            cp_model_mod.FEASIBLE: constants.LpSolutionIntegerFeasible,
        }
        status = cp_status.get(status_code, constants.LpStatusUndefined)
        lp.assignStatus(status, sol_status.get(status_code))

        if status_code in (cp_model_mod.OPTIMAL, cp_model_mod.FEASIBLE):
            values = {
                var.name: solver.Value(cp_var)
                for var, cp_var in zip(exported_vars, var_handles)
            }
            lp.assignVarsVals(values)

        return status
