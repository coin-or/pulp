"""Statistics describing a single solve.

:class:`LpSolveStats` is what :meth:`~pulp.LpProblem.solve` returns when called with
``stats=True``: why the solver stopped, whether a usable solution came back, how long
it took, and -- when the solver produced a log ``orloge`` can read -- a good deal of
detail read back out of that log.
"""

from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING, Any

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

import orloge

from .. import constants as const

if TYPE_CHECKING:
    from ..apis.core import LpSolver


#: solution codes that mean the solver handed back a usable solution
FEASIBLE_SOLUTIONS = (const.LpSolutionOptimal, const.LpSolutionIntegerFeasible)

#: orloge dialect each solver's log speaks, keyed by :attr:`~pulp.apis.core.LpSolver.name`.
#: Solvers left out here have no orloge parser; :func:`dialect_for_solver` returns
#: ``None`` for them and :func:`parse_logs` then skips parsing entirely.
LOG_DIALECTS: dict[str, str] = {
    "COIN_CMD": "CBC",
    "CPLEX_CMD": "CPLEX",
    "CPLEX_PY": "CPLEX",
    "GUROBI": "GUROBI",
    "GUROBI_CMD": "GUROBI",
    "CPSAT": "CPSAT",
}

# LpSolveStats properties backed by the orloge payload (see LpSolveStats._log_get)
_LOG_PROPERTIES = (
    "solver_version",
    "solver_status",
    "solver_status_code",
    "solver_sol_code",
    "solver_time",
    "solver_gap",
    "nodes",
    "root_time",
    "presolve",
    "matrix",
    "matrix_post",
    "cut_info",
    "first_relaxed",
    "first_solution",
)


def dialect_for_solver(solver_name: str) -> str | None:
    """orloge dialect the named solver's log speaks, or ``None`` if orloge can't read it.

    :param solver_name: :attr:`~pulp.apis.core.LpSolver.name` of the solver, e.g.
        ``"COIN_CMD"``
    """
    return LOG_DIALECTS.get(solver_name)


def parse_logs(log_path: str | None, dialect: str | None) -> dict[str, Any] | None:
    """Parse the solver log at ``log_path`` with orloge.

    Returns ``None`` when there is no log or when the solver speaks a dialect orloge
    does not know. Parsing is best effort: a log orloge chokes on yields ``None``
    rather than failing an otherwise good solve.

    :param log_path: path to the log file the solver wrote
    :param dialect: orloge log dialect, e.g. ``"CBC"``; see
        :func:`dialect_for_solver`
    """
    if not log_path or not dialect or not os.path.isfile(log_path):
        return None
    try:
        return orloge.get_info_solver(log_path, dialect)
    except Exception:
        pass
    try:
        # Building the progress table is the fragile part of the parse; everything
        # else is still worth having when it breaks.
        return orloge.get_info_solver(log_path, dialect, get_progress=False)
    except Exception:
        return None


@dataclasses.dataclass
class LpSolveStats:
    """Everything known about one solve.

    The fields below are always filled in, straight from the solver and the
    problem. Everything orloge can read out of the solver log stays in :attr:`logs`
    as-is -- the whole payload, unmodified -- and is exposed through read-only
    properties (:attr:`solver_version`, :attr:`nodes`, :attr:`matrix`, ...) that
    read out of it lazily. Those properties fall back to ``None`` when there is no
    log, or orloge could not parse it.

    :param solver: name of the solver that ran, e.g. ``"COIN_CMD"``
    :param status: why the solver stopped, a :data:`~pulp.constants.LpStatus` code
    :param has_solution: whether the solver found a feasible solution and handed it
        back
    :param time: wall-clock seconds spent solving
    :param cpu_time: CPU seconds spent solving
    :param objective: objective value of the returned solution, if any
    :param best_bound: best bound the solver proved, if known
    :param num_variables: variables in the model handed to the solver
    :param num_constraints: constraints in the model handed to the solver
    :param is_mip: whether the model was solved as a mixed integer program
    :param solver_options: the options the solver ran with
    :param logs: the whole orloge payload, including the progress table as a list
        of one dataclass per row
    """

    # always available
    solver: str = "LpSolver"
    status: int = const.LpStatusNotSolved
    has_solution: bool = False
    time: float = 0.0
    cpu_time: float = 0.0
    objective: float | None = None
    best_bound: float | None = None
    num_variables: int = 0
    num_constraints: int = 0
    is_mip: bool = False
    solver_options: dict[str, Any] = dataclasses.field(default_factory=dict)
    logs: dict[str, Any] | None = None

    def _log_get(self, key: str) -> Any:
        """Read one key out of the orloge payload, treating ``{}`` as "not found"."""
        if not self.logs:
            return None
        value = self.logs.get(key)
        # orloge reports "nothing found" as {} for some dict fields, e.g. cut_info
        return value if value not in (None, {}) else None

    @property
    def solver_version(self) -> str | None:
        """Solver version string, from the log."""
        return self._log_get("version")

    @property
    def solver_status(self) -> str | None:
        """Stop reason as the solver itself worded it."""
        return self._log_get("status")

    @property
    def solver_status_code(self) -> int | None:
        """orloge status code. Unlike :attr:`status` it can say that a run hit the
        time limit (-4) or the memory limit (-5)."""
        return self._log_get("status_code")

    @property
    def solver_sol_code(self) -> int | None:
        """orloge solution code."""
        return self._log_get("sol_code")

    @property
    def solver_time(self) -> float | None:
        """Solve time as the solver reported it."""
        return self._log_get("time")

    @property
    def solver_gap(self) -> float | None:
        """Relative gap as the solver reported it."""
        return self._log_get("gap")

    @property
    def nodes(self) -> int | None:
        """Branch and bound nodes explored."""
        return self._log_get("nodes")

    @property
    def root_time(self) -> float | None:
        """Seconds spent on the root relaxation."""
        return self._log_get("rootTime")

    @property
    def presolve(self) -> dict[str, Any] | None:
        """What presolve removed."""
        return self._log_get("presolve")

    @property
    def matrix(self) -> dict[str, Any] | None:
        """Constraint, variable and non-zero counts."""
        return self._log_get("matrix")

    @property
    def matrix_post(self) -> dict[str, Any] | None:
        """The same counts as :attr:`matrix`, after presolve."""
        return self._log_get("matrix_post")

    @property
    def cut_info(self) -> dict[str, Any] | None:
        """Cuts applied and what they bought."""
        return self._log_get("cut_info")

    @property
    def first_relaxed(self) -> float | None:
        """Value of the first relaxation."""
        return self._log_get("first_relaxed")

    @property
    def first_solution(self) -> dict[str, Any] | None:
        """The first integer solution found: its ``BestInteger`` value, and the
        ``Node``, ``NodesLeft`` and ``CutsBestBound`` at that point."""
        return self._log_get("first_solution")

    @property
    def status_str(self) -> str:
        """Human readable reason the solver stopped, e.g. ``"Optimal"``."""
        return const.LpStatus.get(self.status, "Unknown")

    @property
    def gap_abs(self) -> float | None:
        """Absolute distance between the solution and the best bound, if both are known."""
        if self.objective is None or self.best_bound is None:
            return None
        return abs(self.objective - self.best_bound)

    @property
    def gap_rel(self) -> float | None:
        """Relative gap between the solution and the best bound.

        Falls back to the gap the solver reported when the bound is unknown.
        """
        gap = self.gap_abs
        if gap is None or self.objective is None:
            return self.solver_gap
        if self.objective == 0:
            return 0.0 if gap == 0 else float("inf")
        return gap / abs(self.objective)

    def toDict(self, logs: bool = False) -> dict[str, Any]:
        """Return the statistics as a plain dictionary.

        :param logs: include the raw orloge payload. It is left out by default
            because its progress table holds one dataclass per row. Every field
            promoted out of it, such as :attr:`nodes` or :attr:`solver_version`, is
            included either way.
        """
        data = {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)
            if f.name != "logs"
        }
        for name in _LOG_PROPERTIES:
            data[name] = getattr(self, name)
        data.update(
            status_str=self.status_str,
            gap_abs=self.gap_abs,
            gap_rel=self.gap_rel,
        )
        if logs:
            data["logs"] = self.logs
        return data

    to_dict = toDict

    def toJson(self, filename: str, *args: Any, **kwargs: Any) -> None:
        """Write the statistics to ``filename`` as JSON, without the raw log."""
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    to_json = toJson

    def __str__(self) -> str:
        name = self.solver
        if self.solver_version:
            name += f" ({self.solver_version})"
        lines = [
            f"solver: {name}",
            f"status: {self.status_str} ({self.status})",
            f"has solution: {self.has_solution}",
            f"objective: {self.objective}",
        ]
        if self.best_bound is not None:
            lines.append(f"best bound: {self.best_bound}")
        gap = self.gap_rel
        if gap is not None:
            lines.append(f"gap: {gap:.4%}")
        lines.append(f"time: {self.time:.4f}s (cpu {self.cpu_time:.4f}s)")
        if self.nodes is not None:
            lines.append(f"nodes: {self.nodes}")
        return "\n".join(lines)

    def fill_from_logs(self, logs: dict[str, Any] | None) -> None:
        """Store the orloge payload; :attr:`logs`-derived properties read out of it."""
        self.logs = logs
        if logs is None:
            return
        # the solver itself is the better source for these two; only fall back
        if self.objective is None:
            self.objective = logs.get("best_solution")
        if self.best_bound is None:
            self.best_bound = logs.get("best_bound")

    def fill_from_problem(self, lp: Any, solver: LpSolver) -> None:
        """Copy across what is read off the problem and the solver after a solve."""
        self.solver = solver.name
        self.solver_options = solver.toDict()
        self.num_variables = lp.numVariables()
        self.num_constraints = lp.numConstraints()
        self.is_mip = bool(lp.isMIP())
        objective = lp.objective
        if objective is not None:
            self.objective = objective.value()
