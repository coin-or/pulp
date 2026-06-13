"""
Shared solver test infrastructure for pulp unit tests.
"""

import functools
import os
import unittest
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar, Type

import pulp.apis as solvers
from pulp import (
    LpConstraint,
    LpProblem,
    PulpSolverError,
    lpSum,
)
from pulp import constants as const
from pulp.constants import PulpError

try:
    import gurobipy as gp  # type: ignore[import-not-found, import-untyped]
except ImportError:
    gp = None  # type: ignore[assignment]

EXAMPLE_MPS_RHS56 = """NAME          TESTPROB
ROWS
 N  COST
 L  LIM1
 G  LIM2
 E  MYEQN
COLUMNS
    XONE      COST                 1   LIM1                 1
    XONE      LIM2                 1
    YTWO      COST                 4   LIM1                 1
    YTWO      MYEQN               -1
    ZTHREE    COST                 9   LIM2                 1
    ZTHREE    MYEQN                1
RHS
    RHS1      LIM1                 5   LIM2                10
    RHS1      MYEQN                7
BOUNDS
 UP BND1      XONE                 4
 LO BND1      YTWO                -1
 UP BND1      YTWO                 1
ENDATA
"""

EXAMPLE_MPS_PL_BOUNDS = EXAMPLE_MPS_RHS56.replace(
    "LO BND1      YTWO                -1", "PL BND1      YTWO                  "
)

EXAMPLE_MPS_MI_BOUNDS = EXAMPLE_MPS_RHS56.replace(
    "LO BND1      YTWO                -1", "MI BND1      YTWO                  "
)


def gurobi_test(test_item):
    @functools.wraps(test_item)
    def skip_wrapper(test_obj, *args, **kwargs):
        if test_obj.solver.name not in ["GUROBI", "GUROBI_CMD"]:
            # if we're not testing gurobi, we do not care on the licence
            return test_item(test_obj, *args, **kwargs)
        if gp is None:
            raise unittest.SkipTest("No gurobipy, can't check license")
        try:
            return test_item(test_obj, *args, **kwargs)
        except gp.GurobiError as ge:
            # Skip the test if the failure was due to licensing
            if ge.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
                raise unittest.SkipTest("Size-limited Gurobi license")
            if ge.errno == gp.GRB.Error.NO_LICENSE:
                raise unittest.SkipTest("No Gurobi license")
            # Otherwise, let the error go through as-is
            raise

    return skip_wrapper


def dumpTestProblem(prob):
    try:
        prob.writeLP("debug.lp")
        prob.writeMPS("debug.mps")
    except Exception:
        pass


def _constraint_named(prob: LpProblem, name: str) -> LpConstraint:
    """Return the constraint with the given name (first match)."""
    for c in prob.constraints():
        if c.name == name:
            return c
    raise KeyError(name)


@dataclass(frozen=True)
class PulpTestConfig:
    skip: bool = False
    skip_reason: str | None = None
    okstatus: tuple[int, ...] | None = None
    sol: Any = None
    reducedcosts: Any = None
    duals: Any = None
    slacks: Any = None
    objective: float | None = None
    solve_kwargs: dict[str, Any] = field(default_factory=dict)
    expect_pulp_error: bool | None = None
    allow_pulp_error: bool | None = None
    check_log_path: bool = False
    warm_start: bool = False
    set_mip_zero: bool = False

    def merge(self, other: "PulpTestConfig") -> "PulpTestConfig":
        merged: dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            ov = getattr(other, f)
            dv = getattr(self, f)
            if f == "solve_kwargs":
                merged[f] = {**dv, **ov}
            elif ov is not None and ov is not False and ov != () and ov != {}:
                merged[f] = ov
            elif f == "skip" and ov:
                merged[f] = True
            elif f in ("expect_pulp_error", "allow_pulp_error"):
                merged[f] = ov if ov is not None else dv
            elif (
                f
                in (
                    "check_log_path",
                    "warm_start",
                    "set_mip_zero",
                )
                and ov
            ):
                merged[f] = ov
            else:
                merged[f] = dv
        return PulpTestConfig(**merged)


# CMD/API backends that export duplicate names (e.g. last wins in MPS) without raising.
ALLOW_REPEATED_VAR_NAMES = PulpTestConfig(expect_pulp_error=False)


def _status(*names: str) -> tuple[int, ...]:
    return tuple(getattr(const, n) for n in names)


DEFAULT_PULP_TEST_CONFIGS: dict[str, PulpTestConfig] = {
    "test_infeasible": PulpTestConfig(
        okstatus=_status(
            "LpStatusInfeasible", "LpStatusNotSolved", "LpStatusUndefined"
        ),
    ),
    "test_empty": PulpTestConfig(
        okstatus=_status("LpStatusOptimal", "LpStatusNotSolved"),
        sol={},
    ),
    "test_continuous": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"),
        sol="std_lp",
    ),
    "test_continuous_max": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"),
        sol="std_lp_max",
    ),
    "test_unbounded": PulpTestConfig(
        okstatus=_status("LpStatusUnbounded", "LpStatusUndefined"),
    ),
    "test_long_var_name": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"),
        sol="std_lp",
    ),
    "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
    "test_zero_constraint": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_lp"
    ),
    "test_no_objective": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
    "test_variable_as_objective": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
    "test_longname_lp": PulpTestConfig(skip=True, skip_reason="COIN_CMD only"),
    "test_divide": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol="std_lp"),
    "test_mip": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol="std_mip"),
    "test_mip_floats_objective": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_mip", objective=64.95
    ),
    "test_initial_value": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_mip"
    ),
    "test_fixed_value": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_mip_fixed"
    ),
    "test_relaxed_mip": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_mip_relaxed", set_mip_zero=True
    ),
    "test_feasibility_only": PulpTestConfig(okstatus=_status("LpStatusOptimal")),
    "test_infeasible_2": PulpTestConfig(okstatus=_status("LpStatusInfeasible")),
    "test_integer_infeasible": PulpTestConfig(okstatus=_status("LpStatusInfeasible")),
    "test_integer_infeasible_2": PulpTestConfig(
        okstatus=_status("LpStatusInfeasible", "LpStatusUndefined")
    ),
    "test_dual_variables_reduced_costs": PulpTestConfig(skip=True),
    "test_sequential_solve": PulpTestConfig(skip=True),
    "test_msg_arg": PulpTestConfig(okstatus=_status("LpStatusOptimal"), sol="std_lp"),
    "test_logPath": PulpTestConfig(skip=True),
    "test_unset_objective_value__is_valid": PulpTestConfig(
        okstatus=_status("LpStatusOptimal")
    ),
    "test_infeasible_problem__is_not_valid": PulpTestConfig(
        okstatus=_status("LpStatusInfeasible", "LpStatusUndefined")
    ),
    "test_invalid_var_names": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="std_lp"
    ),
    "test_options_parsing_SCIP_HIGHS": PulpTestConfig(skip=True),
    "test_decimal_815": PulpTestConfig(
        okstatus=_status("LpStatusOptimal"), sol="decimal_815"
    ),
}


def pulpTestCheck(
    prob,
    solver,
    okstatus,
    sol=None,
    reducedcosts=None,
    duals=None,
    slacks=None,
    eps=10**-3,
    status=None,
    objective=None,
    **kwargs,
):
    if status is None:
        status = prob.solve(solver, **kwargs)
    if status not in okstatus:
        dumpTestProblem(prob)
        raise PulpError(
            "Tests failed for solver {}:\nstatus == {} not in {}\nstatus == {} not in {}".format(
                solver,
                status,
                okstatus,
                const.LpStatus[status],
                [const.LpStatus[s] for s in okstatus],
            )
        )
    if sol is not None:
        for v, x in sol.items():
            if v.varValue is not None and abs(v.varValue - x) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nvar {} == {} != {}".format(
                        solver, v, v.varValue, x
                    )
                )
    if reducedcosts:
        for v, dj in reducedcosts.items():
            if abs(v.dj - dj) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nTest failed: var.dj {} == {} != {}".format(
                        solver, v, v.dj, dj
                    )
                )
    if duals:
        for cname, p in duals.items():
            c = _constraint_named(prob, cname)
            if abs(c.pi - p) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nconstraint.pi {} == {} != {}".format(
                        solver, cname, c.pi, p
                    )
                )
    if slacks:
        for cname, slack in slacks.items():
            c = _constraint_named(prob, cname)
            if abs(c.slack - slack) > eps:
                dumpTestProblem(prob)
                raise PulpError(
                    "Tests failed for solver {}:\nconstraint.slack {} == {} != {}".format(
                        solver, cname, c.slack, slack
                    )
                )
    if objective is not None:
        z = prob.objective.value()
        if abs(z - objective) > eps:
            dumpTestProblem(prob)
            raise PulpError(
                f"Tests failed for solver {solver}:\nobjective {z} != {objective}"
            )


class BaseSolverTest:
    class PuLPTest(unittest.TestCase):
        solveInst: Type[solvers.LpSolver] | None = None
        solver: solvers.LpSolver
        pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {}

        def setUp(self):
            if self.solveInst == solvers.CUOPT:
                self.solver = self.solveInst(msg=False, timeLimit=120)
            else:
                self.solver = self.solveInst(msg=False)
            if not self.solver.available():
                self.skipTest(f"solver {self.solveInst.name} not available")

        def tearDown(self):
            for ext in ["mst", "log", "lp", "mps", "sol", "out"]:
                filename = f"{self._testMethodName}.{ext}"
                try:
                    os.remove(filename)
                except Exception:
                    pass

        def _config(self, method: str) -> PulpTestConfig:
            default = DEFAULT_PULP_TEST_CONFIGS.get(method, PulpTestConfig())
            overrides = type(self).pulp_test_overrides.get(method)
            if overrides is None:
                return default
            return default.merge(overrides)

        def _sol_map(self, prob: LpProblem, key: str) -> dict:
            if key == "std_lp":
                x, y, z, w = ({v.name: v for v in prob.variables()}[n] for n in "xyzw")
                return {x: 4, y: -1, z: 6, w: 0}
            if key == "std_lp_max":
                x, y, z, w = ({v.name: v for v in prob.variables()}[n] for n in "xyzw")
                return {x: 4, y: 1, z: 8, w: 0}
            if key == "std_mip":
                x, y, z = ({v.name: v for v in prob.variables()}[n] for n in "xyz")
                return {x: 3, y: -0.5, z: 7}
            if key == "std_mip_fixed":
                x, y, z = ({v.name: v for v in prob.variables()}[n] for n in "xyz")
                return {x: 4, y: -0.5, z: 7}
            if key == "std_mip_relaxed":
                x, y, z = ({v.name: v for v in prob.variables()}[n] for n in "xyz")
                return {x: 3.5, y: -1, z: 6.5}
            if key == "decimal_815":
                x, y = ({v.name: v for v in prob.variables()}[n] for n in "xy")
                return {x: 2.15686, y: 11.4706}
            raise KeyError(key)

        def _apply_pulp_check(
            self,
            prob: LpProblem,
            *,
            method: str | None = None,
            sol: dict | None = None,
            okstatus: list[int] | None = None,
            **extra,
        ) -> None:
            method = self._testMethodName if method is None else method
            cfg = self._config(method)
            if cfg.skip:
                self.skipTest(cfg.skip_reason or method)
            setup_fn = getattr(self, f"setup_{method}", None)
            if setup_fn is not None:
                setup_fn(prob)
            if cfg.set_mip_zero:
                self.solver.mip = 0
            if cfg.warm_start:
                self.solver.optionsDict["warmStart"] = True
            if sol is None and isinstance(cfg.sol, str):
                sol = self._sol_map(prob, cfg.sol)
            elif sol is None and cfg.sol is not None:
                sol = cfg.sol
            status_list = (
                okstatus
                if okstatus is not None
                else (
                    list(cfg.okstatus)
                    if cfg.okstatus is not None
                    else [const.LpStatusOptimal]
                )
            )
            check_extra = dict(extra)
            reducedcosts = check_extra.pop("reducedcosts", cfg.reducedcosts)
            duals = check_extra.pop("duals", cfg.duals)
            slacks = check_extra.pop("slacks", cfg.slacks)
            solve_kwargs = {**cfg.solve_kwargs, **check_extra}
            if cfg.expect_pulp_error is True:

                def _run():
                    pulpTestCheck(
                        prob,
                        self.solver,
                        status_list,
                        sol=sol,
                        reducedcosts=reducedcosts,
                        duals=duals,
                        slacks=slacks,
                        objective=cfg.objective,
                        **solve_kwargs,
                    )

                self.assertRaises((PulpError, PulpSolverError), _run)
                return
            if cfg.allow_pulp_error is True:
                try:
                    pulpTestCheck(
                        prob,
                        self.solver,
                        status_list,
                        sol=sol,
                        reducedcosts=reducedcosts,
                        duals=duals,
                        slacks=slacks,
                        objective=cfg.objective,
                        **solve_kwargs,
                    )
                except PulpError:
                    pass
                return
            pulpTestCheck(
                prob,
                self.solver,
                status_list,
                sol=sol,
                reducedcosts=reducedcosts,
                duals=duals,
                slacks=slacks,
                objective=cfg.objective,
                **solve_kwargs,
            )
            if cfg.check_log_path:
                log_filename = self._testMethodName + ".log"
                if not os.path.exists(log_filename):
                    raise PulpError(f"Test failed for solver: {self.solver}")
                if not os.path.getsize(log_filename):
                    raise PulpError(f"Test failed for solver: {self.solver}")

        def test_continuous(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_continuous_max(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: 1, z: 8, w: 0}
            )

        def test_decimal_815(self):
            # See: https://github.com/coin-or/pulp/issues/815
            # Will not run on other solvers due to how results are updated
            m1 = 3
            m2 = Decimal("8.1")
            extra = 5
            prob = LpProblem("graph", const.LpMaximize)

            x = prob.add_variable("x", lowBound=0, upBound=50, cat=const.LpContinuous)
            y = prob.add_variable(
                "y", lowBound=0, upBound=Decimal("32.24"), cat=const.LpContinuous
            )
            include_extra = prob.add_variable("include_extra1", cat=const.LpBinary)

            prob += y

            # y = 3x + 5 | y = 3x
            e1 = x * m1 + include_extra * extra - y
            c1 = e1 == 0
            prob += c1

            # y = 8.1x - 6
            e2 = x * m2 - 6 - y
            c2 = e2 == 0
            prob += c2

            # This generates two possible systems of equations,
            # y = 3x + 5
            # y = 8.1x - 6
            # this intersects at ~(11/5, 58/5)

            # OR
            # y = 3x
            # y = 8.1x-6
            # this intersects at ~(6/5, 18/5)
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 2.15686, y: 11.4706},
            )

        def test_divide(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += ((2 * x + 2 * y) / 2.0) <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )

        def test_dual_variables_reduced_costs(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 5)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            c1 = x + y <= 5
            c2 = x + z >= 10
            c3 = -y + z == 7
            prob += x + 4 * y + 9 * z, "obj"
            prob += c1, "c1"
            prob += c2, "c2"
            prob += c3, "c3"
            self._apply_pulp_check(
                prob,
                sol={x: 4, y: -1, z: 6},
                reducedcosts={x: 0, y: 12, z: 0},
                duals={"c1": 0, "c2": 1, "c3": 8},
                slacks={"c1": 2, "c2": 0, "c3": 0},
            )

        def test_empty(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal, const.LpStatusNotSolved], {}
            )

        def test_feasibility_only(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_fixed_value(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            solution = {x: 4, y: -0.5, z: 7}
            for v in [x, y, z]:
                v.setInitialValue(solution[v])
                v.fixValue()
            self.solver.optionsDict["warmStart"] = True
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal], solution)

        def test_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += (
                lpSum([v for v in [x] if False]) >= 5,
                "c1",
            )
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob)

        def test_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, 10)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 17.5, "c3"
            self._apply_pulp_check(prob)

        def test_infeasible_problem__is_not_valid(self):
            """Given a problem where x cannot converge to any value
            given conflicting constraints, assert that it is invalid."""
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = prob.add_variable("x")
            prob += 1 * x
            prob += x >= 2
            prob += x <= 1
            self._apply_pulp_check(prob)
            self.assertFalse(prob.valid())

        def test_initial_value(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            x.setInitialValue(3)
            y.setInitialValue(-0.5)
            z.setInitialValue(7)
            self._apply_pulp_check(prob, sol={x: 3, y: -0.5, z: 7})

        def test_integer_infeasible(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4, const.LpInteger)
            y = prob.add_variable("y", -1, 1, const.LpInteger)
            z = prob.add_variable("z", 0, 10, const.LpInteger)
            prob += x + y <= 5.2, "c1"
            prob += x + z >= 10.3, "c2"
            prob += -y + z == 7.4, "c3"
            self._apply_pulp_check(prob)

        def test_integer_infeasible_2(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            dummy = prob.add_variable("dummy")
            c1 = prob.add_variable("c1", 0, 1, const.LpBinary)
            c2 = prob.add_variable("c2", 0, 1, const.LpBinary)
            prob += dummy
            prob += c1 + c2 == 2
            prob += c1 <= 0
            self._apply_pulp_check(prob)

        def test_invalid_var_names(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("a")
            w = prob.add_variable("b")
            y = prob.add_variable("g", -1, 1)
            z = prob.add_variable("End")
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_logPath(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self.solver.optionsDict["logPath"] = self._testMethodName + ".log"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_long_var_name(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x" * 120, 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_longname_lp(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x" * 90, 0, 4)
            y = prob.add_variable("y" * 90, -1, 1)
            z = prob.add_variable("z" * 90, 0)
            w = prob.add_variable("w" * 90, 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_mip(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 3, y: -0.5, z: 7}
            )

        def test_mip_floats_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += 1.1 * x + 4.1 * y + 9.1 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            pulpTestCheck(
                prob,
                self.solver,
                [const.LpStatusOptimal],
                {x: 3, y: -0.5, z: 7},
                objective=64.95,
            )

        def test_msg_arg(self):
            """
            Test setting the msg arg to True does not interfere with solve
            """
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            data = prob.toDict()
            var1, prob1 = LpProblem.fromDict(data)
            x, y, z, w = (var1[name] for name in ["x", "y", "z", "w"])
            pulpTestCheck(
                prob1,
                self.solveInst(msg=True),
                [const.LpStatusOptimal],
                {x: 4, y: -1, z: 6, w: 0},
            )

        def test_no_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_options_parsing_SCIP_HIGHS(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_relaxed_mip(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0, None, const.LpInteger)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7.5, "c3"
            self.solver.mip = 0
            self._apply_pulp_check(prob, sol={x: 3.5, y: -1, z: 6.5})

        def test_repeated_name(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("x", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

        def test_sequential_solve(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 1)
            y = prob.add_variable("y", 0, 1)
            z = prob.add_variable("z", 0, 1)
            obj1 = x + 0 * y + 0 * z
            obj2 = 0 * x - 1 * y + 0 * z
            prob += x <= 1, "c1"
            status = prob.sequentialSolve([obj1, obj2], solver=self.solver)
            self._apply_pulp_check(
                prob,
                sol={x: 0, y: 1},
                okstatus=[[const.LpStatusOptimal, const.LpStatusOptimal]],
                status=status,
            )

        def test_unbounded(self):
            prob = LpProblem(self._testMethodName, const.LpMaximize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z + w, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            self._apply_pulp_check(prob)

        def test_unset_objective_value__is_valid(self):
            """Given a valid problem that does not converge,
            assert that it is still categorised as valid.
            """
            name = self._testMethodName
            prob = LpProblem(name, const.LpMaximize)
            x = prob.add_variable("x")
            prob += 0 * x
            prob += x >= 1
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])
            self.assertTrue(prob.valid())

        def test_variable_as_objective(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob.setObjective(x)
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(prob, self.solver, [const.LpStatusOptimal])

        def test_zero_constraint(self):
            prob = LpProblem(self._testMethodName, const.LpMinimize)
            x = prob.add_variable("x", 0, 4)
            y = prob.add_variable("y", -1, 1)
            z = prob.add_variable("z", 0)
            w = prob.add_variable("w", 0)
            prob += x + 4 * y + 9 * z, "obj"
            prob += x + y <= 5, "c1"
            prob += x + z >= 10, "c2"
            prob += -y + z == 7, "c3"
            prob += w >= 0, "c4"
            prob += lpSum([0, 0]) <= 0, "c5"
            pulpTestCheck(
                prob, self.solver, [const.LpStatusOptimal], {x: 4, y: -1, z: 6, w: 0}
            )


class SASTest:
    def test_sas_with_option(self):
        prob = LpProblem("test", const.LpMinimize)
        X = prob.add_variable_dicts("x", [1, 2, 3], lowBound=0.0, cat="Integer")
        prob += 2 * X[1] - 3 * X[2] - 4 * X[3], "obj"
        prob += -2 * X[2] - 3 * X[3] >= -5, "R1"
        prob += X[1] + X[2] + 2 * X[3] <= 4, "R2"
        prob += X[1] + 2 * X[2] + 3 * X[3] <= 7, "R3"
        self.solver.optionsDict["with"] = "lp"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpStatusOptimal],
            {X[1]: 0.0, X[2]: 2.5, X[3]: 0.0},
        )


def getSortedDict(prob, keyCons="name", keyVars="name"):
    _dict = prob.toDict()
    _dict["constraints"].sort(
        key=lambda v: (v.get(keyCons) is None, str(v.get(keyCons, "")))
    )
    _dict["variables"].sort(
        key=lambda v: (v.get(keyVars) is None, str(v.get(keyVars, "")))
    )
    return _dict
