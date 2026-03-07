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

* ``LpConstraintVar`` -- A special type of constraint for constructing column of the model in column-wise modelling

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


class LpElement:
    """Base class for LpVariable and LpConstraintVar"""

    # To remove illegal characters from the names
    illegal_chars = "-+[] ->/"
    expression = re.compile(f"[{re.escape(illegal_chars)}]")
    trans = str.maketrans(illegal_chars, "________")

    def setName(self, name):
        if name:
            if self.expression.match(name):
                warnings.warn(
                    "The name {} has illegal characters that will be replaced by _".format(
                        name
                    )
                )
            self.__name = str(name).translate(self.trans)
        else:
            self.__name = None

    def getName(self):
        return self.__name

    name = property(fget=getName, fset=setName)

    def __init__(self, name):
        self.name = name
        self.modified = True

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __neg__(self):
        return -LpAffineExpression(self)

    def __pos__(self):
        return self

    def __bool__(self) -> bool:
        return True

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

    def __eq__(self, other):
        return LpAffineExpression(self) == other

    def __ne__(self, other):
        if isinstance(other, LpVariable):
            return self.name is not other.name
        elif isinstance(other, (LpAffineExpression, LpConstraint)):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return True
        else:
            return True


def _rust_cat_to_const(rust_cat):
    if rust_cat == _rustcore.Category.Continuous:
        return const.LpContinuous
    if rust_cat == _rustcore.Category.Integer:
        return const.LpInteger
    if rust_cat == _rustcore.Category.Binary:
        return const.LpInteger  # Binary as Integer 0-1
    return const.LpContinuous


def _inf_to_none(x: float):
    if x == float("-inf") or x <= -1e30:
        return None
    if x == float("inf") or x >= 1e30:
        return None
    return x


class LpVariable(LpElement):
    """
    Thin wrapper over the Rust Variable. Created only via
    LpProblem.add_variable() or add_variable_dicts/dict/matrix.
    """

    def __init__(self, _var):
        self._var = _var
        LpElement.__init__(self, _var.name)

    @property
    def name(self) -> str:
        return self._var.name

    @name.setter
    def name(self, value: str) -> None:
        self._var.set_name(value)  # type: ignore[union-attr]

    def __hash__(self) -> int:
        return hash(self._var.id())

    def __eq__(self, other: object):
        if isinstance(other, LpVariable):
            return self._var.id() == other._var.id()
        if isinstance(other, (int, float)):
            return LpAffineExpression(self) == other
        return NotImplemented

    @property
    def lowBound(self) -> Optional[float]:
        return _inf_to_none(self._var.lb)

    @lowBound.setter
    def lowBound(self, value: Optional[float]) -> None:
        lb = float("-inf") if value is None else value
        self._var.set_lb(lb)  # type: ignore[union-attr]

    @property
    def upBound(self) -> Optional[float]:
        return _inf_to_none(self._var.ub)

    @upBound.setter
    def upBound(self, value: Optional[float]) -> None:
        ub = float("inf") if value is None else value
        self._var.set_ub(ub)  # type: ignore[union-attr]

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

    dj = None  # placeholder; can be extended if Rust stores dual

    def toDataclass(self) -> mpslp.MPSVariable:
        """
        Exports a variable into a dataclass with its relevant information

        :return: a :py:class:`mpslp.MPSVariable` with the variable information
        :rtype: :mpslp.MPSVariable
        """
        return mpslp.MPSVariable(
            lowBound=self.lowBound,
            upBound=self.upBound,
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

    def add_expression(self, e):
        """Column-based modelling: add variable to constraints in e."""
        self.addVariableToConstraints(e)

    def getLb(self):
        return self.lowBound

    def getUb(self):
        return self.upBound

    def bounds(self, low, up):
        lb = float("-inf") if low is None else low
        ub = float("inf") if up is None else up
        self._var.set_lb(lb)
        self._var.set_ub(ub)
        self.modified = True

    def positive(self):
        self.bounds(0, None)

    def value(self):
        return self._var.value

    def round(self, epsInt=1e-5, eps=1e-7):
        if self.varValue is not None:
            if (
                self.upBound != None
                and self.varValue > self.upBound
                and self.varValue <= self.upBound + eps
            ):
                self.varValue = self.upBound
            elif (
                self.lowBound is not None
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
        elif self.lowBound is not None:
            if self.upBound is not None:
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
        elif self.upBound is not None:
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
        if self.upBound is not None and self.varValue > self.upBound + eps:
            return False
        if self.lowBound is not None and self.varValue < self.lowBound - eps:
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
        if self.upBound is not None and self.varValue > self.upBound:
            return self.varValue - self.upBound
        if self.lowBound is not None and self.varValue < self.lowBound:
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
        return self.lowBound is None and self.upBound is None

    def isConstant(self):
        return self.lowBound is not None and self.upBound == self.lowBound

    def isPositive(self):
        return self.lowBound == 0 and self.upBound is None

    def asCplexLpVariable(self):
        if self.isFree():
            return self.name + " free"
        if self.isConstant():
            return self.name + f" = {self.lowBound:.12g}"
        if self.lowBound is None:
            s = "-inf <= "
        # Note: XPRESS and CPLEX do not interpret integer variables without
        # explicit bounds
        elif self.lowBound == 0 and self.cat == const.LpContinuous:
            s = ""
        else:
            s = f"{self.lowBound:.12g} <= "
        s += self.name
        if self.upBound is not None:
            s += f" <= {self.upBound:.12g}"
        return s

    def asCplexLpAffineExpression(self, name, include_constant: bool = True):
        return LpAffineExpression(self).asCplexLpAffineExpression(
            name, include_constant
        )

    def __ne__(self, other):
        if isinstance(other, LpElement):
            return self.name is not other.name
        elif isinstance(other, (LpAffineExpression, LpConstraint)):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return True
        else:
            return True

    def __bool__(self):
        return bool(self.roundedValue())

    def addVariableToConstraints(self, e):
        """adds a variable to the constraints indicated by
        the LpConstraintVars in e
        """
        for constraint, coeff in e.items():
            constraint.addVariable(self, coeff)

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


class LpAffineExpression(dict):
    __name: str
    constant: float
    """
    A linear combination of :class:`LpVariables<LpVariable>`.
    Can be initialised with the following:

    #.   e = None: an empty Expression
    #.   e = dict: gives an expression with the values being the coefficients of the keys (order of terms is undetermined)
    #.   e = list or generator of 2-tuples: equivalent to dict.items()
    #.   e = LpElement: an expression of length 1 with the coefficient 1
    #.   e = other: the constant is initialised as e

    Examples:

       >>> f=LpAffineExpression(LpElement('x'))
       >>> f
       1*x + 0
       >>> x_name = ['x_0', 'x_1', 'x_2']
       >>> x = [LpVariable(x_name[i], lowBound = 0, upBound = 10) for i in range(3) ]
       >>> c = LpAffineExpression([ (x[0],1), (x[1],-3), (x[2],4)])
       >>> c
       1*x_0 + -3*x_1 + 4*x_2 + 0
    """

    # to remove illegal characters from the names
    trans = str.maketrans("-+[] ", "_____")

    @property
    def name(self) -> str | None:
        return self.__name

    @name.setter
    def name(self, name: str | None):
        if name:
            self.__name = str(name).translate(self.trans)
        else:
            self.__name = None  # type: ignore[assignment]

    def __init__(self, e=None, constant: float = 0.0, name: str | None = None, _expr=None):
        self.name = name
        if _expr is not None:
            self._expr = _expr
            self.constant = _expr.constant
            super().__init__()
            return
        # TODO remove isinstance usage
        if e is None:
            e = {}
        if not math.isfinite(constant):
            raise const.PulpError(
                f"Invalid constant value: {constant}. It must be a finite number."
            )
        if isinstance(e, (LpAffineExpression, LpConstraint)):
            self.constant = e.constant
            super().__init__(e.items())
        elif isinstance(e, dict):
            self.constant = constant
            super().__init__(e.items())
        elif isinstance(e, Iterable):
            self.constant = constant
            super().__init__(e)
        elif isinstance(e, LpElement):
            self.constant = 0
            super().__init__([(e, 1)])
        else:
            self.constant = e
            super().__init__()
        # Keep Rust _expr in sync for constraint/objective push to Rust
        self._expr = None
        if e is None or (isinstance(e, dict) and len(e) == 0):
            self._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
        elif isinstance(e, LpVariable):
            self._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
            self._expr.add_term(e._var, 1)  # type: ignore[union-attr]
        elif isinstance(e, (LpAffineExpression, LpConstraint)) and getattr(e, "_expr", None) is not None:
            self._expr = e._expr.clone_expr()  # type: ignore[union-attr]
        elif isinstance(e, (int, float)) and math.isfinite(e):
            self._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
            self._expr.set_constant(float(e))  # type: ignore[union-attr]
        else:
            self._expr = _rustcore.AffineExpr()  # type: ignore[attr-defined]
            self._expr.set_constant(self.constant)  # type: ignore[union-attr]

    # Proxy functions for variables

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self):
        return len(self) == 0

    def atom(self):
        return next(iter(self.keys()))

    # Functions on expressions

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

    def addterm(self, key: LpElement, value: float | int):
        if key in self:
            self[key] += value
        else:
            self[key] = value

    def __setitem__(self, key: LpElement, value: float | int):
        old = self.get(key, 0.0)
        super().__setitem__(key, value)
        if getattr(self, "_expr", None) is not None and isinstance(key, LpVariable):
            delta = float(value) - float(old)
            self._expr.add_term(key._var, delta)  # type: ignore[union-attr]

    def emptyCopy(self):
        return LpAffineExpression()

    def copy(self):
        """Make a copy of self except the name which is reset"""
        # Will not copy the name
        return LpAffineExpression(self)

    @staticmethod
    def _str_coeff(c: float) -> str:
        """Format coefficient for __str__: int when whole number, else float."""
        c = float(c)
        return str(int(c)) if c == int(c) else str(c)

    def __str__(
        self, include_constant: bool = True, override_constant: float | None = None
    ):
        s = ""
        for v in self.sorted_keys():
            val = self[v]
            if val < 0:
                if s != "":
                    s += " - "
                else:
                    s += "-"
                val = -val
            elif s != "":
                s += " + "
            if val == 1:
                s += str(v)
            else:
                s += self._str_coeff(val) + "*" + str(v)
        if include_constant:
            constant = self.constant if override_constant is None else override_constant
            if s == "":
                s = str(constant)
            else:
                if constant < 0:
                    s += " - " + str(-constant)
                elif constant > 0:
                    s += " + " + str(constant)
        elif s == "":
            s = "0"
        return s

    def sorted_keys(self) -> list[LpElement]:
        """
        returns the list of keys sorted by name
        """
        result = list(self.keys())
        result.sort(key=lambda v: v.name)
        return result

    def __repr__(self, override_constant: float | None = None):
        constant = self.constant if override_constant is None else override_constant
        l = [f"{float(self[v])}*{v}" for v in self.sorted_keys()]
        l.append(str(float(constant)))
        s = " + ".join(l)
        return s

    @staticmethod
    def _count_characters(line):
        # counts the characters in a list of strings
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name: str):
        """
        helper for asCplexLpAffineExpression
        """
        result = []
        line = [f"{name}:"]
        notFirst = 0
        variables = self.sorted_keys()
        for v in variables:
            val = self[v]
            if val < 0:
                sign = " -"
                val = -val
            elif notFirst:
                sign = " +"
            else:
                sign = ""
            notFirst = 1
            if val == 1:
                term = f"{sign} {v.name}"
            else:
                # adding zero to val to remove instances of negative zero
                term = f"{sign} {val + 0:.12g} {v.name}"

            if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
                result += ["".join(line)]
                line = [term]
            else:
                line += [term]
        return result, line

    def asCplexLpAffineExpression(
        self,
        name: str,
        include_constant: bool = True,
        override_constant: float | None = None,
    ):
        """
        returns a string that represents the Affine Expression in lp format
        """
        # refactored to use a list for speed in iron python
        result, line = self.asCplexVariablesOnly(name)
        if not self:
            term = f" {self.constant}"
        else:
            term = ""
            if include_constant:
                constant = (
                    self.constant if override_constant is None else override_constant
                )

                if constant < 0:
                    term = " - %s" % (-constant)
                elif constant > 0:
                    term = f" + {constant}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def addInPlace(self, other, sign: Literal[+1, -1] = 1):
        if isinstance(other, int) and (other == 0):
            return self
        if other is None:
            return self
        if isinstance(other, LpElement):
            self.addterm(other, sign)
            if getattr(self, "_expr", None) is not None and isinstance(other, LpVariable):
                self._expr.add_term(other._var, sign)  # type: ignore[union-attr]
        elif isinstance(other, (LpAffineExpression, LpConstraint)):
            self.constant += other.constant * sign
            if getattr(self, "_expr", None) is not None and getattr(other, "_expr", None) is not None:
                # Both have _expr: update dict and _expr without __setitem__ (so _expr updated once per term)
                for v, x in other.items():
                    super().__setitem__(v, self.get(v, 0) + x * sign)
                    if isinstance(v, LpVariable):
                        self._expr.add_term(v._var, float(x * sign))  # type: ignore[union-attr]
                self._expr.set_constant(
                    self._expr.constant + float(other.constant * sign)
                )  # type: ignore[union-attr]
            else:
                for v, x in other.items():
                    self.addterm(v, x * sign)
                if getattr(self, "_expr", None) is not None and getattr(other, "_expr", None) is None:
                    self._expr = None  # other has no _expr, can't keep in sync
        elif isinstance(other, dict):
            for e in other.values():
                self.addInPlace(e, sign=sign)
        elif isinstance(other, Iterable):
            for e in other:
                self.addInPlace(e, sign=sign)
        elif not math.isfinite(other):
            raise const.PulpError("Cannot add/subtract NaN/inf values")
        else:
            self.constant += other * sign
            if getattr(self, "_expr", None) is not None:
                self._expr.set_constant(self._expr.constant + other * sign)  # type: ignore[union-attr]
        return self

    def subInPlace(self, other):
        return self.addInPlace(other, sign=-1)

    def __neg__(self):
        e = self.emptyCopy()
        e.constant = -self.constant
        for v, x in self.items():
            e[v] = -x
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
        return (self).subInPlace(other)

    def __mul__(self, other):
        e = self.emptyCopy()
        if isinstance(other, (LpAffineExpression, LpConstraint)):
            e.constant = self.constant * other.constant
            if len(other):
                if len(self):
                    raise TypeError("Non-constant expressions cannot be multiplied")
                else:
                    c = self.constant
                    if c != 0:
                        for v, x in other.items():
                            e[v] = c * x
            else:
                c = other.constant
                if c != 0:
                    for v, x in self.items():
                        e[v] = c * x
        elif isinstance(other, LpVariable):
            return self * LpAffineExpression(other)
        else:
            if not math.isfinite(other):
                raise const.PulpError("Cannot multiply variables with NaN/inf values")
            elif other != 0:
                e.constant = self.constant * other
                for v, x in self.items():
                    e[v] = other * x
        return e

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        if isinstance(other, (LpAffineExpression, LpConstraint)) or isinstance(
            other, LpVariable
        ):
            if len(other):
                raise TypeError(
                    "Expressions cannot be divided by a non-constant expression"
                )
            other = other.constant
        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        e = self.emptyCopy()
        e.constant = self.constant / other
        for v, x in self.items():
            e[v] = x / other
        return e

    def __le__(self, other) -> LpConstraint:
        if isinstance(other, (int, float)):
            return LpConstraint(self, const.LpConstraintLE, rhs=other)
        else:
            return LpConstraint(self - other, const.LpConstraintLE)

    def __ge__(self, other) -> LpConstraint:
        if isinstance(other, (int, float)):
            return LpConstraint(self, const.LpConstraintGE, rhs=other)
        else:
            return LpConstraint(self - other, const.LpConstraintGE)

    def __eq__(self, other) -> LpConstraint:  # type: ignore[override]
        if isinstance(other, (int, float)):
            return LpConstraint(self, const.LpConstraintEQ, rhs=other)
        else:
            return LpConstraint(self - other, const.LpConstraintEQ)

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


class _ConstraintExprProxy:
    """Proxy for LpConstraint.expr when constraint is Rust-backed (no Python expr)."""

    def __init__(self, constraint: "LpConstraint"):
        self._constraint = constraint

    @property
    def constant(self) -> float:
        return self._constraint.constant

    def items(self):
        return self._constraint.items()

    def keys(self):
        return self._constraint.keys()

    def values(self):
        return self._constraint.values()

    def __str__(self, include_constant=True, override_constant=None):
        c = override_constant if override_constant is not None else self.constant
        parts = [f"{coeff}*{v.name}" for v, coeff in self.items()]
        return " + ".join(parts) + (f" + {c}" if c else "")

    def __repr__(self, override_constant=None):
        c = override_constant if override_constant is not None else self.constant
        return " + ".join(f"{float(coeff)}*{v.name}" for v, coeff in self.items()) + f" + {float(c)}"

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

    def asCplexLpAffineExpression(self, name: str, include_constant=True, override_constant=None):
        result, line = self.asCplexVariablesOnly(name)
        c = override_constant if override_constant is not None else self.constant
        term = f" - {-c:.12g}" if c < 0 else (f" + {c}" if c > 0 else " 0")
        result += ["".join(line) + term]
        return "%s\n" % "\n".join(result)

    def toDataclass(self):
        return [mpslp.MPSCoefficient(name=k.name, value=v) for k, v in self.items()]

    def isNumericalConstant(self):
        return len(self.items()) == 0

    def atom(self):
        items = self.items()
        return items[0][0] if items else None

    def get(self, key, default=None):
        for v, c in self.items():
            if v is key or getattr(v, "name", None) == getattr(key, "name", None):
                return c
        return default

    def copy(self):
        return LpAffineExpression(self.items())


class LpConstraint:
    """An LP constraint (input form: expr, sense, rhs; or stored form: _constr, _model)."""

    constant: float
    expr: LpAffineExpression
    __name: str | None
    sense: int
    modified: bool
    pi: float | None
    slack: float | None

    def __init__(
        self,
        e=None,
        sense: int = const.LpConstraintEQ,
        name: str | None = None,
        rhs: float | None = None,
        _constr=None,
        _model=None,
    ):
        if _constr is not None and _model is not None:
            self._constr = _constr
            self._model = _model
            self.expr = _ConstraintExprProxy(self)
            self.pi = None
            self.slack = None
            self.modified = True
            self.__name = None
            return
        self._constr = None
        self._model = None
        self.expr = e if isinstance(e, LpAffineExpression) else LpAffineExpression(e)
        self.__name = name
        # __constant is the RHS in normalized form (expr + __constant <= 0); used when pushing to Rust
        expr_const = float(self.expr.constant)
        if rhs is not None:
            if not math.isfinite(rhs):
                raise const.PulpError("Cannot set constraint RHS to NaN/inf values")
            self.__constant = expr_const - float(rhs)
        else:
            # (e, sense) form: expr <= 0 / >= 0 / == 0 => normalized RHS is 0
            self.__constant = 0.0
        self.__sense = sense
        self.pi = None
        self.slack = None
        self.modified = True

    def _get_rust_data(self):
        if self._constr is None:
            return None
        return self._model.get_constraint_data(self._constr.id())  # type: ignore[union-attr]

    def _normalized_rhs(self) -> float:
        """RHS in normalized form (expr + _normalized_rhs <= 0); use when pushing to Rust."""
        if self._constr is None:
            return self.__constant
        d = self._get_rust_data()
        return -d[1] if d else 0.0

    @property
    def name(self) -> str | None:
        if self._constr is None:
            return self.__name
        d = self._get_rust_data()
        return d[0] if d else None

    @name.setter
    def name(self, value: str | None):
        if self._constr is None:
            self.__name = value
        # no setter for Rust-backed name

    @property
    def constant(self) -> float:
        if self._constr is None:
            # For EQ (e == 0), API expects constraint.constant == -expr.constant
            if self.__sense == const.LpConstraintEQ:
                return -float(self.expr.constant)
            return self.__constant
        d = self._get_rust_data()
        if d is None:
            return 0.0
        return -d[1]  # PuLP constant = -rhs

    @constant.setter
    def constant(self, value: float):
        if self._constr is None:
            self.__constant = value
        # no setter for Rust-backed

    @property
    def sense(self) -> int:
        if self._constr is None:
            return self.__sense
        d = self._get_rust_data()
        return _rust_sense_to_const(d[2]) if d else const.LpConstraintEQ

    @sense.setter
    def sense(self, value: int):
        if self._constr is None:
            self.__sense = value

    def items(self):
        if self._constr is not None:
            d = self._get_rust_data()
            if d:
                return [(LpVariable(v), c) for v, c in d[3]]
            return []
        return list(self.expr.items()) if hasattr(self.expr, "items") else []

    def keys(self):
        return [v for v, _ in self.items()]

    def values(self):
        return [c for _, c in self.items()]

    def __getitem__(self, key):
        for v, c in self.items():
            if v is key or (getattr(v, "name", None) == getattr(key, "name", None)):
                return c
        raise KeyError(key)

    def __contains__(self, key):
        return any(v is key or getattr(v, "name", None) == getattr(key, "name", None) for v, _ in self.items())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.items())

    def getLb(self) -> float | None:
        if (self.sense == const.LpConstraintGE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
            return None

    def getUb(self) -> float | None:
        if (self.sense == const.LpConstraintLE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
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
        """
        Returns a constraint as a string
        """
        result, line = self.expr.asCplexVariablesOnly(name)
        if len(self.keys()) == 0:
            line += ["0"]
        c = -self.constant
        if c == 0:
            c = 0  # Supress sign
        term = f" {const.LpConstraintSenses[self.sense]} {c:.12g}"
        if self.expr._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def asCplexLpAffineExpression(self, name: str, include_constant: bool = True):
        """
        returns a string that represents the Affine Expression in lp format
        """
        return self.expr.asCplexLpAffineExpression(
            name, include_constant, override_constant=self.constant
        )

    def changeRHS(self, RHS: float):
        """
        alters the RHS of a constraint so that it can be modified in a resolve
        """
        self.constant = -RHS
        self.modified = True

    def copy(self):
        """Make a copy of self"""
        return LpConstraint(
            self.expr.copy(), self.sense, rhs=-self.constant + self.expr.constant
        )

    def emptyCopy(self):
        return LpConstraint(sense=self.sense)

    def addInPlace(self, other, sign: Literal[+1, -1] = 1):
        """
        :param int sign: the sign of the operation to do other.
            if we add other => 1
            if we subtract other => -1
        """
        if isinstance(other, LpConstraint):
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
        else:
            raise TypeError(f"Cannot multiple LpConstraint by {type(other)}")

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
        else:
            raise TypeError(f"Cannot divide LpConstraint by {type(other)}")

    def valid(self, eps: float = 0) -> bool:
        val = self.value()
        if val is None:
            return False
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        else:
            return val * self.sense >= -eps

    def makeElasticSubProblem(self, *args, **kwargs):
        """
        Builds an elastic subproblem by adding variables to a hard constraint

        uses FixedElasticSubProblem
        """
        return FixedElasticSubProblem(self, *args, **kwargs)

    def toDataclass(self) -> mpslp.MPSConstraint:
        """
        Exports constraint information into a :py:class:`mpslp.MPSConstraint` dataclass

        :return: :py:class:`mpslp.MPSConstraint` with all the constraint information
        """
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
    ) -> LpConstraint:
        """
        Initializes a constraint object from a :py:class:`mpslp.MPSConstraint` dataclass and variables

        :param mps: :py:class:`mpslp.MPSConstraint` containing constraint information
        :param variables: dictionary of the variables
        :return: a new :py:class:`LpConstraint`
        """
        const = cls(
            e=LpAffineExpression(
                {
                    variables[coefficient.name]: coefficient.value
                    for coefficient in mps.coefficients
                }
            ),
            sense=mps.sense,
            name=mps.name,
            rhs=-mps.constant,
        )
        const.pi = mps.pi
        return const

    @property
    def name(self) -> str | None:
        return self.__name

    @name.setter
    def name(self, name: str | None):
        if name is not None:
            self.__name = name.translate(LpAffineExpression.trans)
        else:
            self.__name = None

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and next(iter(self.values())) == 1

    def isNumericalConstant(self):
        return self.expr.isNumericalConstant()

    def atom(self):
        return self.expr.atom()

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def __len__(self):
        if self._constr is not None:
            return len(self.items())
        return len(self.expr)

    def __iter__(self):
        if self._constr is not None:
            return iter(self.keys())
        return iter(self.expr)

    def __getitem__(self, key: LpElement):
        return self.expr[key]

    def get(self, key: LpVariable, default: float | None) -> float | None:
        if self._constr is not None:
            for v, c in self.items():
                if v is key or (getattr(v, "name", None) == getattr(key, "name", None)):
                    return c
            return default
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


class LpFractionConstraint(LpConstraint):
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
        LpConstraint.__init__(self, lhs, sense=sense, rhs=0, name=name)
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


class LpConstraintVar(LpElement):
    """A Constraint that can be treated as a variable when constructing
    a LpProblem by columns
    """

    def __init__(self, name=None, sense=None, rhs=None, e=None):
        LpElement.__init__(self, name)
        self.constraint = LpConstraint(name=self.name, sense=sense, rhs=rhs, e=e)

    def __hash__(self) -> int:
        return id(self)

    def addVariable(self, var, coeff):
        """
        Adds a variable to the constraint with the
        activity coeff
        """
        self.constraint.expr.addterm(var, coeff)

    def value(self):
        return self.constraint.value()


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
            v is variable or getattr(v, "name", None) == getattr(variable, "name", None)
            for v, _ in self.items()
        )

    def __getitem__(self, variable):
        for v, c in self.items():
            if v is variable or getattr(v, "name", None) == getattr(variable, "name", None):
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
        self.noOverlap = 1
        self.solver = None
        self.solverModel = None
        self.modifiedVariables = []
        self.modifiedConstraints = []
        self.resolveOK = False
        self.dummyVar = None
        self.solutionTime = 0
        self.solutionCpuTime = 0
        self.lastUnused = 0

        self._model = _rustcore.Model(self.name)  # type: ignore[attr-defined]
        self._constraints: dict[str, LpConstraint] = {}
        self._variable_cache: dict[str, LpVariable] = {}

    def add_variable(
        self,
        name: str,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        obj=None,
    ) -> LpVariable:
        """Add a variable to the problem. Returns LpVariable wrapping the Rust variable.
        If obj is given (column-based modelling), add variable to each LpConstraintVar with the given coefficient.
        """
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
        var = LpVariable(rvar)
        self._variable_cache[var.name] = var
        if obj is not None:
            for term, coeff in obj.items():
                if isinstance(term, LpConstraintVar):
                    term.addVariable(var, coeff)
        return var

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
        """Constraints name -> LpConstraint (from Rust)."""
        return self._constraints

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
        if isinstance(value, LpAffineExpression):
            # Use dict as source of truth (constraint-style); _expr may be out of sync e.g. when built from dict
            coeffs = [(v._var, float(c)) for v, c in value.items()]
            cst = float(value.constant)
            sense = (
                _rustcore.ObjSense.Minimize  # type: ignore[attr-defined]
                if self.sense == const.LpMinimize
                else _rustcore.ObjSense.Maximize  # type: ignore[attr-defined]
            )
            self._model.set_objective(coeffs, cst, sense)  # type: ignore[union-attr]
        elif isinstance(value, _ObjectiveView):
            sense = (
                _rustcore.ObjSense.Minimize  # type: ignore[attr-defined]
                if self.sense == const.LpMinimize
                else _rustcore.ObjSense.Maximize  # type: ignore[attr-defined]
            )
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
            lpcopy.add_variable(v.name, v.lowBound, v.upBound, v.cat)
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
                LpConstraint(expr, c.sense, name=name, rhs=-c.constant),
                name=name,
            )
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def deepcopy(self):
        """Make a copy of self. Expressions are copied by value"""
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        if self.objective is not None:
            lpcopy.objective = self.objective.copy()
        lpcopy.constraints = {}
        for k, v in self.constraints.items():
            lpcopy.constraints[k] = v.copy()
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
            pb += LpConstraint.fromDataclass(c, var)

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

    def unusedConstraintName(self):
        self.lastUnused += 1
        while True:
            s = "_C%d" % self.lastUnused
            if s not in self.constraints:
                break
            self.lastUnused += 1
        return s

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
        """Returns the problem variables from the Rust model (cached so assignVarsVals/Dj update the same instances)."""
        out = []
        for v in self._model.list_variables():  # type: ignore[union-attr]
            if v.name in self._variable_cache:
                out.append(self._variable_cache[v.name])
            else:
                w = LpVariable(v)
                self._variable_cache[v.name] = w
                out.append(w)
        return out

    def variablesDict(self):
        """Dict of variable name -> LpVariable, using same order as variables()."""
        return {v.name: v for v in self.variables()}

    def add(self, constraint, name=None):
        self.addConstraint(constraint, name)

    def addConstraint(self, constraint: LpConstraint, name=None):
        if not isinstance(constraint, LpConstraint):
            raise TypeError("Can only add LpConstraint objects")
        if name:
            constraint.name = name
        try:
            cname = constraint.name
        except AttributeError:
            cname = None
        name = cname or self.unusedConstraintName()
        if name in self._constraints:
            if self.noOverlap:
                raise const.PulpError("overlapping constraint names: " + name)
            else:
                print("Warning: overlapping constraint names:", name)
        # Input constraint has .expr (LpAffineExpression with _expr), .constant, .sense
        expr = getattr(constraint, "expr", None)
        if expr is not None and hasattr(expr, "_expr"):
            # Use expr.items() (Python dict) as source of truth for coefficients
            coeffs = [(v._var, float(c)) for v, c in expr.items()]
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
            rust_constr = self._model.add_constraint(name, coeffs, rhs, sense)  # type: ignore[union-attr]
            self._constraints[name] = LpConstraint(_constr=rust_constr, _model=self._model)
        else:
            # Stored constraint (already has _constr, _model) - just store
            self._constraints[name] = constraint
        self.modifiedConstraints.append(self._constraints[name])

    def setObjective(self, obj):
        """
        Sets the input variable as the objective function. Used in Columnwise Modelling

        :param obj: the objective function of type :class:`LpConstraintVar`

        Side Effects:
            - The objective function is set
        """
        if isinstance(obj, LpVariable):
            # allows the user to add a LpVariable as an objective
            obj = obj + 0.0
        try:
            obj = obj.constraint
            name = obj.name
        except AttributeError:
            name = None
        self.objective = obj
        self.resolveOK = False

    def __iadd__(self, other):
        if isinstance(other, tuple):
            other, name = other
        else:
            name = None
        if other is True:
            return self
        elif other is False:
            raise TypeError("A False object cannot be passed as a constraint")
        elif isinstance(other, LpConstraintVar):
            self.addConstraint(other.constraint)
        elif isinstance(other, LpConstraint):
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
                "Can only add LpConstraintVar, LpConstraint, LpAffineExpression or True objects"
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
                self.constraints[name] = constraint
        elif isinstance(other, LpProblem):
            for v in set(other.variables()).difference(self.variables()):
                v.name = other.name + v.name
            for name, c in other.constraints.items():
                c.name = other.name + name
                self.addConstraint(c)
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
                if not name:
                    name = self.unusedConstraintName()
                self.constraints[name] = c

    def coefficients(self, translation=None):
        coefs = []
        if translation is None:
            for c in self.constraints:
                cst = self.constraints[c]
                coefs.extend([(v.name, c, cst[v]) for v in cst])
        else:
            for c in self.constraints:
                ctr = translation[c]
                cst = self.constraints[c]
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
        variables = self.variablesDict()
        for name in values:
            if name != "__dummy" and name in variables:
                variables[name].varValue = values[name]

    def assignVarsDj(self, values):
        variables = self.variablesDict()
        for name in values:
            if name != "__dummy":
                variables[name].dj = values[name]
        # Ensure variables not in solution file have dj set (e.g. 0) so v.dj is never None
        for name, v in variables.items():
            if name != "__dummy" and v.dj is None:
                v.dj = 0.0

    def assignConsPi(self, values):
        for name in values:
            try:
                self.constraints[name].pi = values[name]
            except KeyError:
                pass

    def assignConsSlack(self, values, activity=False):
        for name in values:
            try:
                if activity:
                    # reports the activity not the slack
                    self.constraints[name].slack = -1 * (
                        self.constraints[name].constant + float(values[name])
                    )
                else:
                    self.constraints[name].slack = float(values[name])
            except KeyError:
                pass

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
        resolves an Problem using the same solver as previously
        """
        if not (solver):
            solver = self.solver
        if self.resolveOK:
            return self.solver.actualResolve(self, **kwargs)
        else:
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
        self += constraint, "_Constraint"
        # create and add these variables but disabled (use problem so Rust-backed)
        self.freeVar = self.add_variable("_free_bound", 0, 0)
        self.upVar = self.add_variable("_pos_penalty_var", 0, 0)
        self.lowVar = self.add_variable("_neg_penalty_var", 0, 0)
        constraint.addInPlace(self.freeVar + self.lowVar + self.upVar)
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
        safe way to get the value of a variable that may not exist
        """
        var = getattr(self, attrib, 0)
        if var:
            val = value(var)
            if val is not None:
                return val
            else:
                return 0.0
        else:
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
        self.freeVar = LpVariable("_free_bound", upBound=0, lowBound=0)
        self.upVar = LpVariable("_pos_penalty_var", upBound=0, lowBound=0)
        self.lowVar = LpVariable("_neg_penalty_var", upBound=0, lowBound=0)
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
        | Iterable[tuple[LpElement, float]]
        | int
        | float
        | LpElement
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
