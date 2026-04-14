from __future__ import annotations

import dataclasses
import math
import re
from typing import TYPE_CHECKING, Any, Optional

from .. import _rustcore
from .. import mps_lp as mpslp
from ._internal import _rust_cat_to_const

if TYPE_CHECKING:
    from .lp_affine_expression import LpAffineExpression
    from .lp_problem import LpProblem

_ae_cls: type[LpAffineExpression] | None = None


def _affine_expr_cls() -> type[LpAffineExpression]:
    global _ae_cls
    if _ae_cls is None:
        from .lp_affine_expression import LpAffineExpression

        _ae_cls = LpAffineExpression
    return _ae_cls


class LpVariable:
    """
    Thin wrapper over the Rust Variable. Created only via
    LpProblem.add_variable() or add_variable_dicts/dict/matrix.
    """

    # Causes numpy to defer comparisons (e.g. np.float64(3) >= var) to our __le__/__ge__/__eq__
    __array_priority__ = 20

    illegal_chars = "-+[] ->/"
    expression = re.compile(f"[{re.escape(illegal_chars)}]")
    trans = str.maketrans(illegal_chars, "________")

    def __init__(self, _var: _rustcore.Variable) -> None:
        if _var is None:
            raise TypeError(
                "LpVariable requires a Rust variable (created only by the model)"
            )
        self._var: _rustcore.Variable = _var

    @property
    def name(self) -> str:
        return self._var.name

    @name.setter
    def name(self, value: str) -> None:
        self._var.set_name(value)

    @property
    def id(self) -> int:
        """Index of this variable in the model's variable list (from ModelCore)."""
        return self._var.id()

    def __hash__(self) -> int:
        return hash(self._var.id())

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __neg__(self) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return -AE.from_variable(self)

    def __pos__(self) -> LpVariable:
        return self

    def __bool__(self) -> bool:
        return bool(self.roundedValue())

    def __add__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) + other

    def __radd__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) + other

    def __sub__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) - other

    def __rsub__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return other - AE.from_variable(self)

    def __mul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) * other

    def __rmul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) * other

    def __truediv__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) / other

    def __le__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) <= other

    def __ge__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        AE = _affine_expr_cls()
        return AE.from_variable(self) >= other

    def __eq__(self, other: object):
        if isinstance(other, LpVariable):
            return self._var.id() == other._var.id()
        AE = _affine_expr_cls()
        if isinstance(other, (int, float, AE)):
            return AE.from_variable(self) == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, LpVariable):
            return self._var.id() != other._var.id()
        AE = _affine_expr_cls()
        if isinstance(other, AE):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return True
        else:
            return True

    @property
    def lowBound(self) -> float:
        return self._var.lb

    @lowBound.setter
    def lowBound(self, value: float | None) -> None:
        self._var.set_lb(float("-inf") if value is None else value)

    @property
    def upBound(self) -> float:
        return self._var.ub

    @upBound.setter
    def upBound(self, value: float | None) -> None:
        self._var.set_ub(float("inf") if value is None else value)

    @property
    def cat(self) -> str:
        return _rust_cat_to_const(self._var.category)

    @property
    def varValue(self) -> Optional[float]:
        return self._var.value

    @varValue.setter
    def varValue(self, v: Optional[float]) -> None:
        if v is not None:
            self._var.set_value(v)

    @property
    def _lowbound_original(self) -> Optional[float]:
        return self.lowBound

    @property
    def _upbound_original(self) -> Optional[float]:
        return self.upBound

    @property
    def dj(self) -> float | None:
        return self._var.dj

    @dj.setter
    def dj(self, v: float | None) -> None:
        if v is not None:
            self._var.set_dj(v)

    def toDataclass(self) -> mpslp.MPSVariable:
        """
        Exports a variable into a dataclass with its relevant information

        :return: a :py:class:`mpslp.MPSVariable` with the variable information
        :rtype: :mpslp.MPSVariable
        """
        return mpslp.MPSVariable(
            lowBound=self.lowBound if math.isfinite(self.lowBound) else None,
            upBound=self.upBound if math.isfinite(self.upBound) else None,
            cat=self.cat,
            varValue=self.varValue,
            dj=self.dj,
            name=self.name,
        )

    @classmethod
    def fromDataclass(cls, problem: LpProblem, mps: mpslp.MPSVariable):
        """
        Initializes a variable from a dataclass by adding it to the given problem.

        :param problem: the problem to add the variable to
        :param mps: a :py:class:`mpslp.MPSVariable` with the variable information
        :return: a :py:class:`LpVariable`
        """
        var = problem.add_variable(mps.name, mps.lowBound, mps.upBound, mps.cat)
        if mps.varValue is not None:
            var._var.set_value(mps.varValue)
        return var

    def toDict(self) -> dict[str, Any]:
        """
        Exports a variable into a dict with its relevant information.

        :return: a :py:class:`dict` with the variable information
        :rtype: :dict
        """
        return dataclasses.asdict(self.toDataclass())

    @classmethod
    def fromDict(cls, problem: LpProblem, data: dict[str, Any]):
        """
        Initializes a variable from a dict by adding it to the given problem.

        :param problem: the problem to add the variable to
        :param data: a dict with the variable information
        :return: a :py:class:`LpVariable`
        """
        return cls.fromDataclass(problem, mpslp.MPSVariable.fromDict(data))

    def getLb(self) -> float:
        return self.lowBound

    def getUb(self) -> float:
        return self.upBound

    def bounds(self, low: float | None, up: float | None) -> None:
        self._var.set_lb(low if low is not None else float("-inf"))
        self._var.set_ub(up if up is not None else float("inf"))

    def positive(self) -> None:
        self.bounds(0, float("inf"))

    def value(self) -> float | None:
        return self._var.value

    def round(self, epsInt: float = 1e-5, eps: float = 1e-7) -> None:
        self._var.round_value(epsInt, eps)

    def roundedValue(self, eps: float = 1e-5) -> float | None:
        return self._var.rounded_value(eps)

    def valueOrDefault(self) -> float:
        return self._var.value_or_default()

    def valid(self, eps: float) -> bool:
        return self._var.valid(eps)

    def infeasibilityGap(self, mip: bool = True) -> float:
        return self._var.infeasibility_gap(bool(mip))

    def isBinary(self) -> bool:
        return self._var.is_binary()

    def isInteger(self) -> bool:
        return self._var.is_integer()

    def isFree(self) -> bool:
        return self._var.is_free()

    def isConstant(self) -> bool:
        return self._var.is_constant()

    def isPositive(self) -> bool:
        return self._var.is_positive()

    def asCplexLpVariable(self) -> str:
        return self._var.as_cplex_lp_variable()

    def asCplexLpAffineExpression(
        self, name: str, include_constant: bool = True
    ) -> str:
        AE = _affine_expr_cls()
        return AE.from_variable(self).asCplexLpAffineExpression(name, include_constant)

    def setInitialValue(self, val: float, check: bool = True) -> bool:
        lb = self.lowBound
        ub = self.upBound
        if lb is not None and val < lb:
            if check:
                raise ValueError(
                    "In variable {}, initial value {} is smaller than lowBound {}".format(
                        self.name, val, lb
                    )
                )
            return False
        if ub is not None and val > ub:
            if check:
                raise ValueError(
                    "In variable {}, initial value {} is greater than upBound {}".format(
                        self.name, val, ub
                    )
                )
            return False
        self._var.set_value(val)
        return True

    def fixValue(self) -> None:
        """
        changes lower bound and upper bound to the initial value if exists.
        :return: None
        """
        val = self.varValue
        if val is not None:
            self.bounds(val, val)

    def isFixed(self) -> bool:
        """

        :return: True if upBound and lowBound are the same
        :rtype: bool
        """
        return self.isConstant()

    def unfixValue(self) -> None:
        self.bounds(self._lowbound_original, self._upbound_original)
