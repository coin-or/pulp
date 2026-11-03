from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .. import constants
from .core import LpSolver_API, PulpSolverError, import_optional, requires

if TYPE_CHECKING:
    from .. import _rustcore
    from ..core.lp_problem import LpProblem

clarabel_mod = import_optional("clarabel")
np = import_optional("numpy")
sparse = import_optional("scipy.sparse")

# looked up by name: older clarabel versions lack some statuses
_status_names = {
    "Unsolved": constants.LpSolveStatus.NotSolved,
    "Solved": constants.LpSolveStatus.Optimal,
    "AlmostSolved": constants.LpSolveStatus.Optimal,
    "PrimalInfeasible": constants.LpSolveStatus.Infeasible,
    "AlmostPrimalInfeasible": constants.LpSolveStatus.Infeasible,
    "DualInfeasible": constants.LpSolveStatus.Unbounded,
    "AlmostDualInfeasible": constants.LpSolveStatus.Unbounded,
    "MaxIterations": constants.LpSolveStatus.IterationLimit,
    "MaxTime": constants.LpSolveStatus.TimeLimit,
    "CallbackTerminated": constants.LpSolveStatus.Interrupted,
    "NumericalError": constants.LpSolveStatus.NumericalError,
    "InsufficientProgress": constants.LpSolveStatus.NumericalError,
}


class CLARABEL(LpSolver_API):
    """
    The Clarabel interior point solver (via its python interface).

    Clarabel solves linear programs only: a problem with integer variables
    needs ``mip=False``, which solves its LP relaxation. It has no warm start,
    so a resolve builds the model again.

    The Clarabel ``DefaultSolver`` is available (after a solve) in
    ``prob.solverModel``.
    """

    # https://clarabel.org
    name = "CLARABEL"
    # print_to_file sends the log to the file instead of the console
    logPathSilencesMsg = True

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        threads=None,
        logPath=None,
        **solverParams,
    ):
        """
        :param bool mip: if False, integer variables are relaxed to continuous
            ones; if True, a problem with integer variables cannot be solved
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param int threads: sets the maximum number of threads
        :param str logPath: path to the log file; the log goes there instead of
            the console
        :param dict solverParams: fields of Clarabel's ``DefaultSettings``
            (e.g. ``max_iter``, ``tol_gap_rel``, ``presolve_enable``)
        """
        super().__init__(
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            logPath=logPath,
            **solverParams,
        )
        self.threads = threads

    def available(self):
        return clarabel_mod is not None and np is not None and sparse is not None

    def _settings(self) -> Any:
        """The ``DefaultSettings`` from the solver options."""
        settings = clarabel_mod.DefaultSettings()
        settings.verbose = bool(self.msg) or "logPath" in self.optionsDict
        if self.timeLimit is not None:
            settings.time_limit = float(self.timeLimit)
        if self.threads is not None:
            settings.max_threads = self.threads
        for key, value in self.optionsDict.items():
            if key == "logPath":
                continue
            setattr(settings, key, value)
        return settings

    @requires("clarabel", "numpy", "scipy.sparse")
    def buildSolverModel(self, lp: LpProblem) -> None:
        """
        Takes the pulp lp model and translates it into a Clarabel model:
        minimize ``q'x`` subject to ``Ax + s = b``, with ``s`` in a cone.

        Column j is the variable with id j and row i the constraint with id i,
        a ``>=`` row negated into a ``<=`` one. The finite variable bounds come
        after them, as rows too: Clarabel has no variable bounds.
        """
        if self.mip and lp.isMIP():
            raise PulpSolverError(
                "CLARABEL is an LP solver: pass mip=False to solve the LP relaxation"
            )
        variables = lp.variables()
        q = np.zeros(len(variables))
        for var, coefficient in lp.objective.items():
            q[var.id] = coefficient
        if lp.sense == constants.LpMaximize:
            q = -q

        rows: list[int] = []
        cols: list[int] = []
        values: list[float] = []
        b: list[float] = []
        # whether each row is an equality (zero cone) or not (nonnegative cone)
        equality: list[bool] = []

        def add_row(row: list[tuple[int, float]], rhs: float, is_eq: bool) -> None:
            for j, value in row:
                rows.append(len(b))
                cols.append(j)
                values.append(value)
            b.append(rhs)
            equality.append(is_eq)

        for constraint in lp.constraints():
            sign = -1.0 if constraint.sense == constants.LpConstraintGE else 1.0
            add_row(
                [(var.id, sign * a) for var, a in constraint.items() if a != 0],
                -sign * constraint.constant,
                constraint.sense == constants.LpConstraintEQ,
            )
        for var in variables:
            lb, ub = var.lowBound, var.upBound
            if lb == ub:
                add_row([(var.id, 1.0)], lb, True)
                continue
            if math.isfinite(ub):
                add_row([(var.id, 1.0)], ub, False)
            if math.isfinite(lb):
                add_row([(var.id, -1.0)], -lb, False)

        # one cone per run of rows of the same kind
        cones: list[Any] = []
        start = 0
        for i in range(1, len(equality) + 1):
            if i == len(equality) or equality[i] != equality[start]:
                cone = (
                    clarabel_mod.ZeroConeT
                    if equality[start]
                    else clarabel_mod.NonnegativeConeT
                )
                cones.append(cone(i - start))
                start = i

        n = len(variables)
        A = sparse.csc_matrix((values, (rows, cols)), shape=(len(b), n))
        P = sparse.csc_matrix((n, n))
        lp.solverModel = clarabel_mod.DefaultSolver(
            P, q, A, np.array(b, dtype=np.float64), cones, self._settings()
        )

    @requires("clarabel")
    def callSolver(
        self,
        lp: LpProblem,
        *,
        changes: _rustcore.ModelChanges | None = None,
        **kwargs: Any,
    ) -> Any:
        """Solves the problem with Clarabel, stopping when the ``callback``
        given to solve (called with Clarabel's ``DefaultInfo`` on every
        iteration) returns True; returns the ``DefaultSolution``."""
        model = lp.solverModel
        logPath = self.optionsDict.get("logPath")
        if logPath is not None:
            model.print_to_file(str(logPath))
        callback = kwargs.get("callback")
        if callback is not None:
            model.set_termination_callback(callback)
        return model.solve()

    def findSolutionValues(
        self, lp: LpProblem, result: Any = None
    ) -> tuple[constants.LpSolveStatus, bool]:
        """:param result: the ``DefaultSolution`` that :meth:`callSolver` returned"""
        S = constants.LpSolveStatus
        clarabelStatus = {
            getattr(clarabel_mod.SolverStatus, name): status
            for name, status in _status_names.items()
            if hasattr(clarabel_mod.SolverStatus, name)
        }
        status = clarabelStatus.get(result.status, S.Undefined)
        # an interior point iterate stopped early is not feasible
        has_solution = status == S.Optimal
        if not has_solution:
            return status, has_solution
        # column j is the variable with id j, row i the constraint with id i.
        # The values only meet their bounds within tolerance: snap them inside
        variables = lp.variables()
        values = np.clip(
            result.x,
            [var.lowBound for var in variables],
            [var.upBound for var in variables],
        )
        lp._model.set_variable_values(list(enumerate(values.tolist())))
        sense = -1.0 if lp.sense == constants.LpMaximize else 1.0
        dj = np.zeros(len(result.x))
        for var, coefficient in lp.objective.items():
            dj[var.id] = coefficient
        for constraint in lp.constraints():
            sign = -1.0 if constraint.sense == constants.LpConstraintGE else 1.0
            i = constraint.id
            constraint.slack = sign * result.s[i]
            # Clarabel's duals satisfy q + A'z = 0: the shadow price of b is -z
            pi = -sense * sign * result.z[i]
            constraint.pi = pi
            for var, coefficient in constraint.items():
                dj[var.id] -= pi * coefficient
        lp._model.set_variable_djs(list(enumerate(dj)))
        return status, has_solution
