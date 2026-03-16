#! /usr/bin/env python
# PuLP : Python LP Modeler

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id: pulp.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


"""
PuLP is an linear and mixed integer programming modeler written in Python.

With PuLP, it is simple to create MILP optimisation problems and solve them with the
latest open-source (or proprietary) solvers.  PuLP can generate MPS or LP files and
call solvers such as GLPK_, COIN-OR CLP/`CBC`_, CPLEX_, GUROBI_, MOSEK_, XPRESS_,
CHOCO_, MIPCL_, HiGHS_, SCIP_/FSCIP_.

The documentation for PuLP can be `found here <https://coin-or.github.io/pulp/>`_.

Many examples are shown in the `documentation <https://coin-or.github.io/pulp/CaseStudies/index.html>`_
and pure code examples are available in `examples/ directory <https://github.com/coin-or/pulp/tree/master/examples>`_ .
The examples require at least a solver in your PATH or a shared library file.

Quickstart
------------
Use ``LpProblem`` to create a problem, then add variables with ``add_variable``. Create a
problem and a variable x with 0 ≤ x ≤ 3::

     from pulp import *
     prob = LpProblem("myProblem", LpMinimize)
     x = prob.add_variable("x", 0, 3)

To create a binary variable y (values 0 or 1)::

     y = prob.add_variable("y", cat="Binary")

Combine variables to create expressions and constraints and add them to the problem::

     prob += x + y <= 2

An expression is a constraint without a right-hand side (RHS) sense (one of ``=``,
``<=`` or ``>=``). If you add an expression to a problem, it will become the
objective::

     prob += -4*x + y

To solve the problem  with the default included solver::

     status = prob.solve()

If you want to try another solver to solve the problem::

     status = prob.solve(GLPK(msg = 0))

Display the status of the solution::

     LpStatus[status]
     > 'Optimal'

You can get the value of the variables using ``value``. ex::

     value(x)
     > 2.0

Useful Classes and Functions
-----------------------------

Exported classes:

* ``LpProblem`` -- Container class for a Linear or Integer programming problem
* ``LpVariable`` -- Variables that are added into constraints in the LP problem
* ``LpConstraint`` -- Constraints of the general form

      a1x1 + a2x2 + ... + anxn (<=, =, >=) b

Exported functions:

* ``value()`` -- Finds the value of a variable or expression
* ``lpSum()`` -- Given a list of the form [a1*x1, a2*x2, ..., an*xn] will construct a linear expression to be used as a constraint or variable
* ``lpDot()`` -- Given two lists of the form [a1, a2, ..., an] and [x1, x2, ..., xn] will construct a linear expression to be used as a constraint or variable

Contributing to PuLP
-----------------------
Instructions for making your first contribution to PuLP are given
`here <https://coin-or.github.io/pulp/develop/contribute.html>`_.

**Comments, bug reports, patches and suggestions are very welcome!**

* Comments and suggestions: https://github.com/coin-or/pulp/discussions
* Bug reports: https://github.com/coin-or/pulp/issues
* Patches: https://github.com/coin-or/pulp/pulls

References
----------
[1] http://www.gnu.org/software/glpk/glpk.html
[2] http://www.coin-or.org/
[3] http://www.cplex.com/
[4] http://www.gurobi.com/
[5] http://www.mosek.com/

"""

from __future__ import annotations

import dataclasses
import logging
import math
import re
import warnings
from collections.abc import Iterable, Iterator
from time import time
from typing import Any, Literal, Optional

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

from . import _rustcore
from . import constants as const
from . import mps_lp as mpslp
from .apis import LpSolverDefault
from .apis.core import LpSolver, clock
from .utilities import value

log = logging.getLogger(__name__)


def _is_numpy_bool(obj: object) -> bool:
    """Return True if obj is a numpy boolean scalar (e.g. from np.float64(3) >= var)."""
    t = type(obj)
    return getattr(t, "__name__", "") in ("bool_", "bool8", "bool") and (
        getattr(t, "__module__", "") or ""
    ).startswith("numpy")


def _rust_cat_to_const(rust_cat: _rustcore.Category) -> str:
    if rust_cat == _rustcore.Category.Continuous:
        return const.LpContinuous
    if rust_cat == _rustcore.Category.Integer:
        return const.LpInteger
    if rust_cat == _rustcore.Category.Binary:
        return const.LpInteger  # Binary as Integer 0-1
    return const.LpContinuous


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
        return -LpAffineExpression.from_variable(self)

    def __pos__(self) -> LpVariable:
        return self

    def __bool__(self) -> bool:
        return bool(self.roundedValue())

    def __add__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) + other

    def __radd__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) + other

    def __sub__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) - other

    def __rsub__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return other - LpAffineExpression.from_variable(self)

    def __mul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) * other

    def __rmul__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) * other

    def __truediv__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) / other

    def __le__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) <= other

    def __ge__(
        self, other: LpAffineExpression | LpVariable | int | float
    ) -> LpAffineExpression:
        return LpAffineExpression.from_variable(self) >= other

    def __eq__(self, other: object):
        if isinstance(other, LpVariable):
            return self._var.id() == other._var.id()
        if isinstance(other, (int, float, LpAffineExpression)):
            return LpAffineExpression.from_variable(self) == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, LpVariable):
            return self._var.id() != other._var.id()
        elif isinstance(other, (LpAffineExpression, LpConstraint)):
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
    def fromDataclass(cls, problem: "LpProblem", mps: mpslp.MPSVariable):
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
    def fromDict(cls, problem: "LpProblem", data: dict[str, Any]):
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

    def infeasibilityGap(self, mip: int | bool = True) -> float:
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
        return LpAffineExpression.from_variable(self).asCplexLpAffineExpression(
            name, include_constant
        )

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

    def sorted_keys(self) -> list[LpVariable]:
        return [LpVariable(v) for v in self._expr.sorted_keys()]

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
        | LpConstraint
        | dict[Any, Any]
        | Iterable[Any]
        | int
        | float
        | None,
        sign: Literal[+1, -1] = 1,
    ) -> LpAffineExpression:
        if other is None or (isinstance(other, int) and other == 0):
            return self
        if isinstance(other, LpVariable):
            self.addterm(other, sign)
        elif isinstance(other, LpAffineExpression):
            self._expr.add_expr(other._expr, sign)
            self._expr.combine_sense(other._expr.sense, float(sign))
        elif isinstance(other, LpConstraint):
            self._expr.add_expr(other._expr, sign)
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
        return self

    def subInPlace(
        self,
        other: LpVariable
        | LpAffineExpression
        | LpConstraint
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
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __radd__(
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return self.copy().addInPlace(other)

    def __iadd__(
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return self.addInPlace(other)

    def __sub__(
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return self.copy().subInPlace(other)

    def __rsub__(
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return (-self).addInPlace(other)

    def __isub__(
        self, other: LpVariable | LpAffineExpression | LpConstraint | int | float
    ) -> LpAffineExpression:
        return self.subInPlace(other)

    def __mul__(
        self, other: LpAffineExpression | LpConstraint | LpVariable | int | float
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
        elif isinstance(other, LpConstraint):
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
        self, other: LpAffineExpression | LpConstraint | LpVariable | int | float
    ) -> LpAffineExpression:
        return self * other

    def __truediv__(
        self, other: LpAffineExpression | LpConstraint | LpVariable | int | float
    ) -> LpAffineExpression:
        if isinstance(other, LpVariable):
            raise TypeError(
                "Expressions cannot be divided by a non-constant expression"
            )
        if isinstance(other, (LpAffineExpression, LpConstraint)):
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


def _rust_sense_to_const(rsense: _rustcore.Sense) -> int:
    if rsense == _rustcore.Sense.LessEqual:
        return const.LpConstraintLE
    if rsense == _rustcore.Sense.GreaterEqual:
        return const.LpConstraintGE
    return const.LpConstraintEQ


def _const_to_rust_sense(sense_int: int) -> _rustcore.Sense:
    if sense_int == const.LpConstraintLE:
        return _rustcore.Sense.LessEqual
    if sense_int == const.LpConstraintGE:
        return _rustcore.Sense.GreaterEqual
    return _rustcore.Sense.Equal


class LpConstraint:
    """LP constraint backed by Rust. Only created via LpProblem.addConstraint."""

    # Causes numpy to defer comparisons to our __le__/__ge__/__eq__
    __array_priority__ = 20

    def __init__(self, _constr: _rustcore.Constraint) -> None:
        if _constr is None:
            raise TypeError(
                "LpConstraint requires a Rust Constraint (created only by the model)"
            )
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
    def name(self) -> str | None:
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


class LpProblem:
    """An LP Problem"""

    def __init__(self, name: str = "NoName", sense: int = const.LpMinimize) -> None:
        """
        Creates an LP Problem

        This function creates a new LP Problem  with the specified associated parameters

        :param name: name of the problem used in the output .lp file
        :param sense: of the LP problem objective.  \
                Either :data:`~pulp.const.LpMinimize` (default) \
                or :data:`~pulp.const.LpMaximize`.
        :return: An LP Problem
        """
        if " " in name:
            warnings.warn("Spaces are not permitted in the name. Converted to '_'")
            name = name.replace(" ", "_")
        self.name = name
        self._sense = sense
        self.sos1 = {}
        self.sos2 = {}
        self.status = const.LpStatusNotSolved
        self.sol_status = const.LpSolutionNoSolutionFound
        self.solver = None
        self.solverModel = None
        self.dummyVar = None
        self.solutionTime = 0
        self.solutionCpuTime = 0

        self._model: _rustcore.Model = _rustcore.Model(self.name)
        self._model.set_sense(
            _rustcore.ObjSense.Minimize
            if sense == const.LpMinimize
            else _rustcore.ObjSense.Maximize
        )

    def add_variable(
        self,
        name: str,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
    ) -> LpVariable:
        """Add a variable to the problem. Returns LpVariable wrapping the Rust variable."""
        if lowBound is not None and not math.isfinite(lowBound):
            raise const.PulpError(
                "The lower bound of a variable must be finite, got {}".format(lowBound)
            )
        if upBound is not None and not math.isfinite(upBound):
            raise const.PulpError(
                "The upper bound of a variable must be finite, got {}".format(upBound)
            )
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        if lowBound is not None and math.isfinite(lowBound):
            lb = lowBound
        if upBound is not None and math.isfinite(upBound):
            ub = upBound
        rcat = (
            _rustcore.Category.Binary
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer
                if cat == const.LpInteger
                else _rustcore.Category.Continuous
            )
        )
        rvar = self._model.add_variable(name, lb, ub, rcat)
        return LpVariable(rvar)

    def add_variable_dicts(
        self,
        name: str,
        indices: tuple[Iterable[Any], ...] | Iterable[Any] | None = None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart: list[Any] | None = None,
    ) -> dict[Any, Any]:
        """Create a dictionary of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = list(indices[0])  # type: ignore[arg-type]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = (
            _rustcore.Category.Binary
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer
                if cat == const.LpInteger
                else _rustcore.Category.Continuous
            )
        )
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [str(i)]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
            return {i: LpVariable(v) for i, v in zip(index, vars_)}
        return {
            i: self.add_variable_dicts(
                name, indices_rest, lowBound, upBound, cat, indexStart + [i]
            )
            for i in index
        }

    def add_variable_dict(
        self,
        name: str,
        indices,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
    ) -> dict:
        """Create a dictionary of variables with Cartesian product of indices."""
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        lists = list(indices)
        if len(indices) > 1:
            res = []
            while lists:
                first = lists[-1]
                nres = []
                if res:
                    if first:
                        for f in first:
                            nres.extend([[f] + r for r in res])
                    else:
                        nres = res
                    res = nres
                else:
                    res = [[f] for f in first]
                lists = lists[:-1]
            index = [tuple(r) for r in res]
        elif len(indices) == 1:
            index = list(indices[0])
        else:
            return {}
        names = [name % (i if isinstance(i, tuple) else (i,)) for i in index]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = (
            _rustcore.Category.Binary
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer
                if cat == const.LpInteger
                else _rustcore.Category.Continuous
            )
        )
        vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
        return {i: LpVariable(v) for i, v in zip(index, vars_)}

    def add_variable_matrix(
        self,
        name: str,
        indices: tuple[Iterable[Any], ...] | Iterable[Any] | None = None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart: list[Any] | None = None,
    ) -> list[Any]:
        """Create a list or nested list of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = list(indices[0])  # type: ignore[arg-type]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = (
            _rustcore.Category.Binary
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer
                if cat == const.LpInteger
                else _rustcore.Category.Continuous
            )
        )
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [i]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
            return [LpVariable(v) for v in vars_]
        return [
            self.add_variable_matrix(
                name, indices_rest, lowBound, upBound, cat, indexStart + [i]
            )
            for i in index
        ]

    @property
    def constraints(self) -> dict[str, LpConstraint]:
        """Constraints name -> LpConstraint (from Rust model)."""
        return {name: LpConstraint(c) for name, c in self._model.constraints_dict()}

    @property
    def objective(self) -> LpAffineExpression | None:
        """Objective expression from Rust, wrapped as LpAffineExpression."""
        expr = self._model.get_objective()
        if expr is None:
            return None
        return LpAffineExpression(expr)

    @objective.setter
    def objective(self, value: LpAffineExpression | LpVariable | None) -> None:
        """Set objective from LpAffineExpression or similar; stored in Rust."""
        if value is None:
            self._model.clear_objective()
            return
        if isinstance(value, LpVariable):
            value = LpAffineExpression.from_variable(value)
        self._model.set_objective(value._expr)

    @property
    def sense(self) -> int:
        return self._sense

    @sense.setter
    def sense(self, value: int) -> None:
        self._sense = value
        self._model.set_sense(
            _rustcore.ObjSense.Minimize
            if value == const.LpMinimize
            else _rustcore.ObjSense.Maximize
        )

    def __repr__(self) -> str:
        s = self.name + ":\n"
        if self.sense == 1:
            s += "MINIMIZE\n"
        else:
            s += "MAXIMIZE\n"
        s += repr(self.objective) + "\n"

        if self.constraints:
            s += "SUBJECT TO\n"
            for n, c in self.constraints.items():
                s += c.asCplexLpConstraint(n) + "\n"
        s += "VARIABLES\n"
        for v in self.variables():
            s += v.asCplexLpVariable() + " " + const.LpCategories[v.cat] + "\n"
        return s

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__.update(state)

    def copy(self) -> LpProblem:
        """Make a copy of self. Variables, objective, and constraints are re-built in Rust."""
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        for v in self.variables():
            lb = v.lowBound if math.isfinite(v.lowBound) else None
            ub = v.upBound if math.isfinite(v.upBound) else None
            lpcopy.add_variable(v.name, lb, ub, v.cat)
        if self.objective is not None:
            lpcopy.objective = self.objective
        var_by_name = {v.name: v for v in lpcopy.variables()}
        for name, c in self.constraints.items():
            items = c.items()
            items_new = [
                (var_by_name[v.name], coeff)
                for v, coeff in items
                if v.name in var_by_name
            ]
            rust_expr = _rustcore.AffineExpr()
            for v_new, coeff in items_new:
                rust_expr.add_term(v_new._var, coeff)
            rust_expr.set_constant(-(-c.constant))
            rust_expr.set_sense(_const_to_rust_sense(c.sense))
            if name:
                rust_expr.set_name(name)
            pending = LpAffineExpression(rust_expr)
            lpcopy.addConstraint(pending, name=name)
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def deepcopy(self) -> LpProblem:
        """Make a copy of self. Expressions are copied by value"""
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        for v in self.variables():
            lb = v.lowBound if math.isfinite(v.lowBound) else None
            ub = v.upBound if math.isfinite(v.upBound) else None
            lpcopy.add_variable(v.name, lb, ub, v.cat)
        if self.objective is not None:
            lpcopy.objective = self.objective
        for k, v in self.constraints.items():
            lpcopy.addConstraint(v.copy(), name=k)
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def toDataclass(self) -> mpslp.MPS:
        """
        Creates a :py:class:`mpslp.MPS` from the model with as much data as possible.
        It replaces variables by variable names.
        So it requires to have unique names for variables.

        :return: :py:class:`mpslp.MPS` with model data
        :rtype: mpslp.MPS
        """
        try:
            self.checkDuplicateVars()
        except const.PulpError:
            raise const.PulpError(
                "Duplicated names found in variables:\nto export the model, variable names need to be unique"
            )
        self.fixObjective()
        assert self.objective is not None
        variables = self.variables()
        return mpslp.MPS(
            objective=mpslp.MPSObjective(
                name=self.objective.name, coefficients=self.objective.toDataclass()
            ),
            constraints=[v.toDataclass() for v in self.constraints.values()],
            variables=[v.toDataclass() for v in variables],
            parameters=mpslp.MPSParameters(
                name=self.name,
                sense=self.sense,
                status=self.status,
                sol_status=self.sol_status,
            ),
            sos1=list(self.sos1.values()),
            sos2=list(self.sos2.values()),
        )

    def toRustModel(self) -> _rustcore.Model:
        """
        Return the Rust-backed model for this problem, if available.

        When the compiled extension ``pulp._rustcore`` is present, each
        :class:`LpProblem` maintains an internal Rust ``Model`` that mirrors
        variables, objective, and constraints as they are created.

        :raises RuntimeError: if the Rust extension is not available.
        """
        if self._model is None:
            raise RuntimeError(
                "pulp._rustcore is not available; build the Rust extension with maturin "
                "before calling toRustModel()."
            )
        return self._model

    @classmethod
    def fromDataclass(
        cls,
        mps: mpslp.MPS,
        *,
        objective_negate_for_max: bool = True,
    ) -> tuple[dict[str, LpVariable], LpProblem]:
        """
        Takes a :py:class:`mpslp.MPS` with all necessary information to build a model.
        And returns a dictionary of variables and a problem object.

        :param mps: :py:class:`mpslp.MPS` with the model stored
        :param objective_negate_for_max: when True (default), negate objective coefficients
            when sense is Maximize (for MPS files written as minimization). Set False when
            loading from :meth:`toDict` / JSON, where coefficients are stored as-is.
        :return: a tuple with a dictionary of variables and a :py:class:`LpProblem`
        """

        # we instantiate the problem
        pb = cls(name=mps.parameters.name, sense=mps.parameters.sense)
        pb.status = mps.parameters.status
        pb.sol_status = mps.parameters.sol_status

        # recreate the variables.
        var: dict[str, LpVariable] = {
            v.name: LpVariable.fromDataclass(pb, v) for v in mps.variables
        }

        # objective function.
        obj_e = {var[v.name]: v.value for v in mps.objective.coefficients}
        # MPS files are written as minimization; when sense is Maximize we negated on write, so negate back on read. toDict stores coefficients as-is, so do not negate when loading from dict.
        if objective_negate_for_max and mps.parameters.sense == const.LpMaximize:
            obj_e = {v: -c for v, c in obj_e.items()}
        pb += LpAffineExpression.from_dict(obj_e, name=mps.objective.name)

        # constraints
        for c in mps.constraints:
            pb._addConstraintFromDataclass(c, var)

        # last, parameters, other options
        pb.sos1 = dict(enumerate(mps.sos1))
        pb.sos2 = dict(enumerate(mps.sos2))

        return var, pb

    def toDict(self) -> dict[str, Any]:
        return dataclasses.asdict(self.toDataclass())

    def to_dict(self) -> dict[str, Any]:
        warnings.warn(
            "LpProblem.to_dict is deprecated, use LpProblem.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()

    @classmethod
    def fromDict(cls, data: dict[Any, Any]) -> tuple[dict[str, LpVariable], LpProblem]:
        return cls.fromDataclass(
            mpslp.MPS.fromDict(data), objective_negate_for_max=False
        )

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> tuple[dict[str, LpVariable], LpProblem]:
        warnings.warn(
            "LpProblem.from_dict is deprecated, use LpProblem.fromDict instead",
            category=DeprecationWarning,
        )
        return cls.fromDict(data)

    def toJson(self, filename: str, *args: Any, **kwargs: Any):
        """
        Creates a json file from the LpProblem information

        :param str filename: filename to write json
        :param args: additional arguments for json function
        :param kwargs: additional keyword arguments for json function
        :return: None
        """
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    def to_json(self, filename: str, *args: Any, **kwargs: Any):
        warnings.warn(
            "LpProblem.to_json is deprecated, use LpProblem.toJson instead",
            category=DeprecationWarning,
        )
        return self.toJson(filename, *args, **kwargs)

    @classmethod
    def fromJson(cls, filename: str) -> tuple[dict[str, LpVariable], LpProblem]:
        """
        Creates a new LpProblem from a json file with information

        :param str filename: json file name
        :return: a tuple with a dictionary of variables and an LpProblem
        :rtype: (dict, :py:class:`LpProblem`)
        """
        with open(filename) as f:
            data = json.load(f)
        return cls.fromDict(data)

    @classmethod
    def from_json(cls, filename: str) -> tuple[dict[str, LpVariable], LpProblem]:
        warnings.warn(
            "LpProblem.from_json is deprecated, use LpProblem.fromJson instead",
            category=DeprecationWarning,
        )
        return cls.fromJson(filename)

    @classmethod
    def fromMPS(
        cls, filename: str, sense: int = const.LpMinimize, dropConsNames: bool = False
    ) -> tuple[dict[str, LpVariable], LpProblem]:
        data = mpslp.readMPS(filename, sense=sense, dropConsNames=dropConsNames)
        return cls.fromDataclass(data)

    def isMIP(self) -> int:
        return 1 if self._model.is_mip() else 0

    def roundSolution(self, epsInt: float = 1e-5, eps: float = 1e-7) -> None:
        """
        Rounds the lp variables

        Inputs:
            - none

        Side Effects:
            - The lp variables are rounded
        """
        self._model.round_solution(epsInt, eps)

    def valid(self, eps: float = 0) -> bool:
        for v in self.variables():
            if not v.valid(eps):
                return False
        for c in self.constraints.values():
            if not c.valid(eps):
                return False
        else:
            return True

    def infeasibilityGap(self, mip: int = 1) -> float:
        gap: float = 0
        for v in self.variables():
            gap = max(abs(v.infeasibilityGap(mip)), gap)
        for c in self.constraints.values():
            if not c.valid(0):
                cv = c.value()
                if cv is not None:
                    gap = max(abs(cv), gap)
        return gap

    def variables(self) -> list[LpVariable]:
        """Returns the problem variables from the Rust model."""
        return [LpVariable(v) for v in self._model.list_variables()]

    def variablesDict(self) -> dict[str, LpVariable]:
        """Dict of variable name -> LpVariable, using same order as variables()."""
        return {v.name: v for v in self.variables()}

    def add(
        self, constraint: LpConstraint | LpAffineExpression, name: str | None = None
    ) -> None:
        self.addConstraint(constraint, name)

    def _addConstraintFromDataclass(
        self, mps: mpslp.MPSConstraint, variables: dict[str, LpVariable]
    ) -> None:
        """Build a constraint directly from an MPSConstraint dataclass, preserving pi."""
        coeffs: list[tuple[_rustcore.Variable, float]] = []
        for coefficient in mps.coefficients:
            coeffs.append((variables[coefficient.name]._var, coefficient.value))
        rhs = -float(mps.constant)
        sense = _const_to_rust_sense(mps.sense)
        cname = str(mps.name).translate(LpAffineExpression.trans) if mps.name else ""
        rust_constr = self._model.add_constraint(cname, coeffs, rhs, sense)
        if mps.pi is not None:
            rust_constr.set_pi(mps.pi)

    def addConstraint(
        self, constraint: LpConstraint | LpAffineExpression, name: str | None = None
    ) -> None:
        if isinstance(constraint, LpConstraint):
            return
        if name:
            constraint.name = name
        cname = constraint.name or ""
        coeffs = constraint._expr.items()
        rhs = -constraint.constant
        if not math.isfinite(rhs):
            raise const.PulpError(
                f"Invalid constraint RHS value: {rhs}. Coefficients and bounds must be finite."
            )
        for var, coeff in coeffs:
            if not math.isfinite(coeff):
                raise const.PulpError(
                    f"Invalid coefficient value: {coeff} for variable {var.name}. Coefficients must be finite."
                )
        csense = constraint.sense
        if csense is None:
            raise const.PulpError("Cannot add constraint without a sense (<=, >=, ==)")
        sense = _const_to_rust_sense(csense)
        self._model.add_constraint(cname, coeffs, rhs, sense)

    def setObjective(self, obj: LpAffineExpression | LpVariable | int | float) -> None:
        """
        Sets the objective function.

        :param obj: the objective function (LpAffineExpression, LpVariable, or numeric)

        Side Effects:
            - The objective function is set
        """
        if isinstance(obj, LpVariable):
            self.objective = LpAffineExpression.from_variable(obj)
        elif isinstance(obj, (int, float)):
            self.objective = LpAffineExpression.from_constant(float(obj))
        else:
            self.objective = obj

    def __iadd__(
        self,
        other: LpConstraint
        | LpAffineExpression
        | LpVariable
        | int
        | float
        | bool
        | tuple[Any, str | None],
    ) -> LpProblem:
        name: str | None = None
        if isinstance(other, tuple):
            other_val = other[0]
            name = str(other[1]) if other[1] is not None else None
            other = other_val  # type: ignore[assignment]
        if other is True:
            return self
        elif other is False:
            raise TypeError("A False object cannot be passed as a constraint")
        elif _is_numpy_bool(other):
            raise TypeError(
                "Comparison with a numpy scalar returned a numpy boolean. "
                "Put the variable on the left, e.g. model += var <= np.float64(34.5)"
            )
        elif isinstance(other, LpConstraint):
            self.addConstraint(other, name)
        elif isinstance(other, LpAffineExpression):
            if other.sense is not None:
                self.addConstraint(other, name)
            else:
                if self.objective is not None:
                    warnings.warn("Overwriting previously set objective.")
                if name is not None:
                    other.name = name
                self.objective = other
        elif isinstance(other, LpVariable):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression.from_variable(other, name=name)
        elif isinstance(other, (int, float)):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression.from_constant(float(other), name=name)
        else:
            raise TypeError(
                "Can only add LpConstraint, LpAffineExpression or True objects"
            )
        return self

    def extend(
        self,
        other: (
            LpProblem
            | dict[str, LpConstraint]
            | Iterable[tuple[str, LpConstraint] | LpConstraint]
        ),
        use_objective: bool = True,
    ):
        """
        extends an LpProblem by adding constraints either from a dictionary
        a tuple or another LpProblem object.

        :param bool use_objective: determines whether the objective is imported from
        the other problem

        For dictionaries the constraints will be named with the keys
        For tuples an unique name will be generated
        For LpProblems the name of the problem will be added to the constraints
        name
        """
        if isinstance(other, dict):
            for name, constraint in other.items():
                self.addConstraint(constraint, name=str(name))  # type: ignore[arg-type]
        elif isinstance(other, LpProblem):
            for v in set(other.variables()).difference(self.variables()):
                v.name = other.name + v.name
            for name, c in other.constraints.items():
                c.name = other.name + name
                self.addConstraint(c)
            if use_objective:
                if other.objective is None:
                    raise ValueError("Objective not set by provided problem")
                if self.objective is not None:
                    obj = self.objective.copy()
                    obj.addInPlace(other.objective)
                    self.objective = obj
                else:
                    self.objective = other.objective
        else:
            for item in other:
                if isinstance(item, tuple):
                    cname_val: str | None = (
                        str(item[0]) if item[0] is not None else None
                    )
                    constr: LpConstraint = item[1]  # type: ignore[assignment]
                elif isinstance(item, LpConstraint):
                    cname_val = None
                    constr = item
                else:
                    continue
                if not cname_val:
                    cname_val = constr.name
                self.addConstraint(constr, name=cname_val or None)

    def coefficients(
        self, translation: dict[str, str] | None = None
    ) -> list[tuple[str, str, float]]:
        coefs = []
        cons = self.constraints
        if translation is None:
            for c, cst in cons.items():
                coefs.extend([(v.name, c, cst[v]) for v in cst])
        else:
            for c, cst in cons.items():
                ctr = translation[c]
                coefs.extend([(translation[v.name], ctr, cst[v]) for v in cst])
        return coefs

    def writeMPS(
        self,
        filename: str,
        mpsSense: int = 0,
        rename: int | bool = 0,
        mip: int | bool = 1,
        with_objsense: bool = False,
    ) -> tuple[list[str], list[str], str]:
        """
        Writes an mps file from the problem information.

        :param filename: name of the file to write
        :param mpsSense: 0 (use problem sense), 1 minimize, -1 maximize
        :param rename: if True, normalized names (X0000000, C0000000) are used in the file
        :param mip: include integer/binary markers
        :param with_objsense: write OBJSENSE section
        :return: (variable_names, constraint_names, objective_name) as lists in model order (original or MPS names depending on rename)
        """
        return mpslp.writeMPS(
            self,
            filename,
            mpsSense=mpsSense,
            rename=rename,
            mip=mip,
            with_objsense=with_objsense,
        )

    def writeLP(
        self,
        filename: str,
        writeSOS: int | bool = 1,
        mip: int | bool = 1,
        max_length: int = 100,
    ) -> list[LpVariable]:
        """
        Write the given Lp problem to a .lp file.

        This function writes the specifications (objective function,
        constraints, variables) of the defined Lp problem to a file.

        :param str filename: the name of the file to be created.
        :return: variables

        Side Effects:
            - The file is created
        """
        return mpslp.writeLP(
            self, filename=filename, writeSOS=writeSOS, mip=mip, max_length=max_length
        )

    def checkDuplicateVars(self) -> None:
        """
        Checks if there are at least two variables with the same name
        :return: 1
        :raises `const.PulpError`: if there ar duplicates
        """
        try:
            self._model.check_duplicate_vars()
        except RuntimeError as e:
            raise const.PulpError(str(e)) from None

    def checkLengthVars(self, max_length: int) -> None:
        """
        Checks if variables have names smaller than `max_length`
        :param int max_length: max size for variable name
        :return:
        :raises const.PulpError: if there is at least one variable that has a long name
        """
        try:
            self._model.check_length_vars(max_length)
        except RuntimeError as e:
            raise const.PulpError(str(e)) from None

    def assignVarsVals(self, values: dict[str, float]) -> None:
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_values_by_name(filtered)

    def assignVarsDj(self, values: dict[str, float]) -> None:
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_djs_by_name(filtered)

    def assignConsPi(self, values: dict[str, float]) -> None:
        self._model.set_constraint_pis_by_name(dict(values))

    def assignConsSlack(self, values: dict[str, float], activity: bool = False) -> None:
        if activity:
            cons = self.constraints
            slack_vals = {}
            for name, val in values.items():
                if name in cons:
                    slack_vals[name] = -1 * (cons[name].constant + float(val))
            self._model.set_constraint_slacks_by_name(slack_vals)
        else:
            self._model.set_constraint_slacks_by_name(
                {k: float(v) for k, v in values.items()}
            )

    def get_dummyVar(self) -> LpVariable:
        if self.dummyVar is None:
            self.dummyVar = self.add_variable("__dummy", 0, 0)
        return self.dummyVar

    def fixObjective(self) -> tuple[bool, LpVariable | None]:
        obj = self.objective
        if obj is None:
            self.objective = LpAffineExpression.from_constant(0.0)
            obj = self.objective
            wasNone = True
        else:
            wasNone = False

        if obj is not None and obj.isNumericalConstant():
            dummyVar = self.get_dummyVar()
            expr = obj.copy()
            expr.addInPlace(dummyVar)
            self.objective = expr
        else:
            dummyVar = None

        return wasNone, dummyVar

    def restoreObjective(self, wasNone: bool, dummyVar: LpVariable | None) -> None:
        if wasNone:
            self.objective = None
        elif dummyVar is not None:
            obj = self.objective
            if obj is not None:
                expr = obj.copy()
                expr.subInPlace(dummyVar)
                self.objective = expr

    def solve(self, solver: LpSolver | None = None, **kwargs: Any) -> int:
        """
        Solve the given Lp problem.

        This function changes the problem to make it suitable for solving
        then calls the solver.actualSolve() method to find the solution

        :param solver:  Optional: the specific solver to be used, defaults to the
              default solver.

        Side Effects:
            - The attributes of the problem object are changed in
              :meth:`~pulp.solver.LpSolver.actualSolve()` to reflect the Lp solution
        """

        if not (solver):
            solver = self.solver
        if not (solver):
            solver = LpSolverDefault
        if solver is None:
            raise const.PulpError("No solver available")
        wasNone, dummyVar = self.fixObjective()
        # time it
        self.startClock()
        status = solver.actualSolve(self, **kwargs)
        self.stopClock()
        self.restoreObjective(wasNone, dummyVar)
        self.solver = solver
        return status

    def startClock(self) -> None:
        "initializes properties with the current time"
        self.solutionCpuTime = -clock()
        self.solutionTime = -time()

    def stopClock(self) -> None:
        "updates time wall time and cpu time"
        self.solutionTime += time()
        self.solutionCpuTime += clock()

    def sequentialSolve(
        self,
        objectives: list[LpAffineExpression],
        absoluteTols: list[int] | list[float] | None = None,
        relativeTols: list[int] | list[float] | None = None,
        solver: LpSolver | None = None,
        debug: bool = False,
    ) -> list[int]:
        """
        Solve the given Lp problem with several objective functions.

        This function sequentially changes the objective of the problem
        and then adds the objective function as a constraint

        :param objectives: the list of objectives to be used to solve the problem
        :param absoluteTols: the list of absolute tolerances to be applied to
           the constraints should be +ve for a minimise objective
        :param relativeTols: the list of relative tolerances applied to the constraints
        :param solver: the specific solver to be used, defaults to the default solver.

        """
        # TODO Add a penalty variable to make problems elastic
        # TODO add the ability to accept different status values i.e. infeasible etc

        if not (solver):
            solver = self.solver
        if not (solver):
            solver = LpSolverDefault
        if solver is None:
            raise const.PulpError("No solver available")
        if not (absoluteTols):
            absoluteTols = [0] * len(objectives)
        if not (relativeTols):
            relativeTols = [1] * len(objectives)
        # time it
        self.startClock()
        statuses = []
        for i, (obj, absol, rel) in enumerate(
            zip(objectives, absoluteTols, relativeTols)
        ):
            self.setObjective(obj)
            status = solver.actualSolve(self)
            statuses.append(status)
            if debug:
                self.writeLP(f"{i}Sequence.lp")
            if self.sense == const.LpMinimize:
                self += obj <= value(obj) * rel + absol, f"Sequence_Objective_{i}"
            elif self.sense == const.LpMaximize:
                self += obj >= value(obj) * rel + absol, f"Sequence_Objective_{i}"
        self.stopClock()
        self.solver = solver
        return statuses

    def resolve(self, solver: LpSolver | None = None, **kwargs: Any) -> int:
        """
        Re-solves the problem using the same solver as previously.
        """
        return self.solve(solver=solver, **kwargs)

    def setSolver(self, solver: LpSolver | None = LpSolverDefault) -> None:
        """Sets the Solver for this problem useful if you are using
        resolve
        """
        self.solver = solver

    def numVariables(self) -> int:
        """

        :return: number of variables in model
        """
        return len(self.variables())

    def numConstraints(self) -> int:
        """

        :return: number of constraints in model
        """
        return len(self.constraints)

    def getSense(self) -> int:
        return self.sense

    def assignStatus(self, status: int, sol_status: int | None = None) -> bool:
        """
        Sets the status of the model after solving.
        :param status: code for the status of the model
        :param sol_status: code for the status of the solution
        :return:
        """
        if status not in const.LpStatus:
            raise const.PulpError("Invalid status code: " + str(status))

        if sol_status is not None and sol_status not in const.LpSolution:
            raise const.PulpError("Invalid solution status code: " + str(sol_status))

        self.status = status
        if sol_status is None:
            sol_status = const.LpStatusToSolution.get(
                status, const.LpSolutionNoSolutionFound
            )
        self.sol_status = sol_status
        return True


def lpSum(
    vector: (
        Iterable[LpAffineExpression | LpVariable | int | float]
        | Iterable[tuple[LpVariable, float]]
        | int
        | float
        | LpVariable
    ),
) -> LpAffineExpression:
    """
    Calculate the sum of a list of linear expressions

    :param vector: A list of linear expressions
    """
    return LpAffineExpression.empty().addInPlace(vector)


def _vector_like(obj: object) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, LpAffineExpression)


def lpDot(v1: Any, v2: Any) -> LpAffineExpression:
    """Calculate the dot product of two lists of linear expressions"""
    if not _vector_like(v1) and not _vector_like(v2):
        return v1 * v2
    elif not _vector_like(v1):
        return lpDot([v1] * len(v2), v2)
    elif not _vector_like(v2):
        return lpDot(v1, [v2] * len(v1))
    else:
        return lpSum([lpDot(e1, e2) for e1, e2 in zip(v1, v2)])
