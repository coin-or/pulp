from __future__ import annotations

import math
from decimal import Decimal
from collections.abc import Iterable, Iterator
from typing import Any, Literal, cast

from .. import _rustcore
from .. import constants as const
from .. import mps_lp as mpslp
from ._internal import _const_to_rust_sense, _rust_sense_to_const
from .lp_variable import LpVariable


Number = int | float | Decimal


class LpAffineExpression:
    """
    Thin wrapper around Rust AffineExpr.
    A linear combination of LpVariables + constant.
    Optionally carries a constraint sense (for pending constraints created by <=, >=, ==).
    """

    __array_priority__ = 20
    trans = str.maketrans("-+[] ", "_____")

    def __init__(self, _expr: _rustcore.AffineExpr) -> None:
        self._expr: _rustcore.AffineExpr = _expr

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
    def from_constant(cls, value: Number, name: str | None = None) -> LpAffineExpression:
        v = float(value)
        if not math.isfinite(v):
            raise const.PulpError("Cannot create expression from NaN/inf value")
        expr = _rustcore.AffineExpr.from_constant(v)
        cls._set_name(expr, name)
        return cls(expr)

    @classmethod
    def from_dict(
        cls, data: dict[LpVariable, Number], name: str | None = None
    ) -> LpAffineExpression:
        expr = cls.empty(name)
        for var, coeff in data.items():
            expr.addterm(var, coeff)
        return expr

    @classmethod
    def from_list(
        cls, items: Iterable[tuple[LpVariable, Number]], name: str | None = None
    ) -> LpAffineExpression:
        expr = cls.empty(name)
        for var, coeff in items:
            expr.addterm(var, coeff)
        return expr

    def emptyCopy(self) -> LpAffineExpression:
        e = LpAffineExpression.empty()
        if self.sense is not None:
            e.sense = self.sense
        return e

    def copy(self) -> LpAffineExpression:
        e = LpAffineExpression(self._expr.clone_expr())
        if self.sense is not None:
            e.sense = self.sense
        return e

    @staticmethod
    def _to_float(value: Number) -> float:
        v = float(value)
        if not math.isfinite(v):
            raise const.PulpError("Cannot use NaN/inf values in expressions")
        return v

    @staticmethod
    def _str_coeff(c: float) -> str:
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    @staticmethod
    def _fmt_const(c: float) -> str:
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    def addterm(self, key: LpVariable, value: Number) -> None:
        """Add a single term key * value to the expression."""
        self._expr.add_term(key._var, self._to_float(value))

    def addInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | dict[Any, Any]
        | Iterable[Any]
        | Number
        | None,
        sign: Literal[+1, -1] = 1,
    ) -> LpAffineExpression:
        """In-place addition/subtraction."""
        if other is None:
            return self

        if isinstance(other, LpVariable):
            self._expr.add_term(other._var, float(sign))
            return self

        if isinstance(other, LpAffineExpression):
            self._expr.add_expr(other._expr, sign)
            if other.sense is not None:
                self._expr.combine_sense(other._expr.sense, float(sign))
            return self

        if isinstance(other, dict):
            for k, v in other.items():
                if not isinstance(k, LpVariable):
                    raise TypeError(
                        f"Dictionary keys must be LpVariable, got {type(k).__name__}"
                    )
                self.addterm(k, self._to_float(v) * sign)
            return self

        if isinstance(other, Iterable) and not isinstance(other, (str, bytes)):
            for item in other:
                self.addInPlace(cast(Any, item), sign=sign)
            return self

        if isinstance(other, (int, float, Decimal)):
            self._expr.set_constant(self._expr.constant + self._to_float(other) * sign)
            return self

        raise TypeError(
            f"Unsupported type for in-place add/subtract: {type(other).__name__}"
        )

    def subInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | dict[Any, Any]
        | Iterable[Any]
        | Number
        | None,
    ) -> LpAffineExpression:
        return self.addInPlace(other, sign=-1)

    def __neg__(self) -> LpAffineExpression:
        e = self.copy()
        e._expr.scale(-1.0)
        if e.sense is not None:
            e.sense = -e.sense
        return e

    def __pos__(self) -> LpAffineExpression:
        return self

    def __add__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __radd__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __iadd__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return self.addInPlace(other)

    def __sub__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return self.copy().subInPlace(other)

    def __rsub__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return (-self).addInPlace(other)

    def __isub__(
        self, other: LpVariable | LpAffineExpression | Number
    ) -> LpAffineExpression:
        return self.subInPlace(other)

    def __mul__(
        self, other: LpAffineExpression | LpVariable | Number
    ) -> LpAffineExpression:
        if isinstance(other, Decimal):
            other = float(other)

        e = self.emptyCopy()

        if isinstance(other, LpVariable):
            return self * LpAffineExpression.from_variable(other)

        if isinstance(other, LpAffineExpression):
            if len(self) and len(other):
                raise TypeError("Non-constant expressions cannot be multiplied")
            if len(other):
                e._expr = other._expr.clone_expr()
                e._expr.scale(self.constant)
                return e
            if len(self):
                e._expr = self._expr.clone_expr()
                e._expr.scale(other.constant)
                return e
            e._expr = _rustcore.AffineExpr.from_constant(self.constant * other.constant)
            return e

        if not math.isfinite(other):
            raise const.PulpError("Cannot multiply variables with NaN/inf values")

        if other != 0:
            e._expr = self._expr.clone_expr()
            e._expr.scale(float(other))
        return e

    def __rmul__(
        self, other: LpAffineExpression | LpVariable | Number
    ) -> LpAffineExpression:
        return self * other

    def __truediv__(
        self, other: LpAffineExpression | LpVariable | Number
    ) -> LpAffineExpression:
        if isinstance(other, LpVariable):
            raise TypeError("Expressions cannot be divided by a non-constant expression")

        if isinstance(other, LpAffineExpression):
            if len(other):
                raise TypeError("Expressions cannot be divided by a non-constant expression")
            other = other.constant

        if isinstance(other, Decimal):
            other = float(other)

        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        if other == 0:
            raise ZeroDivisionError("division by zero")

        e = self.copy()
        e._expr.scale(1.0 / float(other))
        return e

    def __le__(
        self, other: LpAffineExpression | LpVariable | Number
    ) -> LpAffineExpression:
        if isinstance(other, (int, float, Decimal)):
            result = self.copy()
            result.constant = result.constant - self._to_float(other)
            result.sense = const.LpConstraintLE
            return result
        if isinstance(other, (LpAffineExpression, LpVariable)):
            result = self - other
            result.sense = const.LpConstraintLE
            return result
        return NotImplemented

    def __ge__(
        self, other: LpAffineExpression | LpVariable | Number
    ) -> LpAffineExpression:
        if isinstance(other, (int, float, Decimal)):
            result = self.copy()
            result.constant = result.constant - self._to_float(other)
            result.sense = const.LpConstraintGE
            return result
        if isinstance(other, (LpAffineExpression, LpVariable)):
            result = self - other
            result.sense = const.LpConstraintGE
            return result
        return NotImplemented

    def __eq__(self, other: object) -> LpAffineExpression:  # type: ignore[override]
        if isinstance(other, (int, float, Decimal)):
            result = self.copy()
            result.constant = result.constant - self._to_float(other)
            result.sense = const.LpConstraintEQ
            return result
        if isinstance(other, (LpAffineExpression, LpVariable)):
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

    def changeRHS(self, RHS: Number) -> None:
        self.constant = -self._to_float(RHS)

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
        return self.toDict()