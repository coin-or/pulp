from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from .. import _rustcore
from .. import constants as const
from .. import mps_lp as mpslp
from ._internal import _const_to_rust_sense, _rust_sense_to_const
from .lp_affine_expression import LpAffineExpression
from .lp_variable import LpVariable


class LpConstraint:
    """LP constraint backed by Rust for a row already stored in the model.

    Instances appear in :attr:`LpProblem.constraints` as a list in model order; they are not
    pending expressions and must not be combined with ``+`` / ``-`` on affine
    expressions. Use :meth:`copy` to obtain a pending :class:`LpAffineExpression`.
    """

    # Causes numpy to defer comparisons to our __le__/__ge__/__eq__
    __array_priority__ = 20

    def __init__(self, _constr: _rustcore.Constraint) -> None:
        self._constr: _rustcore.Constraint = _constr

    @property
    def _expr(self) -> _rustcore.AffineExpr:
        """Build a Rust AffineExpr from this constraint's data (for arithmetic interop)."""
        expr = _rustcore.AffineExpr()
        for var, coeff in self._constr.items():
            expr.add_term(var, coeff)
        expr.set_constant(-self._constr.rhs)
        expr.set_sense(_const_to_rust_sense(self.sense))
        return expr

    @property
    def pi(self) -> float | None:
        return self._constr.pi

    @pi.setter
    def pi(self, v: float | None) -> None:
        if v is not None:
            self._constr.set_pi(v)

    @property
    def slack(self) -> float | None:
        return self._constr.slack

    @slack.setter
    def slack(self, v: float | None) -> None:
        if v is not None:
            self._constr.set_slack(v)

    @property
    def name(self) -> str:
        return self._constr.name

    @name.setter
    def name(self, value: str | None) -> None:
        self._constr.set_name(value or "")

    @property
    def constant(self) -> float:
        val = -self._constr.rhs
        return 0.0 if val == 0.0 else val

    @property
    def sense(self) -> int:
        return _rust_sense_to_const(self._constr.sense)

    @property
    def id(self) -> int:
        """Index of this constraint in the model's constraint list (from ModelCore)."""
        return self._constr.id()

    def _normalized_rhs(self) -> float:
        val = -self._constr.rhs
        return 0.0 if val == 0.0 else val

    def items(self) -> list[tuple[LpVariable, float]]:
        return [(LpVariable(v), c) for v, c in self._constr.items()]

    def keys(self) -> list[LpVariable]:
        return [v for v, _ in self.items()]

    def values(self) -> list[float]:
        return [c for _, c in self.items()]

    def __getitem__(self, key: LpVariable) -> float:
        for v, c in self.items():
            if v is key or (v.name == key.name):
                return c
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, LpVariable):
            return any(v is key or v.name == key.name for v, _ in self.items())
        if isinstance(key, str):
            return any(v.name == key for v, _ in self.items())
        return any(v is key for v, _ in self.items())

    def __iter__(self) -> Iterator[LpVariable]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._constr.items())

    def getLb(self) -> float | None:
        if (self.sense == const.LpConstraintGE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        return None

    def getUb(self) -> float | None:
        if (self.sense == const.LpConstraintLE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        return None

    @staticmethod
    def _count_characters(line: list[str]) -> int:
        return sum(len(t) for t in line)

    def _asCplexVariablesOnly(self, name: str) -> tuple[list[str], list[str]]:
        return self._expr.as_cplex_variables_only(name)

    def __str__(self) -> str:
        return self._expr.str_with_sense()

    def __repr__(self) -> str:
        return self._expr.repr_expr()

    def asCplexLpConstraint(self, name: str) -> str:
        return self._expr.as_cplex_lp_constraint(name)

    def asCplexLpAffineExpression(
        self, name: str, include_constant: bool = True
    ) -> str:
        return self._expr.as_cplex_lp_affine_expression(name, include_constant)

    def changeRHS(self, RHS: float) -> None:
        raise NotImplementedError("Cannot change RHS of constraint already in model")

    def addInPlace(self, other: Any, sign: Literal[+1, -1] = 1) -> LpAffineExpression:
        raise NotImplementedError(
            "Cannot modify constraint already in model; use a pending constraint (e.g. expr <= rhs) for in-place ops"
        )

    def copy(self) -> LpAffineExpression:
        """Return a pending LpAffineExpression copy with sense set."""
        expr = _rustcore.AffineExpr()
        for var, coeff in self._constr.items():
            expr.add_term(var, coeff)
        expr.set_constant(-self._constr.rhs)
        expr.set_sense(_const_to_rust_sense(self.sense))
        return LpAffineExpression(expr)

    def emptyCopy(self) -> LpAffineExpression:
        e = LpAffineExpression.empty()
        e.sense = self.sense
        return e

    def valid(self, eps: float = 0) -> bool:
        val = self.value()
        if val is None:
            return False
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        return val * self.sense >= -eps

    def toDataclass(self) -> mpslp.MPSConstraint:
        return mpslp.MPSConstraint(
            sense=self.sense,
            pi=self.pi,
            constant=self.constant,
            name=self.name,
            coefficients=[
                mpslp.MPSCoefficient(name=k.name, value=v) for k, v in self.items()
            ],
        )

    def isAtomic(self) -> bool:
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self) -> bool:
        return len(self) == 0

    def atom(self) -> LpVariable | None:
        items = self.items()
        return items[0][0] if items else None

    def __bool__(self) -> bool:
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def get(self, key: LpVariable, default: float | None = None) -> float | None:
        for v, c in self.items():
            if v is key or (v.name == key.name):
                return c
        return default

    def value(self) -> float | None:
        return self._expr.value()

    def valueOrDefault(self) -> float:
        return self._expr.value_or_default()
