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
Use ``LpVariable`` to create new variables. To create a variable x with 0  ≤  x  ≤  3::

     from pulp import *
     x = LpVariable("x", 0, 3)

To create a binary variable, y, with values either 0 or 1::

     y = LpVariable("y", cat="Binary")

Use ``LpProblem`` to create new problems. Create a problem called "myProblem" like so::

     prob = LpProblem("myProblem", LpMinimize)

Combine variables in order to create expressions and constraints, and then add them to
the problem.::

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

from collections import Counter
import sys
import warnings
import math
from time import time
from typing import Any, Literal, Optional

from .apis import LpSolverDefault, PULP_CBC_CMD
from .apis.core import clock
from .utilities import value
from . import constants as const
from . import mps_lp as mpslp

from collections.abc import Iterable
import logging
import dataclasses

# The Rust core is a hard dependency in this redesigned, model-centric API.
from . import _rustcore  # type: ignore[import-untyped]

log = logging.getLogger(__name__)

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

import re


def _rust_cat_to_const(rust_cat):
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

    illegal_chars = "-+[] ->/"
    expression = re.compile(f"[{re.escape(illegal_chars)}]")
    trans = str.maketrans(illegal_chars, "________")

    def __init__(self, _var):
        if _var is None:
            raise TypeError("LpVariable requires a Rust variable (created only by the model)")
        self._var = _var

    @property
    def name(self) -> str:
        return self._var.name

    @name.setter
    def name(self, value: str) -> None:
        self._var.set_name(value)  # type: ignore[union-attr]

    def __hash__(self) -> int:
        return hash(self._var.id())

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __neg__(self):
        return -LpAffineExpression(self)

    def __pos__(self):
        return self

    def __bool__(self):
        return bool(self.roundedValue())

    def __add__(self, other):
        return LpAffineExpression(self) + other

    def __radd__(self, other):
        return LpAffineExpression(self) + other

    def __sub__(self, other):
        return LpAffineExpression(self) - other

    def __rsub__(self, other):
        return other - LpAffineExpression(self)

    def __mul__(self, other):
        return LpAffineExpression(self) * other

    def __rmul__(self, other):
        return LpAffineExpression(self) * other

    def __truediv__(self, other):
        return LpAffineExpression(self) / other

    def __le__(self, other):
        return LpAffineExpression(self) <= other

    def __ge__(self, other):
        return LpAffineExpression(self) >= other

    def __eq__(self, other: object):
        if isinstance(other, LpVariable):
            return self._var.id() == other._var.id()
        if isinstance(other, (int, float)):
            return LpAffineExpression(self) == other
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, LpVariable):
            return self._var.id() != other._var.id()
        elif isinstance(other, (LpAffineExpression, LpConstraint, LpConstraintExpr)):
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
        self._var.set_lb(float('-inf') if value is None else value)  # type: ignore[union-attr]

    @property
    def upBound(self) -> float:
        return self._var.ub

    @upBound.setter
    def upBound(self, value: float | None) -> None:
        self._var.set_ub(float('inf') if value is None else value)  # type: ignore[union-attr]

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
        lb = mps.lowBound if mps.lowBound is not None else float("-inf")
        ub = mps.upBound if mps.upBound is not None else float("inf")
        var = problem.add_variable(mps.name, lb, ub, mps.cat)
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

    def to_dict(self) -> dict[str, Any]:
        """
        Exports a variable into a dict with its relevant information.

        This method is deprecated and :py:class:`LpVariable.toDict` should be used instead.

        :return: a :py:class:`dict` with the variable information
        :rtype: :dict
        """
        warnings.warn(
            "LpVariable.to_dict is deprecated, use LpVariable.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()

    @classmethod
    def fromDict(cls, problem: "LpProblem", data: dict[str, Any]):
        """
        Initializes a variable from a dict by adding it to the given problem.

        :param problem: the problem to add the variable to
        :param data: a dict with the variable information
        :return: a :py:class:`LpVariable`
        """
        return cls.fromDataclass(problem, mpslp.MPSVariable.fromDict(data))

    @classmethod
    def from_dict(cls, problem: "LpProblem", data: dict[str, Any]):
        """
        Deprecated. Use LpVariable.fromDict(problem, data) instead.
        """
        warnings.warn(
            "LpVariable.from_dict is deprecated, use LpVariable.fromDict instead",
            category=DeprecationWarning,
        )
        return cls.fromDict(problem, data)

    def getLb(self):
        return self.lowBound

    def getUb(self):
        return self.upBound

    def bounds(self, low: float, up: float):
        self._var.set_lb(low)
        self._var.set_ub(up)

    def positive(self):
        self.bounds(0, float("inf"))

    def value(self):
        return self._var.value

    def round(self, epsInt=1e-5, eps=1e-7):
        if self.varValue is not None:
            if (
                math.isfinite(self.upBound)
                and self.varValue > self.upBound
                and self.varValue <= self.upBound + eps
            ):
                self.varValue = self.upBound
            elif (
                math.isfinite(self.lowBound)
                and self.varValue < self.lowBound
                and self.varValue >= self.lowBound - eps
            ):
                self.varValue = self.lowBound
            self.varValue = self.roundedValue(epsInt)

    def roundedValue(self, eps=1e-5):
        if (
            self.cat == const.LpInteger
            and self.varValue is not None
            and abs(self.varValue - round(self.varValue)) <= eps
        ):
            return round(self.varValue)
        else:
            return self.varValue

    def valueOrDefault(self):
        if self.varValue is not None:
            return self.varValue
        elif math.isfinite(self.lowBound):
            if math.isfinite(self.upBound):
                if 0 >= self.lowBound and 0 <= self.upBound:
                    return 0
                else:
                    if self.lowBound >= 0:
                        return self.lowBound
                    else:
                        return self.upBound
            else:
                if 0 >= self.lowBound:
                    return 0
                else:
                    return self.lowBound
        elif math.isfinite(self.upBound):
            if 0 <= self.upBound:
                return 0
            else:
                return self.upBound
        else:
            return 0

    def valid(self, eps):
        if self.name == "__dummy" and self.varValue is None:
            return True
        if self.varValue is None:
            return False
        if math.isfinite(self.upBound) and self.varValue > self.upBound + eps:
            return False
        if math.isfinite(self.lowBound) and self.varValue < self.lowBound - eps:
            return False
        if (
            self.cat == const.LpInteger
            and abs(round(self.varValue) - self.varValue) > eps
        ):
            return False
        return True

    def infeasibilityGap(self, mip: bool = True):
        if self.varValue is None:
            raise ValueError("variable value is None")
        if math.isfinite(self.upBound) and self.varValue > self.upBound:
            return self.varValue - self.upBound
        if math.isfinite(self.lowBound) and self.varValue < self.lowBound:
            return self.varValue - self.lowBound
        if (
            mip
            and self.cat == const.LpInteger
            and round(self.varValue) - self.varValue != 0
        ):
            return round(self.varValue) - self.varValue
        return 0

    def isBinary(self):
        if self.cat == const.LpBinary:
            return True
        return self.cat == const.LpInteger and self.lowBound == 0 and self.upBound == 1

    def isInteger(self):
        return self.cat == const.LpInteger

    def isFree(self):
        return not math.isfinite(self.lowBound) and not math.isfinite(self.upBound)

    def isConstant(self):
        return math.isfinite(self.lowBound) and self.upBound == self.lowBound

    def isPositive(self):
        return self.lowBound == 0 and not math.isfinite(self.upBound)

    def asCplexLpVariable(self):
        if self.isFree():
            return self.name + " free"
        if self.isConstant():
            return self.name + f" = {self.lowBound:.12g}"
        if not math.isfinite(self.lowBound):
            s = "-inf <= "
        # Note: XPRESS and CPLEX do not interpret integer variables without
        # explicit bounds
        elif self.lowBound == 0 and self.cat == const.LpContinuous:
            s = ""
        else:
            s = f"{self.lowBound:.12g} <= "
        s += self.name
        if math.isfinite(self.upBound):
            s += f" <= {self.upBound:.12g}"
        return s

    def asCplexLpAffineExpression(self, name, include_constant: bool = True):
        return LpAffineExpression(self).asCplexLpAffineExpression(
            name, include_constant
        )

    def setInitialValue(self, val, check=True):
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

    def fixValue(self):
        """
        changes lower bound and upper bound to the initial value if exists.
        :return: None
        """
        val = self.varValue
        if val is not None:
            self.bounds(val, val)

    def isFixed(self):
        """

        :return: True if upBound and lowBound are the same
        :rtype: bool
        """
        return self.isConstant()

    def unfixValue(self):
        self.bounds(self._lowbound_original, self._upbound_original)


class LpAffineExpression:
    """
    Thin wrapper around Rust AffineExpr. A linear combination of LpVariables + constant.
    Can be initialised with: None (empty), dict, list of (var, coeff),
    LpVariable (1*var), LpAffineExpression/LpConstraintExpr (copy), or number (constant only).

    Examples:
       >>> c = LpAffineExpression([(x[0], 1), (x[1], -3), (x[2], 4)])
    """

    trans = str.maketrans("-+[] ", "_____")

    def __init__(self, e=None, constant: float = 0.0, name: str | None = None, _expr=None):
        self.__name = None
        self.name = name
        if _expr is not None:
            self._expr = _expr
            self._model = None
            return
        if e is None:
            e = {}
        if not math.isfinite(constant):
            raise const.PulpError(
                f"Invalid constant value: {constant}. It must be a finite number."
            )
        self._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
        self._model = None  # set by addConstraint so items() can resolve VarId -> LpVariable

        if isinstance(e, (LpAffineExpression, LpConstraint, LpConstraintExpr)):
            self._expr = e._expr.clone_expr()  # type: ignore[union-attr]
        elif isinstance(e, dict):
            self._expr.set_constant(float(constant))  # type: ignore[union-attr]
            for k, v in e.items():
                if isinstance(k, LpVariable):
                    self._expr.add_term(k._var, float(v))  # type: ignore[union-attr]
        elif isinstance(e, Iterable) and not isinstance(e, str):
            self._expr.set_constant(float(constant))  # type: ignore[union-attr]
            for item in e:
                k, v = item[0], item[1]
                if isinstance(k, LpVariable):
                    self._expr.add_term(k._var, float(v))  # type: ignore[union-attr]
        elif isinstance(e, LpVariable):
            self._expr.add_term(e._var, 1.0)  # type: ignore[union-attr]
        elif isinstance(e, (int, float)) and math.isfinite(e):
            self._expr.set_constant(float(e))  # type: ignore[union-attr]
        else:
            self._expr.set_constant(float(constant) if math.isfinite(constant) else float(e) if e is not None else 0.0)  # type: ignore[union-attr]

    @property
    def name(self) -> str | None:
        return self.__name

    @name.setter
    def name(self, value: str | None):
        if value:
            self.__name = str(value).translate(self.trans)
        else:
            self.__name = None  # type: ignore[assignment]

    @property
    def constant(self) -> float:
        return self._expr.constant  # type: ignore[union-attr]

    @constant.setter
    def constant(self, value: float):
        self._expr.set_constant(float(value))  # type: ignore[union-attr]

    def items(self, model=None):
        """Return (LpVariable, coeff) pairs. If model is provided, store it for future items()/keys()/values()."""
        if model is not None:
            self._model = model._model if hasattr(model, '_model') else model
        if self._model is None:
            return []
        raw = self._expr.terms_with_variables(self._model)  # type: ignore[union-attr]
        return [(LpVariable(v), float(c)) for v, c in raw]

    def keys(self):
        return [v for v, _ in self.items()]

    def values(self):
        return [c for _, c in self.items()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return self._expr.num_terms()  # type: ignore[union-attr]

    def __getitem__(self, key):
        if isinstance(key, LpVariable):
            return self._expr.get_coeff(key._var)  # type: ignore[union-attr]
        for v, c in self.items():
            if v is key or v.name == key.name:
                return c
        raise KeyError(key)

    def __setitem__(self, key: LpVariable, value: float | int):
        if not isinstance(key, LpVariable):
            raise TypeError("Only LpVariable keys supported")
        old = self._expr.get_coeff(key._var)  # type: ignore[union-attr]
        self._expr.add_term(key._var, float(value) - old)  # type: ignore[union-attr]

    def __contains__(self, key):
        if isinstance(key, LpVariable):
            return self._expr.get_coeff(key._var) != 0  # type: ignore[union-attr]
        return any(v is key or v.name == key.name for v, _ in self.items())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self):
        return len(self) == 0

    def atom(self):
        return next(iter(self.keys()))

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def value(self) -> float | None:
        s = self.constant
        for v, x in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * x
        return s

    def valueOrDefault(self) -> float:
        s = self.constant
        for v, x in self.items():
            s += v.valueOrDefault() * x
        return s

    def addterm(self, key: LpVariable, value: float | int):
        self._expr.add_term(key._var, float(value))  # type: ignore[union-attr]

    def emptyCopy(self):
        return LpAffineExpression()

    def copy(self):
        out = LpAffineExpression(_expr=self._expr.clone_expr())  # type: ignore[union-attr]
        out._model = self._model
        return out

    @staticmethod
    def _str_coeff(c: float) -> str:
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    def __str__(self, include_constant: bool = True, override_constant: float | None = None):
        s = ""
        for v in self.sorted_keys():
            val = self[v]
            if val < 0:
                s += (" - " if s else "-") + (str(-val) if val != -1 else "") + ("" if val == -1 else "*") + str(v)
            elif s:
                s += " + " + (str(v) if val == 1 else self._str_coeff(val) + "*" + str(v))
            else:
                s = str(v) if val == 1 else self._str_coeff(val) + "*" + str(v)
        if include_constant:
            c = self.constant if override_constant is None else override_constant
            if not s:
                s = str(c)
            elif c < 0:
                s += " - " + str(-c)
            elif c > 0:
                s += " + " + str(c)
        elif not s:
            s = "0"
        return s

    def sorted_keys(self) -> list:
        result = list(self.keys())
        result.sort(key=lambda v: v.name)
        return result

    def __repr__(self, override_constant: float | None = None):
        c = self.constant if override_constant is None else override_constant
        parts = [f"{float(self[v])}*{v}" for v in self.sorted_keys()]
        parts.append(str(float(c)))
        return " + ".join(parts)

    @staticmethod
    def _count_characters(line):
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name: str):
        result = []
        line = [f"{name}:"]
        not_first = 0
        for v in self.sorted_keys():
            val = self[v]
            sign = " -" if val < 0 else (" +" if not_first else "")
            val = abs(val)
            not_first = 1
            term = f"{sign} {v.name}" if val == 1 else f"{sign} {val + 0:.12g} {v.name}"
            if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
                result += ["".join(line)]
                line = [term]
            else:
                line += [term]
        return result, line

    def asCplexLpAffineExpression(
        self, name: str, include_constant: bool = True, override_constant: float | None = None
    ):
        result, line = self.asCplexVariablesOnly(name)
        c = self.constant if override_constant is None else override_constant
        term = f" - {-c:.12g}" if c < 0 else (f" + {c}" if c > 0 else " 0")
        result += ["".join(line) + term]
        return "%s\n" % "\n".join(result)

    def addInPlace(self, other, sign: Literal[+1, -1] = 1):
        if other is None or (isinstance(other, int) and other == 0):
            return self
        if isinstance(other, LpVariable):
            self.addterm(other, sign)
        elif isinstance(other, (LpAffineExpression, LpConstraint, LpConstraintExpr)):
            self._expr.add_expr(other._expr, sign)  # type: ignore[union-attr]
        elif isinstance(other, dict):
            for e in other.values():
                self.addInPlace(e, sign=sign)
        elif isinstance(other, Iterable) and not isinstance(other, str):
            for e in other:
                self.addInPlace(e, sign=sign)
        elif not math.isfinite(other):
            raise const.PulpError("Cannot add/subtract NaN/inf values")
        else:
            self._expr.set_constant(self._expr.constant + other * sign)  # type: ignore[union-attr]
        return self

    def subInPlace(self, other):
        return self.addInPlace(other, sign=-1)

    def __neg__(self):
        e = self.emptyCopy()
        e._expr = self._expr.clone_expr()  # type: ignore[union-attr]
        e._expr.scale(-1.0)  # type: ignore[union-attr]
        return e

    def __pos__(self):
        return self

    def __add__(self, other):
        return self.copy().addInPlace(other)

    def __radd__(self, other):
        return self.copy().addInPlace(other)

    def __iadd__(self, other):
        return self.addInPlace(other)

    def __sub__(self, other):
        return self.copy().subInPlace(other)

    def __rsub__(self, other):
        return (-self).addInPlace(other)

    def __isub__(self, other):
        return self.subInPlace(other)

    def __mul__(self, other):
        e = self.emptyCopy()
        if isinstance(other, (LpAffineExpression, LpConstraint, LpConstraintExpr)):
            e.constant = self.constant * other.constant
            if len(other):
                if len(self):
                    raise TypeError("Non-constant expressions cannot be multiplied")
                e._expr = other._expr.clone_expr()  # type: ignore[union-attr]
                e._expr.scale(self.constant)  # type: ignore[union-attr]
            else:
                e._expr = self._expr.clone_expr()  # type: ignore[union-attr]
                e._expr.scale(other.constant)  # type: ignore[union-attr]
        elif isinstance(other, LpVariable):
            return self * LpAffineExpression(other)
        else:
            if not math.isfinite(other):
                raise const.PulpError("Cannot multiply variables with NaN/inf values")
            if other != 0:
                e._expr = self._expr.clone_expr()  # type: ignore[union-attr]
                e._expr.scale(float(other))  # type: ignore[union-attr]
        return e

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        if isinstance(other, (LpAffineExpression, LpConstraint, LpConstraintExpr)) or isinstance(other, LpVariable):
            if len(other):
                raise TypeError("Expressions cannot be divided by a non-constant expression")
            other = other.constant
        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        e = self.emptyCopy()
        e._expr = self._expr.clone_expr()  # type: ignore[union-attr]
        e._expr.scale(1.0 / other)  # type: ignore[union-attr]
        return e

    def __le__(self, other) -> LpConstraintExpr:
        if isinstance(other, (int, float)):
            return LpConstraintExpr(self, const.LpConstraintLE, rhs=other)
        return LpConstraintExpr(self - other, const.LpConstraintLE)

    def __ge__(self, other) -> LpConstraintExpr:
        if isinstance(other, (int, float)):
            return LpConstraintExpr(self, const.LpConstraintGE, rhs=other)
        return LpConstraintExpr(self - other, const.LpConstraintGE)

    def __eq__(self, other) -> LpConstraintExpr:  # type: ignore[override]
        if isinstance(other, (int, float)):
            return LpConstraintExpr(self, const.LpConstraintEQ, rhs=other)
        return LpConstraintExpr(self - other, const.LpConstraintEQ)

    def toDataclass(self) -> list[mpslp.MPSCoefficient]:
        """
        exports the :py:class:`LpAffineExpression` into a list of dataclasses with the coefficients
        it does not export the constant

        :return: list of :py:class:`mpslp.MPSCoefficient` with the coefficients
        :rtype: list
        """
        return [mpslp.MPSCoefficient(name=k.name, value=v) for k, v in self.items()]

    def toDict(self) -> list[dict[str, Any]]:
        """
        exports the :py:class:`LpAffineExpression` into a list of dictionaries with the coefficients
        it does not export the constant

        :return: list of dictionaries with the coefficients
        :rtype: list
        """
        return [{"name": k.name, "value": v} for k, v in self.items()]

    def to_dict(self) -> list[dict[str, Any]]:
        """
        exports the :py:class:`LpAffineExpression` into a list of dictionaries with the coefficients
        it does not export the constant

        :return: list of dictionaries with the coefficients
        :rtype: list
        """
        warnings.warn(
            "LpAffineExpression.to_dict is deprecated, use LpAffineExpression.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()


def _rust_sense_to_const(rsense):
    if rsense == _rustcore.Sense.LessEqual:  # type: ignore[attr-defined]
        return const.LpConstraintLE
    if rsense == _rustcore.Sense.GreaterEqual:  # type: ignore[attr-defined]
        return const.LpConstraintGE
    return const.LpConstraintEQ




class LpConstraintExpr:
    """
    Pending constraint (expr, sense, rhs) before it is added to a model.
    Created by e.g. (x <= 5). Only LpConstraint (Rust-backed) is created by the model.
    """

    def __init__(
        self,
        e=None,
        sense: int = const.LpConstraintEQ,
        name: str | None = None,
        rhs: float | None = None,
    ):
        self.expr = e if isinstance(e, LpAffineExpression) else LpAffineExpression(e)
        self.__name = name
        expr_const = float(self.expr.constant)
        if rhs is not None:
            if not math.isfinite(rhs):
                raise const.PulpError("Cannot set constraint RHS to NaN/inf values")
            self.__constant = expr_const - float(rhs)
        else:
            self.__constant = 0.0
        self.__sense = sense
        self.pi = None
        self.slack = None

    def _normalized_rhs(self) -> float:
        return self.__constant

    @property
    def name(self) -> str | None:
        return self.__name

    @name.setter
    def name(self, value: str | None):
        if value is not None:
            self.__name = value.translate(LpAffineExpression.trans)
        else:
            self.__name = None

    @property
    def constant(self) -> float:
        if self.__sense == const.LpConstraintEQ:
            return -float(self.expr.constant)
        return self.__constant

    @constant.setter
    def constant(self, value: float):
        self.__constant = value

    @property
    def sense(self) -> int:
        return self.__sense

    @sense.setter
    def sense(self, value: int):
        self.__sense = value

    def items(self):
        return list(self.expr.items()) if hasattr(self.expr, "items") else []

    def keys(self):
        return [v for v, _ in self.items()]

    def values(self):
        return [c for _, c in self.items()]

    def __getitem__(self, key):
        return self.expr[key]

    def __contains__(self, key):
        return any(v is key or v.name == key.name for v, _ in self.items())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.expr)

    def getLb(self) -> float | None:
        if (self.sense == const.LpConstraintGE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        return None

    def getUb(self) -> float | None:
        if (self.sense == const.LpConstraintLE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        return None

    def __str__(self):
        s = self.expr.__str__(include_constant=False, override_constant=self.constant)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " " + str(-self.constant)
        return s

    def __repr__(self):
        s = self.expr.__repr__(override_constant=self.constant)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " 0"
        return s

    def asCplexLpConstraint(self, name):
        result, line = self.expr.asCplexVariablesOnly(name)
        if len(self.keys()) == 0:
            line += ["0"]
        c = -self.constant
        if c == 0:
            c = 0
        term = f" {const.LpConstraintSenses[self.sense]} {c:.12g}"
        if self.expr._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        return "%s\n" % "\n".join(result)

    def asCplexLpAffineExpression(self, name: str, include_constant: bool = True):
        return self.expr.asCplexLpAffineExpression(
            name, include_constant, override_constant=self.constant
        )

    def changeRHS(self, RHS: float):
        self.constant = -RHS

    def copy(self):
        return LpConstraintExpr(
            self.expr.copy(), self.sense, rhs=-self.constant + self.expr.constant
        )

    def emptyCopy(self):
        return LpConstraintExpr(sense=self.sense)

    def addInPlace(self, other, sign: Literal[+1, -1] = 1):
        if isinstance(other, (LpConstraint, LpConstraintExpr)):
            if not (self.sense * other.sense >= 0):
                sign = -sign
            self.constant += other.constant * sign
            self.expr.addInPlace(other.expr, sign)
            self.sense |= other.sense * sign
        elif isinstance(other, (int, float)):
            self.constant += other * sign
            self.expr.addInPlace(other, sign)
        elif isinstance(other, LpAffineExpression):
            self.constant += other.constant * sign
            self.expr.addInPlace(other, sign)
        elif isinstance(other, LpVariable):
            self.expr.addInPlace(other, sign)
        else:
            raise TypeError(f"Constraints and {type(other)} cannot be added")
        return self

    def subInPlace(self, other):
        return self.addInPlace(other, -1)

    def __neg__(self):
        c = self.copy()
        c.constant = -c.constant
        c.expr = -c.expr
        return c

    def __add__(self, other):
        return self.copy().addInPlace(other)

    def __radd__(self, other):
        return self.copy().addInPlace(other)

    def __sub__(self, other):
        return self.copy().subInPlace(other)

    def __rsub__(self, other):
        return (-self).addInPlace(other)

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            c = self.copy()
            c.constant = c.constant * other
            c.expr = c.expr * other
            return c
        elif isinstance(other, LpAffineExpression):
            c = self.copy()
            c.constant = c.constant * other.constant
            c.expr = c.expr * other
            return c
        raise TypeError(f"Cannot multiply LpConstraintExpr by {type(other)}")

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            c = self.copy()
            c.constant = c.constant / other
            c.expr = c.expr / other
            return c
        elif isinstance(other, LpAffineExpression):
            c = self.copy()
            c.constant = c.constant / other.constant
            c.expr = c.expr / other
            return c
        raise TypeError(f"Cannot divide LpConstraintExpr by {type(other)}")

    def valid(self, eps: float = 0) -> bool:
        val = self.value()
        if val is None:
            return False
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        return val * self.sense >= -eps

    def makeElasticSubProblem(self, *args, **kwargs):
        return FixedElasticSubProblem(self, *args, **kwargs)

    def toDataclass(self) -> mpslp.MPSConstraint:
        return mpslp.MPSConstraint(
            sense=self.sense,
            pi=self.pi,
            constant=self.constant,
            name=self.name,
            coefficients=self.expr.toDataclass(),
        )

    @classmethod
    def fromDataclass(
        cls, mps: mpslp.MPSConstraint, variables: dict[str, LpVariable]
    ) -> "LpConstraintExpr":
        const = cls(
            e=LpAffineExpression(
                {variables[coefficient.name]: coefficient.value for coefficient in mps.coefficients}
            ),
            sense=mps.sense,
            name=mps.name,
            rhs=-mps.constant,
        )
        const.pi = mps.pi
        return const

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self):
        return self.expr.isNumericalConstant()

    def atom(self):
        return self.expr.atom()

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def get(self, key: LpVariable, default: float | None = None) -> float | None:
        return self.expr.get(key, default)

    def value(self) -> float | None:
        s = self.constant
        for v, x in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * x
        return s

    def valueOrDefault(self) -> float:
        s = self.constant
        for v, x in self.items():
            s += v.valueOrDefault() * x
        return s


class LpConstraint:
    """LP constraint backed by Rust. Only created via LpProblem.addConstraint."""

    def __init__(self, _constr):
        if _constr is None:
            raise TypeError("LpConstraint requires a Rust Constraint (created only by the model)")
        self._constr = _constr

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

    @property
    def constant(self) -> float:
        return -self._constr.rhs

    @property
    def sense(self) -> int:
        return _rust_sense_to_const(self._constr.sense)

    def _normalized_rhs(self) -> float:
        return -self._constr.rhs

    def items(self):
        return [(LpVariable(v), c) for v, c in self._constr.items()]

    def keys(self):
        return [v for v, _ in self.items()]

    def values(self):
        return [c for _, c in self.items()]

    def __getitem__(self, key):
        for v, c in self.items():
            if v is key or (v.name == key.name):
                return c
        raise KeyError(key)

    def __contains__(self, key):
        return any(v is key or v.name == key.name for v, _ in self.items())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
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
    def _count_characters(line):
        return sum(len(t) for t in line)

    def _asCplexVariablesOnly(self, name: str):
        result = []
        line = [f"{name}:"]
        not_first = 0
        for v, val in self.items():
            if val < 0:
                sign = " -"
                val = -val
            elif not_first:
                sign = " +"
            else:
                sign = ""
            not_first = 1
            term = f"{sign} {val + 0:.12g} {v.name}" if val != 1 else f"{sign} {v.name}"
            if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
                result += ["".join(line)]
                line = [term]
            else:
                line += [term]
        return result, line

    def __str__(self):
        parts = []
        for v, coeff in self.items():
            if coeff < 0:
                parts.append(f" - {-coeff}*{v.name}" if parts else f"-{-coeff}*{v.name}")
            elif parts:
                parts.append(f" + {coeff}*{v.name}" if coeff != 1 else f" + {v.name}")
            else:
                parts.append(f"{v.name}" if coeff == 1 else f"{coeff}*{v.name}")
        s = "".join(parts) or "0"
        s += " " + const.LpConstraintSenses[self.sense] + " " + str(-self.constant)
        return s

    def __repr__(self):
        parts = [f"{float(c)}*{v.name}" for v, c in self.items()]
        parts.append(str(float(self.constant)))
        s = " + ".join(parts)
        s += " " + const.LpConstraintSenses[self.sense] + " 0"
        return s

    def asCplexLpConstraint(self, name):
        result, line = self._asCplexVariablesOnly(name)
        if len(self.keys()) == 0:
            line += ["0"]
        c = -self.constant
        if c == 0:
            c = 0
        term = f" {const.LpConstraintSenses[self.sense]} {c:.12g}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        return "%s\n" % "\n".join(result)

    def asCplexLpAffineExpression(self, name: str, include_constant: bool = True):
        result, line = self._asCplexVariablesOnly(name)
        c = self.constant
        term = f" - {-c:.12g}" if c < 0 else (f" + {c}" if c > 0 else " 0")
        result += ["".join(line) + term]
        return "%s\n" % "\n".join(result)

    def changeRHS(self, RHS: float):
        raise NotImplementedError("Cannot change RHS of constraint already in model")

    def addInPlace(self, other, sign: Literal[+1, -1] = 1):
        raise NotImplementedError(
            "Cannot modify constraint already in model; use a pending constraint (e.g. expr <= rhs) for in-place ops"
        )

    def copy(self):
        """Return a LpConstraintExpr (pending) copy."""
        return LpConstraintExpr(
            LpAffineExpression(self.items()), self.sense, rhs=self._constr.rhs
        )

    def emptyCopy(self):
        return LpConstraintExpr(sense=self.sense)

    def valid(self, eps: float = 0) -> bool:
        val = self.value()
        if val is None:
            return False
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        return val * self.sense >= -eps

    def makeElasticSubProblem(self, *args, **kwargs):
        return FixedElasticSubProblem(self, *args, **kwargs)

    def toDataclass(self) -> mpslp.MPSConstraint:
        return mpslp.MPSConstraint(
            sense=self.sense,
            pi=self.pi,
            constant=self.constant,
            name=self.name,
            coefficients=[mpslp.MPSCoefficient(name=k.name, value=v) for k, v in self.items()],
        )

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self):
        return len(self) == 0

    def atom(self):
        items = self.items()
        return items[0][0] if items else None

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def get(self, key: LpVariable, default: float | None = None) -> float | None:
        for v, c in self.items():
            if v is key or (v.name == key.name):
                return c
        return default

    def value(self) -> float | None:
        s = self.constant
        for v, x in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * x
        return s

    def valueOrDefault(self) -> float:
        s = self.constant
        for v, x in self.items():
            s += v.valueOrDefault() * x
        return s


class LpFractionConstraint(LpConstraintExpr):
    """
    Creates a constraint that enforces a fraction requirement a/b = c
    """

    def __init__(
        self,
        numerator,
        denominator=None,
        sense=const.LpConstraintEQ,
        RHS=1.0,
        name=None,
        complement=None,
    ):
        """
        creates a fraction Constraint to model constraints of
        the nature
        numerator/denominator {==, >=, <=} RHS
        numerator/(numerator + complement) {==, >=, <=} RHS

        :param numerator: the top of the fraction
        :param denominator: as described above
        :param sense: the sense of the relation of the constraint
        :param RHS: the target fraction value
        :param complement: as described above
        """
        self.numerator = numerator
        if denominator is None and complement is not None:
            self.complement = complement
            self.denominator = numerator + complement
        elif denominator is not None and complement is None:
            self.denominator = denominator
            self.complement = denominator - numerator
        else:
            self.denominator = denominator
            self.complement = complement
        lhs = self.numerator - RHS * self.denominator
        LpConstraintExpr.__init__(self, lhs, sense=sense, rhs=0, name=name)
        self.RHS = RHS

    def findLHSValue(self):
        """
        Determines the value of the fraction in the constraint after solution
        """
        if abs(value(self.denominator)) >= const.EPS:
            return value(self.numerator) / value(self.denominator)
        else:
            if abs(value(self.numerator)) <= const.EPS:
                # zero divided by zero will return 1
                return 1.0
            else:
                raise ZeroDivisionError

    def makeElasticSubProblem(self, *args: Any, **kwargs: Any):
        """
        Builds an elastic subproblem by adding variables and splitting the
        hard constraint

        uses FractionElasticSubProblem
        """
        return FractionElasticSubProblem(self, *args, **kwargs)


class _ObjectiveView:
    """Thin view over Rust objective: .items(), .constant, .name, .sense."""

    def __init__(self, coeffs, constant: float, sense, name=None):
        self._coeffs = coeffs  # list of (Variable, float) from Rust
        self._constant = constant
        self._sense = sense
        self._name = name

    @property
    def constant(self) -> float:
        return self._constant

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def items(self):
        return [(LpVariable(v), c) for v, c in self._coeffs]

    def keys(self):
        return [LpVariable(v) for v, _ in self._coeffs]

    def values(self):
        return [c for _, c in self._coeffs]

    def value(self) -> float | None:
        """Objective value from variable values; None if any variable has no value."""
        s = self._constant
        for v, c in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * c
        return s

    def isNumericalConstant(self):
        return len(self._coeffs) == 0

    def __contains__(self, variable):
        return any(
            v is variable or v.name == variable.name
            for v, _ in self.items()
        )

    def __getitem__(self, variable):
        for v, c in self.items():
            if v is variable or v.name == variable.name:
                return c
        raise KeyError(variable)

    def __iter__(self):
        return iter(self.keys())

    def __neg__(self):
        return _ObjectiveView(
            [(v, -c) for v, c in self._coeffs],
            -self._constant,
            self._sense,
            name=self._name,
        )

    @staticmethod
    def _count_characters(line):
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name: str):
        result = []
        line = [f"{name}:"]
        not_first = 0
        for v, val in self.items():
            if val < 0:
                sign = " -"
                val = -val
            elif not_first:
                sign = " +"
            else:
                sign = ""
            not_first = 1
            term = f"{sign} {val + 0:.12g} {v.name}" if val != 1 else f"{sign} {v.name}"
            if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
                result += ["".join(line)]
                line = [term]
            else:
                line += [term]
        return result, line

    def asCplexLpAffineExpression(
        self, name: str, include_constant: bool = True, override_constant=None
    ):
        result, line = self.asCplexVariablesOnly(name)
        if include_constant:
            c = override_constant if override_constant is not None else self._constant
            term = f" - {-c:.12g}" if c < 0 else (f" + {c}" if c > 0 else " 0")
            result += ["".join(line) + term]
        else:
            result += ["".join(line)]
        return "%s\n" % "\n".join(result)

    def toDataclass(self):
        return [mpslp.MPSCoefficient(name=v.name, value=c) for v, c in self.items()]


class LpProblem:
    """An LP Problem"""

    def __init__(self, name="NoName", sense=const.LpMinimize):
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

        self._model = _rustcore.Model(self.name)  # type: ignore[attr-defined]

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
            _rustcore.Category.Binary  # type: ignore[attr-defined]
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer  # type: ignore[attr-defined]
                if cat == const.LpInteger
                else _rustcore.Category.Continuous  # type: ignore[attr-defined]
            )
        )
        rvar = self._model.add_variable(name, lb, ub, rcat)  # type: ignore[union-attr]
        return LpVariable(rvar)

    def add_variable_dicts(
        self,
        name: str,
        indices=None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart=None,
    ) -> dict:
        """Create a dictionary of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = indices[0]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = (
            _rustcore.Category.Binary  # type: ignore[attr-defined]
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer  # type: ignore[attr-defined]
                if cat == const.LpInteger
                else _rustcore.Category.Continuous  # type: ignore[attr-defined]
            )
        )
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [str(i)]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)  # type: ignore[union-attr]
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
            _rustcore.Category.Binary  # type: ignore[attr-defined]
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer  # type: ignore[attr-defined]
                if cat == const.LpInteger
                else _rustcore.Category.Continuous  # type: ignore[attr-defined]
            )
        )
        vars_ = self._model.add_variables_batch(names, lb, ub, rcat)  # type: ignore[union-attr]
        return {i: LpVariable(v) for i, v in zip(index, vars_)}

    def add_variable_matrix(
        self,
        name: str,
        indices=None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart=None,
    ):
        """Create a list or nested list of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = indices[0]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = (
            _rustcore.Category.Binary  # type: ignore[attr-defined]
            if cat == const.LpBinary
            else (
                _rustcore.Category.Integer  # type: ignore[attr-defined]
                if cat == const.LpInteger
                else _rustcore.Category.Continuous  # type: ignore[attr-defined]
            )
        )
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [i]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)  # type: ignore[union-attr]
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

    def get_constraint_data(self, constraint) -> tuple:
        """Get full constraint data (name, rhs, sense, coeffs) by id or LpConstraint."""
        if isinstance(constraint, LpConstraint):
            cid = constraint._constr.id()
        elif isinstance(constraint, int):
            cid = constraint
        else:
            raise TypeError("Expected LpConstraint or int id")
        return self._model.get_constraint_data(cid)

    @property
    def objective(self):
        """Objective view from Rust (has .items(), .constant, .name, .sense)."""
        obj = self._model.get_objective()  # type: ignore[union-attr]
        if obj is None:
            return None
        coeffs, constant, sense = obj
        return _ObjectiveView(coeffs, constant, sense)

    @objective.setter
    def objective(self, value):
        """Set objective from LpAffineExpression or similar; stored in Rust."""
        if value is None:
            self._model.clear_objective()  # type: ignore[union-attr]
            return
        if isinstance(value, LpVariable):
            value = LpAffineExpression(value)
        sense = (
            _rustcore.ObjSense.Minimize  # type: ignore[attr-defined]
            if self.sense == const.LpMinimize
            else _rustcore.ObjSense.Maximize  # type: ignore[attr-defined]
        )
        if isinstance(value, LpAffineExpression):
            coeffs = value._expr.terms_with_variables(self._model)  # type: ignore[union-attr]
            cst = float(value.constant)
            self._model.set_objective(coeffs, cst, sense)  # type: ignore[union-attr]
        elif isinstance(value, _ObjectiveView):
            self._model.set_objective(value._coeffs, value._constant, sense)  # type: ignore[union-attr]

    @property
    def sense(self):
        return self._sense

    @sense.setter
    def sense(self, value):
        self._sense = value

    def __repr__(self):
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

    def copy(self):
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
            items_new = [(var_by_name[v.name], coeff) for v, coeff in items if v.name in var_by_name]
            expr = LpAffineExpression()
            expr._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
            for v_new, coeff in items_new:
                expr._expr.add_term(v_new._var, coeff)  # type: ignore[union-attr]
            expr._expr.set_constant(0)  # type: ignore[union-attr]
            expr.constant = 0
            lpcopy.addConstraint(
                LpConstraintExpr(expr, c.sense, name=name, rhs=-c.constant),
                name=name,
            )
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def deepcopy(self):
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

    def toRustModel(self):
        """
        Return the Rust-backed model for this problem, if available.

        When the compiled extension ``pulp._rustcore`` is present, each
        :class:`LpProblem` maintains an internal Rust ``Model`` that mirrors
        variables, objective, and constraints as they are created.

        :raises RuntimeError: if the Rust extension is not available.
        """
        if not self._rust_enabled():
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
        pb += LpAffineExpression(e=obj_e, name=mps.objective.name)

        # constraints
        for c in mps.constraints:
            pb += LpConstraintExpr.fromDataclass(c, var)

        # last, parameters, other options
        pb.sos1 = dict(enumerate(mps.sos1))
        pb.sos2 = dict(enumerate(mps.sos2))

        return var, pb

    def toDict(self):
        return dataclasses.asdict(self.toDataclass())

    def to_dict(self):
        warnings.warn(
            "LpProblem.to_dict is deprecated, use LpProblem.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()

    @classmethod
    def fromDict(cls, data: dict[Any, Any]):
        return cls.fromDataclass(
            mpslp.MPS.fromDict(data), objective_negate_for_max=False
        )

    @classmethod
    def from_dict(cls, data: dict[Any, Any]):
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
    def from_json(cls, filename: str):
        warnings.warn(
            "LpProblem.from_json is deprecated, use LpProblem.fromJson instead",
            category=DeprecationWarning,
        )
        return cls.fromJson(filename)

    @classmethod
    def fromMPS(
        cls, filename: str, sense: int = const.LpMinimize, dropConsNames: bool = False
    ):
        data = mpslp.readMPS(filename, sense=sense, dropConsNames=dropConsNames)
        return cls.fromDataclass(data)

    def normalisedNames(self):
        constraintsNames = {k: "C%07d" % i for i, k in enumerate(self.constraints)}
        _variables = self.variables()
        self._variables = _variables  # used by writeMPS after rename
        variablesNames = {k.name: "X%07d" % i for i, k in enumerate(_variables)}
        return constraintsNames, variablesNames, "OBJ"

    def isMIP(self):
        for v in self.variables():
            if v.cat == const.LpInteger:
                return 1
        return 0

    def roundSolution(self, epsInt=1e-5, eps=1e-7):
        """
        Rounds the lp variables

        Inputs:
            - none

        Side Effects:
            - The lp variables are rounded
        """
        for v in self.variables():
            v.round(epsInt, eps)

    def valid(self, eps=0):
        for v in self.variables():
            if not v.valid(eps):
                return False
        for c in self.constraints.values():
            if not c.valid(eps):
                return False
        else:
            return True

    def infeasibilityGap(self, mip=1):
        gap = 0
        for v in self.variables():
            gap = max(abs(v.infeasibilityGap(mip)), gap)
        for c in self.constraints.values():
            if not c.valid(0):
                gap = max(abs(c.value()), gap)
        return gap

    def addVariable(self, variable: LpVariable):
        """No-op: variables are only created via add_variable/add_variables_batch."""
        pass

    def addVariables(self, variables: Iterable[LpVariable]):
        """No-op: variables are only created via add_variable/add_variables_batch."""
        pass

    def variables(self) -> list[LpVariable]:
        """Returns the problem variables from the Rust model."""
        return [LpVariable(v) for v in self._model.list_variables()]

    def variablesDict(self):
        """Dict of variable name -> LpVariable, using same order as variables()."""
        return {v.name: v for v in self.variables()}

    def add(self, constraint, name=None):
        self.addConstraint(constraint, name)

    def addConstraint(self, constraint: "LpConstraint | LpConstraintExpr", name=None):
        if name and isinstance(constraint, LpConstraintExpr):
            constraint.name = name
        if isinstance(constraint, LpConstraint):
            pass
        else:
            cname = constraint.name or ""
            expr = constraint.expr
            coeffs = expr._expr.terms_with_variables(self._model)
            rhs = -constraint._normalized_rhs()
            sense = (
                _rustcore.Sense.LessEqual  # type: ignore[attr-defined]
                if constraint.sense == const.LpConstraintLE
                else (
                    _rustcore.Sense.GreaterEqual  # type: ignore[attr-defined]
                    if constraint.sense == const.LpConstraintGE
                    else _rustcore.Sense.Equal  # type: ignore[attr-defined]
                )
            )
            self._model.add_constraint(cname, coeffs, rhs, sense)  # type: ignore[union-attr]

    def setObjective(self, obj):
        """
        Sets the objective function.

        :param obj: the objective function (LpAffineExpression, LpVariable, or numeric)

        Side Effects:
            - The objective function is set
        """
        if isinstance(obj, LpVariable):
            obj = obj + 0.0
        self.objective = obj

    def __iadd__(self, other):
        if isinstance(other, tuple):
            other, name = other
        else:
            name = None
        if other is True:
            return self
        elif other is False:
            raise TypeError("A False object cannot be passed as a constraint")
        elif isinstance(other, (LpConstraint, LpConstraintExpr)):
            self.addConstraint(other, name)
        elif isinstance(other, LpAffineExpression):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = other
        elif isinstance(other, LpVariable) or isinstance(other, (int, float)):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression(other)
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
                self.addConstraint(constraint, name=name)
        elif isinstance(other, LpProblem):
            for v in set(other.variables()).difference(self.variables()):
                v.name = other.name + v.name
            for name, c in other.constraints.items():
                self.addConstraint(c.copy(), name=other.name + name)
            if use_objective:
                if other.objective is None:
                    raise ValueError("Objective not set by provided problem")
                if isinstance(self.objective, _ObjectiveView):
                    obj = LpAffineExpression(
                        e=dict(self.objective.items()), constant=self.objective.constant
                    )
                    if isinstance(other.objective, _ObjectiveView):
                        obj.addInPlace(
                            LpAffineExpression(
                                e=dict(other.objective.items()),
                                constant=other.objective.constant,
                            )
                        )
                    else:
                        obj.addInPlace(other.objective)
                    self.objective = obj
                else:
                    self.objective += other.objective
        else:
            for c in other:  # type: ignore[assignment]
                if isinstance(c, tuple):
                    name = c[0]
                    c = c[1]
                else:
                    name = None
                if not name:
                    name = c.name
                self.addConstraint(c, name=name or None)

    def coefficients(self, translation=None):
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
        self, filename, mpsSense=0, rename=0, mip=1, with_objsense: bool = False
    ):
        """
        Writes an mps files from the problem information

        :param str filename: name of the file to write
        :param int mpsSense:
        :param bool rename: if True, normalized names are used for variables and constraints
        :param mip: variables and variable renames
        :return:

        Side Effects:
            - The file is created
        """
        return mpslp.writeMPS(
            self,
            filename,
            mpsSense=mpsSense,
            rename=rename,
            mip=mip,
            with_objsense=with_objsense,
        )

    def writeLP(self, filename, writeSOS=1, mip=1, max_length=100):
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
        name_counter = Counter(variable.name for variable in self.variables())
        repeated_names = {
            (name, count) for name, count in name_counter.items() if count >= 2
        }
        if repeated_names:
            raise const.PulpError(f"Repeated variable names: {repeated_names}")

    def checkLengthVars(self, max_length: int) -> None:
        """
        Checks if variables have names smaller than `max_length`
        :param int max_length: max size for variable name
        :return:
        :raises const.PulpError: if there is at least one variable that has a long name
        """
        long_names = [
            variable.name
            for variable in self.variables()
            if len(variable.name) > max_length
        ]
        if long_names:
            raise const.PulpError(
                f"Variable names too long for Lp format: {long_names}"
            )

    def assignVarsVals(self, values):
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_values_by_name(filtered)

    def assignVarsDj(self, values):
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_djs_by_name(filtered)

    def assignConsPi(self, values):
        self._model.set_constraint_pis_by_name(dict(values))

    def assignConsSlack(self, values, activity=False):
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

    def get_dummyVar(self):
        if self.dummyVar is None:
            self.dummyVar = self.add_variable("__dummy", 0, 0)
        return self.dummyVar

    def fixObjective(self):
        if self.objective is None:
            self.objective = LpAffineExpression(0)
            wasNone = True
        else:
            wasNone = False

        if self.objective.isNumericalConstant():
            dummyVar = self.get_dummyVar()
            self.objective += dummyVar
        else:
            dummyVar = None

        return wasNone, dummyVar

    def restoreObjective(self, wasNone, dummyVar):
        if wasNone:
            self.objective = None
        elif not dummyVar is None:
            self.objective -= dummyVar

    def solve(self, solver=None, **kwargs):
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
        wasNone, dummyVar = self.fixObjective()
        # time it
        self.startClock()
        status = solver.actualSolve(self, **kwargs)
        self.stopClock()
        self.restoreObjective(wasNone, dummyVar)
        self.solver = solver
        return status

    def startClock(self):
        "initializes properties with the current time"
        self.solutionCpuTime = -clock()
        self.solutionTime = -time()

    def stopClock(self):
        "updates time wall time and cpu time"
        self.solutionTime += time()
        self.solutionCpuTime += clock()

    def sequentialSolve(
        self, objectives, absoluteTols=None, relativeTols=None, solver=None, debug=False
    ):
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

    def resolve(self, solver=None, **kwargs):
        """
        Re-solves the problem using the same solver as previously.
        """
        return self.solve(solver=solver, **kwargs)

    def setSolver(self, solver=LpSolverDefault):
        """Sets the Solver for this problem useful if you are using
        resolve
        """
        self.solver = solver

    def numVariables(self):
        """

        :return: number of variables in model
        """
        return len(self.variables())

    def numConstraints(self):
        """

        :return: number of constraints in model
        """
        return len(self.constraints)

    def getSense(self):
        return self.sense

    def assignStatus(self, status, sol_status=None):
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


class FixedElasticSubProblem(LpProblem):
    """
    Contains the subproblem generated by converting a fixed constraint
    :math:`\\sum_{i}a_i x_i = b` into an elastic constraint.

    :param constraint: The LpConstraint that the elastic constraint is based on
    :param penalty: penalty applied for violation (+ve or -ve) of the constraints
    :param proportionFreeBound:
        the proportional bound (+ve and -ve) on
        constraint violation that is free from penalty
    :param proportionFreeBoundList: the proportional bound on \
        constraint violation that is free from penalty, expressed as a list\
        where [-ve, +ve]
    """

    def __init__(
        self,
        constraint: LpConstraint,
        penalty: float | None = None,
        proportionFreeBound: float | None = None,
        proportionFreeBoundList: tuple[float, float] | None = None,
    ):
        subProblemName = f"{constraint.name}_elastic_SubProblem"
        super().__init__(subProblemName, const.LpMinimize)
        self.constraint = constraint
        self.constant = constraint.constant
        self.RHS = -constraint.constant
        # If constraint is already in model (LpConstraint), get pending copy to modify
        if isinstance(constraint, LpConstraint):
            constraint = constraint.copy()
        # create and add these variables but disabled (use problem so Rust-backed)
        self.freeVar = self.add_variable("_free_bound", 0, 0)
        self.upVar = self.add_variable("_pos_penalty_var", 0, 0)
        self.lowVar = self.add_variable("_neg_penalty_var", 0, 0)
        constraint.addInPlace(self.freeVar + self.lowVar + self.upVar)
        self += constraint, "_Constraint"
        if proportionFreeBound:
            proportionFreeBoundList = (proportionFreeBound, proportionFreeBound)
        if proportionFreeBoundList:
            # add a costless variable
            self.freeVar.upBound = abs(constraint.constant * proportionFreeBoundList[0])
            self.freeVar.lowBound = -abs(
                constraint.constant * proportionFreeBoundList[1]
            )
            # Note the reversal of the upbound and lowbound due to the nature of the
            # variable
        if penalty is not None:
            # activate these variables
            self.upVar.upBound = None
            self.lowVar.lowBound = None
            self.objective = penalty * self.upVar - penalty * self.lowVar
        else:
            self.objective = LpAffineExpression()

    def _findValue(self, attrib: str) -> float:
        """
        Return the value of the elastic variable for the given attribute name.
        attrib is one of "freeVar", "upVar", "lowVar" (always set in __init__).
        """
        if attrib == "freeVar":
            var = self.freeVar
        elif attrib == "upVar":
            var = self.upVar
        elif attrib == "lowVar":
            var = self.lowVar
        else:
            return 0.0
        if var:
            val = value(var)
            return val if val is not None else 0.0
        return 0.0

    def isViolated(self):
        """
        returns true if the penalty variables are non-zero
        """
        upVar = self._findValue("upVar")
        lowVar = self._findValue("lowVar")
        freeVar = self._findValue("freeVar")
        result = abs(upVar + lowVar) >= const.EPS
        if result:
            log.debug(
                "isViolated %s, upVar %s, lowVar %s, freeVar %s result %s"
                % (self.name, upVar, lowVar, freeVar, result)
            )
            log.debug(f"isViolated value lhs {self.findLHSValue()} constant {self.RHS}")
        return result

    def findDifferenceFromRHS(self) -> float:
        """
        The amount the actual value varies from the RHS (sense: LHS - RHS)
        """
        return self.findLHSValue() - self.RHS

    def findLHSValue(self) -> float:
        """
        for elastic constraints finds the LHS value of the constraint without
        the free variable and or penalty variable assumes the constant is on the
        rhs
        """
        upVar = self._findValue("upVar")
        lowVar = self._findValue("lowVar")
        freeVar = self._findValue("freeVar")
        constraint = self.constraint.value()
        if constraint is None:
            raise ValueError("Constraint has no value")
        return constraint - self.constant - upVar - lowVar - freeVar

    def deElasticize(self):
        """de-elasticize constraint"""
        self.upVar.upBound = 0
        self.lowVar.lowBound = 0

    def reElasticize(self):
        """
        Make the Subproblem elastic again after deElasticize
        """
        self.upVar.lowBound = 0
        self.upVar.upBound = None
        self.lowVar.upBound = 0
        self.lowVar.lowBound = None

    def alterName(self, name: str):
        """
        Alters the name of anonymous parts of the problem
        """
        self.name = f"{name}_elastic_SubProblem"
        if hasattr(self, "freeVar"):
            self.freeVar.name = self.name + "_free_bound"
        if hasattr(self, "upVar"):
            self.upVar.name = self.name + "_pos_penalty_var"
        if hasattr(self, "lowVar"):
            self.lowVar.name = self.name + "_neg_penalty_var"


class FractionElasticSubProblem(FixedElasticSubProblem):
    """
    Contains the subproblem generated by converting a Fraction constraint
    numerator/(numerator+complement) = b
    into an elastic constraint

    :param name: The name of the elastic subproblem
    :param penalty: penalty applied for violation (+ve or -ve) of the constraints
    :param proportionFreeBound: the proportional bound (+ve and -ve) on
        constraint violation that is free from penalty
    :param proportionFreeBoundList: the proportional bound on
        constraint violation that is free from penalty, expressed as a list
        where [-ve, +ve]
    """

    def __init__(
        self,
        name,
        numerator,
        RHS,
        sense,
        complement=None,
        denominator=None,
        penalty=None,
        proportionFreeBound=None,
        proportionFreeBoundList=None,
    ):
        subProblemName = f"{name}_elastic_SubProblem"
        self.numerator = numerator
        if denominator is None and complement is not None:
            self.complement = complement
            self.denominator = numerator + complement
        elif denominator is not None and complement is None:
            self.denominator = denominator
            self.complement = denominator - numerator
        else:
            raise const.PulpError(
                "only one of denominator and complement must be specified"
            )
        self.RHS = RHS
        self.lowTarget = self.upTarget = None
        LpProblem.__init__(self, subProblemName, const.LpMinimize)
        self.freeVar = self.add_variable("_free_bound", 0, 0)
        self.upVar = self.add_variable("_pos_penalty_var", 0, 0)
        self.lowVar = self.add_variable("_neg_penalty_var", 0, 0)
        if proportionFreeBound:
            proportionFreeBoundList = [proportionFreeBound, proportionFreeBound]
        if proportionFreeBoundList:
            upProportionFreeBound, lowProportionFreeBound = proportionFreeBoundList
        else:
            upProportionFreeBound, lowProportionFreeBound = (0, 0)
        # create an objective
        self += LpAffineExpression()
        # There are three cases if the constraint.sense is ==, <=, >=
        if sense in [const.LpConstraintEQ, const.LpConstraintLE]:
            # create a constraint the sets the upper bound of target
            self.upTarget = RHS + upProportionFreeBound
            self.upConstraint = LpFractionConstraint(
                self.numerator,
                self.complement,
                const.LpConstraintLE,
                self.upTarget,
                denominator=self.denominator,
            )
            if penalty is not None:
                self.lowVar.lowBound = None
                self.objective += -1 * penalty * self.lowVar
                self.upConstraint += self.lowVar
            self += self.upConstraint, "_upper_constraint"
        if sense in [const.LpConstraintEQ, const.LpConstraintGE]:
            # create a constraint the sets the lower bound of target
            self.lowTarget = RHS - lowProportionFreeBound
            self.lowConstraint = LpFractionConstraint(
                self.numerator,
                self.complement,
                const.LpConstraintGE,
                self.lowTarget,
                denominator=self.denominator,
            )
            if penalty is not None:
                self.upVar.upBound = None
                self.objective += penalty * self.upVar
                self.lowConstraint += self.upVar
            self += self.lowConstraint, "_lower_constraint"

    def findLHSValue(self):
        """
        for elastic constraints finds the LHS value of the constraint without
        the free variable and or penalty variable assumes the constant is on the
        rhs
        """
        # uses code from LpFractionConstraint
        if abs(value(self.denominator)) >= const.EPS:
            return value(self.numerator) / value(self.denominator)
        else:
            if abs(value(self.numerator)) <= const.EPS:
                # zero divided by zero will return 1
                return 1.0
            else:
                raise ZeroDivisionError

    def isViolated(self):
        """
        returns true if the penalty variables are non-zero
        """
        if abs(value(self.denominator)) >= const.EPS:
            if self.lowTarget is not None:
                if self.lowTarget > self.findLHSValue():
                    return True
            if self.upTarget is not None:
                if self.findLHSValue() > self.upTarget:
                    return True
        else:
            # if the denominator is zero the constraint is satisfied
            return False


def lpSum(
    vector: (
        Iterable[LpAffineExpression | LpVariable | int | float]
        | Iterable[tuple[LpVariable, float]]
        | int
        | float
        | LpVariable
    ),
):
    """
    Calculate the sum of a list of linear expressions

    :param vector: A list of linear expressions
    """
    return LpAffineExpression().addInPlace(vector)


def _vector_like(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, LpAffineExpression)


def lpDot(v1, v2):
    """Calculate the dot product of two lists of linear expressions"""
    if not _vector_like(v1) and not _vector_like(v2):
        return v1 * v2
    elif not _vector_like(v1):
        return lpDot([v1] * len(v2), v2)
    elif not _vector_like(v2):
        return lpDot(v1, [v2] * len(v1))
    else:
        return lpSum([lpDot(e1, e2) for e1, e2 in zip(v1, v2)])
