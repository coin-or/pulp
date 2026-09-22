"""Statistics describing a single solve.

:class:`LpSolveStats` is what :meth:`~pulp.LpProblem.solve` returns when called with
``stats=True``: why the solver stopped, whether a usable solution came back, how long
it took, and -- when a solver log was produced and ``orloge`` is installed -- a good
deal of detail read back out of that log.
"""

from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING, Any

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

from .. import constants as const

if TYPE_CHECKING:
    from ..apis.core import LpSolver


_FEASIBLE_SOLUTIONS = (const.LpSolutionOptimal, const.LpSolutionIntegerFeasible)

# orloge payload key -> LpSolveStats field
_LOG_FIELDS = {
    "version": "solver_version",
    "status": "solver_status",
    "status_code": "solver_status_code",
    "sol_code": "solver_sol_code",
    "time": "solver_time",
    "gap": "solver_gap",
    "nodes": "nodes",
    "rootTime": "root_time",
    "presolve": "presolve",
    "matrix": "matrix",
    "matrix_post": "matrix_post",
    "cut_info": "cut_info",
    "first_relaxed": "first_relaxed",
    "first_solution": "first_solution",
}


def parse_logs(log_path: str | None, dialect: str | None) -> dict[str, Any] | None:
    """Parse the solver log at ``log_path`` with orloge.

    Returns ``None`` when there is no log, when the solver speaks a dialect orloge
    does not know, or when orloge is not installed. Parsing is best effort: a log
    orloge chokes on yields ``None`` rather than failing an otherwise good solve.

    :param log_path: path to the log file the solver wrote
    :param dialect: orloge log dialect, e.g. ``"CBC"``; see
        :py:attr:`~pulp.apis.core.LpSolver.logDialect`
    """
    if not log_path or not dialect or not os.path.isfile(log_path):
        return None
    try:
        import orloge  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return orloge.get_info_solver(log_path, dialect)
    except Exception:
        pass
    try:
        # Building the progress table is the fragile part of the parse and it
        # depends on orloge's own optional extras; everything else is still worth
        # having when it breaks.
        return orloge.get_info_solver(log_path, dialect, get_progress=False)
    except Exception:
        return None


@dataclasses.dataclass
class LpSolveStats:
    """Everything known about one solve.

    The first group of fields is always filled in. The second group is read out of
    the solver log and stays ``None`` when no log could be parsed.

    :param solver: name of the solver that ran, e.g. ``"COIN_CMD"``
    :param status: why the solver stopped, a :data:`~pulp.constants.LpStatus` code
    :param sol_status: what came back, a :data:`~pulp.constants.LpSolution` code
    :param time: wall-clock seconds spent solving
    :param cpu_time: CPU seconds spent solving
    :param objective: objective value of the returned solution, if any
    :param best_bound: best bound the solver proved, if known
    :param num_variables: variables in the model handed to the solver
    :param num_constraints: constraints in the model handed to the solver
    :param is_mip: whether the model was solved as a mixed integer program
    :param solver_options: the options the solver ran with
    :param solver_version: solver version string, from the log
    :param solver_status: stop reason as the solver itself worded it
    :param solver_status_code: orloge status code. Unlike :attr:`status` it can say
        that a run hit the time limit (-4) or the memory limit (-5)
    :param solver_sol_code: orloge solution code
    :param solver_time: solve time as the solver reported it
    :param solver_gap: relative gap as the solver reported it
    :param nodes: branch and bound nodes explored
    :param root_time: seconds spent on the root relaxation
    :param presolve: what presolve removed
    :param matrix: constraint, variable and non-zero counts
    :param matrix_post: the same counts after presolve
    :param cut_info: cuts applied and what they bought
    :param first_relaxed: value of the first relaxation
    :param first_solution: value of the first integer solution found
    :param logs: the whole orloge payload, including the progress table
    """

    # always available
    solver: str = "LpSolver"
    status: int = const.LpStatusNotSolved
    sol_status: int = const.LpSolutionNoSolutionFound
    time: float = 0.0
    cpu_time: float = 0.0
    objective: float | None = None
    best_bound: float | None = None
    num_variables: int = 0
    num_constraints: int = 0
    is_mip: bool = False
    solver_options: dict[str, Any] = dataclasses.field(default_factory=dict)

    # read out of the parsed log
    solver_version: str | None = None
    solver_status: str | None = None
    solver_status_code: int | None = None
    solver_sol_code: int | None = None
    solver_time: float | None = None
    solver_gap: float | None = None
    nodes: int | None = None
    root_time: float | None = None
    presolve: dict[str, Any] | None = None
    matrix: dict[str, Any] | None = None
    matrix_post: dict[str, Any] | None = None
    cut_info: dict[str, Any] | None = None
    first_relaxed: float | None = None
    first_solution: float | None = None
    logs: dict[str, Any] | None = None

    @property
    def status_str(self) -> str:
        """Human readable reason the solver stopped, e.g. ``"Optimal"``."""
        return const.LpStatus.get(self.status, "Unknown")

    @property
    def sol_status_str(self) -> str:
        """Human readable description of the solution, e.g. ``"Optimal Solution Found"``."""
        return const.LpSolution.get(self.sol_status, "Unknown")

    @property
    def feasible(self) -> int:
        """1 if the solver returned a usable solution, 0 otherwise."""
        return int(self.sol_status in _FEASIBLE_SOLUTIONS)

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
            because it holds a pandas DataFrame of solver progress, which does not
            survive a round trip through JSON. Every field promoted out of it, such
            as :attr:`nodes` or :attr:`solver_version`, is included either way.
        """
        data = {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)
            if f.name != "logs"
        }
        data.update(
            status_str=self.status_str,
            sol_status_str=self.sol_status_str,
            feasible=self.feasible,
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
            f"solution: {self.sol_status_str} ({self.sol_status})",
            f"feasible: {self.feasible}",
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
        """Copy the orloge payload onto the log-derived fields."""
        self.logs = logs
        if logs is None:
            return
        for key, field_name in _LOG_FIELDS.items():
            value = logs.get(key)
            if value is not None:
                setattr(self, field_name, value)
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
