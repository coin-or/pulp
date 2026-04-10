from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Iterator
from typing import Any, Literal

from .. import _rustcore
from .. import constants as const
from .. import mps_lp as mpslp
from ._internal import _const_to_rust_sense, _rust_sense_to_const
from .lp_variable import LpVariable


class LpAffineExpression:
    """
    Thin wrapper around Rust AffineExpr. A linear combination of LpVariables + constant.
    Optionally carries a constraint sense (for pending constraints created by <=, >=, ==).

    Use factory class methods to create instances:
      - LpAffineExpression.empty()
      - LpAffineExpression.from_variable(v)
      - LpAffineExpression.from_constant(c)
      - LpAffineExpression.from_dict({v: coeff, ...})
      - LpAffineExpression.from_list([(v, coeff), ...])
    """

    # Causes numpy to defer comparisons (e.g. np.float64(3) >= expr) to our __le__/__ge__/__eq__
    __array_priority__ = 20

    trans = str.maketrans("-+[] ", "_____")

    def __init__(self, _expr: _rustcore.AffineExpr) -> None:
        self._expr: _rustcore.AffineExpr = _expr

    # -- Factory class methods --

    @classmethod
    def _set_name(cls, expr: _rustcore.AffineExpr, name: str | None) -> None:
        if name:
            expr.set_name(str(name).translate(cls.trans))

    @classmethod
    def empty(cls, name: str | None = None) -> LpAffineExpression:
        expr = _rustcore.AffineExpr()
        cls._set_name(expr, name)
        return cls(expr)

    @classmethod
    def from_variable(
        cls, var: LpVariable, name: str | None = None
    ) -> LpAffineExpression:
        expr = _rustcore.AffineExpr.from_variable(var._var)
        cls._set_name(expr, name)
        return cls(expr)

    @classmethod
    def from_constant(cls, value: float, name: str | None = None) -> LpAffineExpression:
        expr = _rustcore.AffineExpr.from_constant(float(value))
        cls._set_name(expr, name)
        return cls(expr)

    @classmethod
    def from_dict(
        cls, d: dict[LpVariable, float], constant: float = 0.0, name: str | None = None
    ) -> LpAffineExpression:
        expr = _rustcore.AffineExpr()
        expr.set_constant(float(constant))
        for k, v in d.items():
            if isinstance(k, LpVariable):
                expr.add_term(k._var, float(v))
        cls._set_name(expr, name)
        return cls(expr)

    @classmethod
    def from_list(
        cls,
        pairs: list[tuple[LpVariable, float]],
        constant: float = 0.0,
        name: str | None = None,
    ) -> LpAffineExpression:
        expr = _rustcore.AffineExpr()
        expr.set_constant(float(constant))
        for k, v in pairs:
            if isinstance(k, LpVariable):
                expr.add_term(k._var, float(v))
        cls._set_name(expr, name)
        return cls(expr)

    # -- Properties delegating to Rust --

    @property
    def name(self) -> str | None:
        return self._expr.name

    @name.setter
    def name(self, value: str | None):
        if value:
            self._expr.set_name(str(value).translate(self.trans))
        else:
            self._expr.clear_name()

    @property
    def constant(self) -> float:
        return self._expr.constant

    @constant.setter
    def constant(self, value: float):
        self._expr.set_constant(float(value))

    @property
    def sense(self) -> int | None:
        rs = self._expr.sense
        if rs is None:
            return None
        return _rust_sense_to_const(rs)

    @sense.setter
    def sense(self, value: int | None):
        if value is None:
            self._expr.clear_sense()
        else:
            self._expr.set_sense(_const_to_rust_sense(value))

    def items(self) -> list[tuple[LpVariable, float]]:
        raw = self._expr.items()
        return [(LpVariable(v), float(c)) for v, c in raw]

    def keys(self) -> list[LpVariable]:
        return [LpVariable(v) for v in self._expr.keys()]

    def values(self) -> list[float]:
        return list(self._expr.values())

    def __iter__(self) -> Iterator[LpVariable]:
        return iter(self.keys())

    def __len__(self) -> int:
        return self._expr.num_terms()

    def __getitem__(self, key: LpVariable) -> float:
        if isinstance(key, LpVariable):
            return self._expr.get_coeff(key._var)
        for v, c in self.items():
            if v is key or v.name == key.name:
                return c
        raise KeyError(key)

    def __setitem__(self, key: LpVariable, value: float | int):
        if not isinstance(key, LpVariable):
            raise TypeError("Only LpVariable keys supported")
        old = self._expr.get_coeff(key._var)
        self._expr.add_term(key._var, float(value) - old)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, LpVariable):
            return self._expr.get_coeff(key._var) != 0
        if isinstance(key, str):
            return any(v.name == key for v, _ in self.items())
        return any(v is key for v, _ in self.items())

    def get(self, key: LpVariable, default: float | None = None) -> float | None:
        try:
            return self[key]
        except KeyError:
            return default

    def isAtomic(self) -> bool:
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self) -> bool:
        return len(self) == 0

    def atom(self) -> LpVariable:
        return next(iter(self.keys()))

    def __bool__(self) -> bool:
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def value(self) -> float | None:
        return self._expr.value()

    def valueOrDefault(self) -> float:
        return self._expr.value_or_default()

    def addterm(self, key: LpVariable, value: float | int):
        self._expr.add_term(key._var, float(value))

    def emptyCopy(self) -> LpAffineExpression:
        e = LpAffineExpression.empty()
        if self.sense is not None:
            e.sense = self.sense
        return e

    def copy(self) -> LpAffineExpression:
        return LpAffineExpression(self._expr.clone_expr())

    @staticmethod
    def _str_coeff(c: float) -> str:
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    @staticmethod
    def _fmt_const(c: float) -> str:
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    def _str_expr(
        self, include_constant: bool = True, override_constant: float | None = None
    ) -> str:
        if override_constant is not None:
            saved = self.constant
            self.constant = override_constant
            result = self._expr.str_expr(include_constant)
            self.constant = saved
            return result
        return self._expr.str_expr(include_constant)

    def __str__(
        self, include_constant: bool = True, override_constant: float | None = None
    ) -> str:
        if self.sense is not None:
            s = self._str_expr(include_constant=False)
            rhs = -self.constant if override_constant is None else -override_constant
            s += " " + const.LpConstraintSenses[self.sense] + " " + str(float(rhs))
            return s
        return self._str_expr(include_constant, override_constant)

    def __repr__(self, override_constant: float | None = None) -> str:
        if override_constant is not None:
            saved = self.constant
            self.constant = override_constant
            result = self._expr.repr_expr()
            self.constant = saved
            return result
        return self._expr.repr_expr()

    @staticmethod
    def _count_characters(line: list[str]) -> int:
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name: str) -> tuple[list[str], list[str]]:
        return self._expr.as_cplex_variables_only(name)

    def asCplexLpAffineExpression(
        self,
        name: str,
        include_constant: bool = True,
        override_constant: float | None = None,
    ) -> str:
        if override_constant is not None:
            saved = self.constant
            self.constant = override_constant
            result = self._expr.as_cplex_lp_affine_expression(name, include_constant)
            self.constant = saved
            return result
        return self._expr.as_cplex_lp_affine_expression(name, include_constant)

    def asCplexLpConstraint(self, name: str) -> str:
        return self._expr.as_cplex_lp_constraint(name)

    def addInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | dict[Any, Any]
        | Iterable[Any]
        | int
        | float
        | None,
        sign: Literal[+1, -1] = 1,
    ) -> LpAffineExpression:
        from .lp_constraint import LpConstraint

        if other is None or (isinstance(other, int) and other == 0):
            return self
        if isinstance(other, LpVariable):
            self.addterm(other, sign)
        elif isinstance(other, LpAffineExpression):
            self._expr.add_expr(other._expr, sign)
            self._expr.combine_sense(other._expr.sense, float(sign))
        elif isinstance(other, LpConstraint):
            raise TypeError(
                "Cannot add or subtract an LpConstraint; use .copy() for a pending expression"
            )
        elif isinstance(other, dict):
            for e in other.values():
                self.addInPlace(e, sign=sign)  # type: ignore[arg-type]
        elif isinstance(other, Iterable) and not isinstance(other, str):
            for e in other:
                self.addInPlace(e, sign=sign)  # type: ignore[arg-type]
        elif isinstance(other, (int, float)):
            if not math.isfinite(other):
                raise const.PulpError("Cannot add/subtract NaN/inf values")
            self._expr.set_constant(self._expr.constant + other * sign)
        else:
            raise TypeError(
                f"Unsupported type for in-place add/subtract: {type(other).__name__}"
            )
        return self

    def subInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | dict[Any, Any]
        | Iterable[Any]
        | int
        | float
        | None,
    ) -> LpAffineExpression:
        return self.addInPlace(other, sign=-1)

    def __neg__(self) -> LpAffineExpression:
        e = LpAffineExpression(self._expr.clone_expr())
        e._expr.scale(-1.0)
        return e

    def __pos__(self) -> LpAffineExpression:
        return self

    def __add__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __radd__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __iadd__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return self.addInPlace(other)

    def __sub__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return self.copy().subInPlace(other)

    def __rsub__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return (-self).addInPlace(other)

    def __isub__(
        self, other: LpVariable | LpAffineExpression | int | float
    ) -> LpAffineExpression:
        return self.subInPlace(other)

    def __mul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        e = LpAffineExpression.empty()
        if isinstance(other, LpAffineExpression):
            e.constant = self.constant * other.constant
            if len(other):
                if len(self):
                    raise TypeError("Non-constant expressions cannot be multiplied")
                e._expr = other._expr.clone_expr()
                e._expr.scale(self.constant)
            else:
                e._expr = self._expr.clone_expr()
                e._expr.scale(other.constant)
        elif isinstance(other, LpVariable):
            return self * LpAffineExpression.from_variable(other)
        else:
            if not math.isfinite(other):
                raise const.PulpError("Cannot multiply variables with NaN/inf values")
            if other != 0:
                e._expr = self._expr.clone_expr()
                e._expr.scale(float(other))
        return e

    def __rmul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return self * other

    def __truediv__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        if isinstance(other, LpVariable):
            raise TypeError(
                "Expressions cannot be divided by a non-constant expression"
            )
        if isinstance(other, LpAffineExpression):
            if len(other):
                raise TypeError(
                    "Expressions cannot be divided by a non-constant expression"
                )
            other = other.constant
        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        e = LpAffineExpression(self._expr.clone_expr())
        e._expr.scale(1.0 / other)
        return e

    def __le__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        if isinstance(other, (int, float)):
            result = self.copy()
            result.constant = result.constant - float(other)
            result.sense = const.LpConstraintLE
            return result
        elif isinstance(other, (LpAffineExpression, LpVariable)):
            result = self - other
            result.sense = const.LpConstraintLE
            return result
        return NotImplemented

    def __ge__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        if isinstance(other, (int, float)):
            result = self.copy()
            result.constant = result.constant - float(other)
            result.sense = const.LpConstraintGE
            return result
        elif isinstance(other, (LpAffineExpression, LpVariable)):
            result = self - other
            result.sense = const.LpConstraintGE
            return result
        return NotImplemented

    def __eq__(self, other: object) -> LpAffineExpression:  # type: ignore[override]
        if isinstance(other, (int, float)):
            result = self.copy()
            result.constant = result.constant - float(other)
            result.sense = const.LpConstraintEQ
            return result
        elif isinstance(other, (LpAffineExpression, LpVariable)):
            result = self - other
            result.sense = const.LpConstraintEQ
            return result
        return NotImplemented

    def _normalized_rhs(self) -> float:
        return self.constant

    def getLb(self) -> float | None:
        if self.sense is not None and (
            self.sense == const.LpConstraintGE or self.sense == const.LpConstraintEQ
        ):
            return -self.constant
        return None

    def getUb(self) -> float | None:
        if self.sense is not None and (
            self.sense == const.LpConstraintLE or self.sense == const.LpConstraintEQ
        ):
            return -self.constant
        return None

    def changeRHS(self, RHS: float) -> None:
        self.constant = -RHS

    def valid(self, eps: float = 0) -> bool:
        val = self.value()
        if val is None:
            return False
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        if self.sense is not None:
            return val * self.sense >= -eps
        return True

    def toDataclass(self) -> list[mpslp.MPSCoefficient]:
        return [mpslp.MPSCoefficient(name=k.name, value=v) for k, v in self.items()]

    def toDict(self) -> list[dict[str, Any]]:
        return [{"name": k.name, "value": v} for k, v in self.items()]

    def to_dict(self) -> list[dict[str, Any]]:
        warnings.warn(
            "LpAffineExpression.to_dict is deprecated, use LpAffineExpression.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()
