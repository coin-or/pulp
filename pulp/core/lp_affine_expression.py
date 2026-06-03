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


class LpAffineExpression:
    """
    Thin wrapper around Rust AffineExpr. A linear combination of LpVariables + constant.
    Optionally carries a constraint sense (for pending constraints created by <=, >=, ==).
    """

    __array_priority__ = 20
    trans = str.maketrans("-+[] ", "_____")

    # ... весь твой существующий код выше (factory-методы, свойства и т.д.) оставляем ...

    def addterm(self, key: LpVariable, value: float | int | Decimal):
        """Add a single term key * value to the expression."""
        # Coerce Decimal to float to keep solver interface in native types
        if isinstance(value, Decimal):
            value = float(value)
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

    # ... здесь твой код __str__, __repr__, asCplex*, и т.д. — не трогаем ...

    def addInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | dict[Any, Any]
        | Iterable[Any]
        | int
        | float
        | Decimal
        | None,
        sign: Literal[+1, -1] = 1,
    ) -> LpAffineExpression:
        """In-place addition/subtraction of various types, with Decimal support."""
        if other is None or (isinstance(other, int) and other == 0):
            return self
        if isinstance(other, LpVariable):
            self.addterm(other, sign)
        elif isinstance(other, LpAffineExpression):
            self._expr.add_expr(other._expr, sign)
            self._expr.combine_sense(other._expr.sense, float(sign))
        elif isinstance(other, dict):
            for e in other.values():
                self.addInPlace(cast(Any, e), sign=sign)
        elif isinstance(other, Iterable) and not isinstance(other, str):
            for e in other:
                self.addInPlace(cast(Any, e), sign=sign)
        elif isinstance(other, (int, float, Decimal)):
            if isinstance(other, Decimal):
                other = float(other)
            if not math.isfinite(other):
                raise const.PulpError("Cannot add/subtract NaN/inf values")
            self._expr.set_constant(self._expr.constant + float(other) * sign)
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
        | Decimal
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
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __radd__(
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __iadd__(
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return self.addInPlace(other)

    def __sub__(
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return self.copy().subInPlace(other)

    def __rsub__(
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return (-self).addInPlace(other)

    def __isub__(
        self, other: LpVariable | LpAffineExpression | int | float | Decimal
    ) -> LpAffineExpression:
        return self.subInPlace(other)

    def __mul__(
        self, other: LpAffineExpression | LpVariable | int | float | Decimal
    ) -> LpAffineExpression:
        """Support multiplication by Decimal as by float."""
        if isinstance(other, Decimal):
            other = float(other)
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
        self, other: LpAffineExpression | LpVariable | int | float | Decimal
    ) -> LpAffineExpression:
        if isinstance(other, Decimal):
            other = float(other)
        return self * other

    def __truediv__(
        self, other: LpAffineExpression | LpVariable | int | float | Decimal
    ) -> LpAffineExpression:
        """Support division by Decimal as by float."""
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
        if isinstance(other, Decimal):
            other = float(other)
        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        e = LpAffineExpression(self._expr.clone_expr())
        e._expr.scale(1.0 / float(other))
        return e

    # дальше твой код __le__, __ge__, __eq__, getLb, getUb, valid, toDataclass, toDict — оставляешь без изменений

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
        return self.toDict()
