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

from collections import Counter
import sys
import warnings
import math
from time import time

from .apis import LpSolverDefault, PULP_CBC_CMD
from .apis.core import clock
from .utilities import value
from . import constants as const
from . import mps_lp as mpslp

from collections.abc import Iterable
import logging

log = logging.getLogger(__name__)

try:  # allow Python 2/3 compatibility
    maketrans = str.maketrans
except AttributeError:
    from string import maketrans

_DICT_TYPE = dict

if sys.platform not in ["cli"]:
    # iron python does not like an OrderedDict
    try:
        from odict import OrderedDict

        _DICT_TYPE = OrderedDict
    except ImportError:
        pass
    try:
        # python 2.7 or 3.1
        from collections import OrderedDict

        _DICT_TYPE = OrderedDict
    except ImportError:
        pass

try:
    import ujson as json
except ImportError:
    import json

import re


class LpElement:
    """Base class for LpVariable and LpConstraintVar"""

    # To remove illegal characters from the names
    illegal_chars = "-+[] ->/"
    expression = re.compile(f"[{re.escape(illegal_chars)}]")
    trans = maketrans(illegal_chars, "________")

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
        # self.hash MUST be different for each variable
        # else dict() will call the comparison operators that are overloaded
        self.hash = id(self)
        self.modified = True

    def __hash__(self):
        return self.hash

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __neg__(self):
        return -LpAffineExpression(self)

    def __pos__(self):
        return self

    def __bool__(self):
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

    def __div__(self, other):
        return LpAffineExpression(self) / other

    def __rdiv__(self, other):
        raise TypeError("Expressions cannot be divided by a variable")

    def __le__(self, other):
        return LpAffineExpression(self) <= other

    def __ge__(self, other):
        return LpAffineExpression(self) >= other

    def __eq__(self, other):
        return LpAffineExpression(self) == other

    def __ne__(self, other):
        if isinstance(other, LpVariable):
            return self.name is not other.name
        elif isinstance(other, LpAffineExpression):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return 1
        else:
            return 1


class LpVariable(LpElement):
    """
    This class models an LP Variable with the specified associated parameters

    :param name: The name of the variable used in the output .lp file
    :param lowBound: The lower bound on this variable's range.
        Default is negative infinity
    :param upBound: The upper bound on this variable's range.
        Default is positive infinity
    :param cat: The category this variable is in, Integer, Binary or
        Continuous(default)
    :param e: Used for column based modelling: relates to the variable's
        existence in the objective function and constraints
    """

    def __init__(
        self, name, lowBound=None, upBound=None, cat=const.LpContinuous, e=None
    ):
        LpElement.__init__(self, name)
        self._lowbound_original = self.lowBound = lowBound
        self._upbound_original = self.upBound = upBound
        self.cat = cat
        self.varValue = None
        self.dj = None
        if cat == const.LpBinary:
            self._lowbound_original = self.lowBound = 0
            self._upbound_original = self.upBound = 1
            self.cat = const.LpInteger
        # Code to add a variable to constraints for column based
        # modelling.
        if e:
            self.add_expression(e)

    def toDict(self):
        """
        Exports a variable into a dictionary with its relevant information

        :return: a dictionary with the variable information
        :rtype: dict
        """
        return dict(
            lowBound=self.lowBound,
            upBound=self.upBound,
            cat=self.cat,
            varValue=self.varValue,
            dj=self.dj,
            name=self.name,
        )

    to_dict = toDict

    @classmethod
    def fromDict(cls, dj=None, varValue=None, **kwargs):
        """
        Initializes a variable object from information that comes from a dictionary (kwargs)

        :param dj: shadow price of the variable
        :param float varValue: the value to set the variable
        :param kwargs: arguments to initialize the variable
        :return: a :py:class:`LpVariable`
        :rtype: :LpVariable
        """
        var = cls(**kwargs)
        var.dj = dj
        var.varValue = varValue
        return var

    from_dict = fromDict

    def add_expression(self, e):
        self.expression = e
        self.addVariableToConstraints(e)

    @classmethod
    def matrix(
        cls,
        name,
        indices=None,
        lowBound=None,
        upBound=None,
        cat=const.LpContinuous,
        indexStart=[],
    ):
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        index = indices[0]
        indices = indices[1:]
        if len(indices) == 0:
            return [
                LpVariable(name % tuple(indexStart + [i]), lowBound, upBound, cat)
                for i in index
            ]
        else:
            return [
                LpVariable.matrix(
                    name, indices, lowBound, upBound, cat, indexStart + [i]
                )
                for i in index
            ]

    @classmethod
    def dicts(
        cls,
        name,
        indices=None,
        lowBound=None,
        upBound=None,
        cat=const.LpContinuous,
        indexStart=[],
    ):
        """
        This function creates a dictionary of :py:class:`LpVariable` with the specified associated parameters.

        :param name: The prefix to the name of each LP variable created
        :param indices: A list of strings of the keys to the dictionary of LP
            variables, and the main part of the variable name itself
        :param lowBound: The lower bound on these variables' range. Default is
            negative infinity
        :param upBound: The upper bound on these variables' range. Default is
            positive infinity
        :param cat: The category these variables are in, Integer or
            Continuous(default)

        :return: A dictionary of :py:class:`LpVariable`
        """

        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        index = indices[0]
        indices = indices[1:]
        d = {}
        if len(indices) == 0:
            for i in index:
                d[i] = LpVariable(
                    name % tuple(indexStart + [str(i)]), lowBound, upBound, cat
                )
        else:
            for i in index:
                d[i] = LpVariable.dicts(
                    name, indices, lowBound, upBound, cat, indexStart + [i]
                )
        return d

    @classmethod
    def dict(cls, name, indices, lowBound=None, upBound=None, cat=const.LpContinuous):
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        lists = indices

        if len(indices) > 1:
            # Cartesian product
            res = []
            while len(lists):
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
            index = indices[0]
        else:
            return {}

        d = {}
        for i in index:
            d[i] = cls(name % i, lowBound, upBound, cat)
        return d

    def getLb(self):
        return self.lowBound

    def getUb(self):
        return self.upBound

    def bounds(self, low, up):
        self.lowBound = low
        self.upBound = up
        self.modified = True

    def positive(self):
        self.bounds(0, None)

    def value(self):
        return self.varValue

    def round(self, epsInt=1e-5, eps=1e-7):
        if self.varValue is not None:
            if (
                self.upBound != None
                and self.varValue > self.upBound
                and self.varValue <= self.upBound + eps
            ):
                self.varValue = self.upBound
            elif (
                self.lowBound != None
                and self.varValue < self.lowBound
                and self.varValue >= self.lowBound - eps
            ):
                self.varValue = self.lowBound
            if (
                self.cat == const.LpInteger
                and abs(round(self.varValue) - self.varValue) <= epsInt
            ):
                self.varValue = round(self.varValue)

    def roundedValue(self, eps=1e-5):
        if (
            self.cat == const.LpInteger
            and self.varValue != None
            and abs(self.varValue - round(self.varValue)) <= eps
        ):
            return round(self.varValue)
        else:
            return self.varValue

    def valueOrDefault(self):
        if self.varValue != None:
            return self.varValue
        elif self.lowBound != None:
            if self.upBound != None:
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
        elif self.upBound != None:
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

    def infeasibilityGap(self, mip=1):
        if self.varValue == None:
            raise ValueError("variable value is None")
        if self.upBound != None and self.varValue > self.upBound:
            return self.varValue - self.upBound
        if self.lowBound != None and self.varValue < self.lowBound:
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
        if self.lowBound == None:
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

    def asCplexLpAffineExpression(self, name, constant=1):
        return LpAffineExpression(self).asCplexLpAffineExpression(name, constant)

    def __ne__(self, other):
        if isinstance(other, LpElement):
            return self.name is not other.name
        elif isinstance(other, LpAffineExpression):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return 1
        else:
            return 1

    def __bool__(self):
        return bool(self.roundedValue())

    def addVariableToConstraints(self, e):
        """adds a variable to the constraints indicated by
        the LpConstraintVars in e
        """
        for constraint, coeff in e.items():
            constraint.addVariable(self, coeff)

    def setInitialValue(self, val, check=True):
        """
        sets the initial value of the variable to `val`
        May be used for warmStart a solver, if supported by the solver

        :param float val: value to set to variable
        :param bool check: if True, we check if the value fits inside the variable bounds
        :return: True if the value was set
        :raises ValueError: if check=True and the value does not fit inside the bounds
        """
        lb = self.lowBound
        ub = self.upBound
        config = [
            ("smaller", "lowBound", lb, lambda: val < lb),
            ("greater", "upBound", ub, lambda: val > ub),
        ]

        for rel, bound_name, bound_value, condition in config:
            if bound_value is not None and condition():
                if not check:
                    return False
                raise ValueError(
                    "In variable {}, initial value {} is {} than {} {}".format(
                        self.name, val, rel, bound_name, bound_value
                    )
                )
        self.varValue = val
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


class LpAffineExpression(_DICT_TYPE):
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

    constant: float
    name: str
    # to remove illegal characters from the names
    trans = maketrans("-+[] ", "_____")

    def setName(self, name):
        if name:
            self.__name = str(name).translate(self.trans)
        else:
            self.__name = None

    def getName(self):
        return self.__name

    name = property(fget=getName, fset=setName)

    def __init__(self, e=None, constant=0, name=None):
        self.name = name
        # TODO remove isinstance usage
        if e is None:
            e = {}
        if isinstance(e, LpAffineExpression):
            # Will not copy the name
            self.constant = e.constant
            super().__init__(list(e.items()))
        elif isinstance(e, dict):
            self.constant = constant
            super().__init__(list(e.items()))
        elif isinstance(e, Iterable):
            self.constant = constant
            super().__init__(e)
        elif isinstance(e, LpElement):
            self.constant = 0
            super().__init__([(e, 1)])
        else:
            self.constant = e
            super().__init__()

    # Proxy functions for variables

    def isAtomic(self):
        return len(self) == 1 and self.constant == 0 and list(self.values())[0] == 1

    def isNumericalConstant(self):
        return len(self) == 0

    def atom(self):
        return list(self.keys())[0]

    # Functions on expressions

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def value(self):
        s = self.constant
        for v, x in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * x
        return s

    def valueOrDefault(self):
        s = self.constant
        for v, x in self.items():
            s += v.valueOrDefault() * x
        return s

    def addterm(self, key, value):
        y = self.get(key, 0)
        if y:
            y += value
            self[key] = y
        else:
            self[key] = value

    def emptyCopy(self):
        return LpAffineExpression()

    def copy(self):
        """Make a copy of self except the name which is reset"""
        # Will not copy the name
        return LpAffineExpression(self)

    def __str__(self, constant=1):
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
                s += str(val) + "*" + str(v)
        if constant:
            if s == "":
                s = str(self.constant)
            else:
                if self.constant < 0:
                    s += " - " + str(-self.constant)
                elif self.constant > 0:
                    s += " + " + str(self.constant)
        elif s == "":
            s = "0"
        return s

    def sorted_keys(self):
        """
        returns the list of keys sorted by name
        """
        result = [(v.name, v) for v in self.keys()]
        result.sort()
        result = [v for _, v in result]
        return result

    def __repr__(self):
        l = [str(self[v]) + "*" + str(v) for v in self.sorted_keys()]
        l.append(str(self.constant))
        s = " + ".join(l)
        return s

    @staticmethod
    def _count_characters(line):
        # counts the characters in a list of strings
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name):
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

    def asCplexLpAffineExpression(self, name, constant=1):
        """
        returns a string that represents the Affine Expression in lp format
        """
        # refactored to use a list for speed in iron python
        result, line = self.asCplexVariablesOnly(name)
        if not self:
            term = f" {self.constant}"
        else:
            term = ""
            if constant:
                if self.constant < 0:
                    term = " - %s" % (-self.constant)
                elif self.constant > 0:
                    term = f" + {self.constant}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def addInPlace(self, other, sign=1):
        """
        :param int sign: the sign of the operation to do other.
            if we add other => 1
            if we subtract other => -1
        """
        if isinstance(other, int) and (other == 0):
            return self
        if other is None:
            return self
        if isinstance(other, LpElement):
            # if a variable, we add it to the dictionary
            self.addterm(other, sign)
        elif isinstance(other, LpAffineExpression):
            # if an expression, we add each variable and the constant
            self.constant += other.constant * sign
            for v, x in other.items():
                self.addterm(v, x * sign)
        elif isinstance(other, dict):
            # if a dictionary, we add each value
            for e in other.values():
                self.addInPlace(e, sign=sign)
        elif isinstance(other, list) or isinstance(other, Iterable):
            # if a list, we add each element of the list
            for e in other:
                self.addInPlace(e, sign=sign)
        # if we're here, other must be a number
        # we check if it's an actual number:
        elif not math.isfinite(other):
            raise const.PulpError("Cannot add/subtract NaN/inf values")
        # if it's indeed a number, we add it to the constant
        else:
            self.constant += other * sign
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
        if isinstance(other, LpAffineExpression):
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

    def __div__(self, other):
        if isinstance(other, LpAffineExpression) or isinstance(other, LpVariable):
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

    def __truediv__(self, other):
        return self.__div__(other)

    def __rdiv__(self, other):
        e = self.emptyCopy()
        if len(self):
            raise TypeError(
                "Expressions cannot be divided by a non-constant expression"
            )
        c = self.constant
        if isinstance(other, LpAffineExpression):
            e.constant = other.constant / c
            for v, x in other.items():
                e[v] = x / c
        elif not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        else:
            e.constant = other / c
        return e

    def __le__(self, other):
        return LpConstraint(self - other, const.LpConstraintLE)

    def __ge__(self, other):
        return LpConstraint(self - other, const.LpConstraintGE)

    def __eq__(self, other):
        return LpConstraint(self - other, const.LpConstraintEQ)

    def toDict(self):
        """
        exports the :py:class:`LpAffineExpression` into a list of dictionaries with the coefficients
        it does not export the constant

        :return: list of dictionaries with the coefficients
        :rtype: list
        """
        return [dict(name=k.name, value=v) for k, v in self.items()]

    to_dict = toDict


class LpConstraint(LpAffineExpression):
    """An LP constraint"""

    def __init__(self, e=None, sense=const.LpConstraintEQ, name=None, rhs=None):
        """
        :param e: an instance of :class:`LpAffineExpression`
        :param sense: one of :data:`~pulp.const.LpConstraintEQ`, :data:`~pulp.const.LpConstraintGE`, :data:`~pulp.const.LpConstraintLE` (0, 1, -1 respectively)
        :param name: identifying string
        :param rhs: numerical value of constraint target
        """
        LpAffineExpression.__init__(self, e, name=name)
        if rhs is not None:
            self.constant -= rhs
        self.sense = sense
        self.pi = None
        self.slack = None
        self.modified = True

    def getLb(self):
        if (self.sense == const.LpConstraintGE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
            return None

    def getUb(self):
        if (self.sense == const.LpConstraintLE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
            return None

    def __str__(self):
        s = LpAffineExpression.__str__(self, 0)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " " + str(-self.constant)
        return s

    def asCplexLpConstraint(self, name):
        """
        Returns a constraint as a string
        """
        result, line = self.asCplexVariablesOnly(name)
        if not list(self.keys()):
            line += ["0"]
        c = -self.constant
        if c == 0:
            c = 0  # Supress sign
        term = f" {const.LpConstraintSenses[self.sense]} {c:.12g}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def changeRHS(self, RHS):
        """
        alters the RHS of a constraint so that it can be modified in a resolve
        """
        self.constant = -RHS
        self.modified = True

    def __repr__(self):
        s = LpAffineExpression.__repr__(self)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " 0"
        return s

    def copy(self):
        """Make a copy of self"""
        return LpConstraint(self, self.sense)

    def emptyCopy(self):
        return LpConstraint(sense=self.sense)

    def addInPlace(self, other, sign=1):
        """
        :param int sign: the sign of the operation to do other.
            if we add other => 1
            if we subtract other => -1
        """
        if isinstance(other, LpConstraint):
            if self.sense * other.sense >= 0:
                LpAffineExpression.addInPlace(self, other, 1)
                self.sense |= other.sense
            else:
                LpAffineExpression.addInPlace(self, other, -1)
                self.sense |= -other.sense
        elif isinstance(other, list):
            for e in other:
                self.addInPlace(e, sign)
        else:
            LpAffineExpression.addInPlace(self, other, sign)
            # raise TypeError, "Constraints and Expressions cannot be added"
        return self

    def subInPlace(self, other):
        return self.addInPlace(other, -1)

    def __neg__(self):
        c = LpAffineExpression.__neg__(self)
        c.sense = -c.sense
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
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__mul__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def __rmul__(self, other):
        return self * other

    def __div__(self, other):
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__div__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def __rdiv__(self, other):
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__rdiv__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def valid(self, eps=0):
        val = self.value()
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

    def toDict(self):
        """
        exports constraint information into a dictionary

        :return: dictionary with all the constraint information
        """
        return dict(
            sense=self.sense,
            pi=self.pi,
            constant=self.constant,
            name=self.name,
            coefficients=LpAffineExpression.toDict(self),
        )

    @classmethod
    def fromDict(cls, _dict):
        """
        Initializes a constraint object from a dictionary with necessary information

        :param dict _dict: dictionary with data
        :return: a new :py:class:`LpConstraint`
        """
        const = cls(
            e=_dict["coefficients"],
            rhs=-_dict["constant"],
            name=_dict["name"],
            sense=_dict["sense"],
        )
        const.pi = _dict["pi"]
        return const

    from_dict = fromDict


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

    def makeElasticSubProblem(self, *args, **kwargs):
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

    def addVariable(self, var, coeff):
        """
        Adds a variable to the constraint with the
        activity coeff
        """
        self.constraint.addterm(var, coeff)

    def value(self):
        return self.constraint.value()


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
        self.objective = None
        self.constraints = _DICT_TYPE()
        self.name = name
        self.sense = sense
        self.sos1 = {}
        self.sos2 = {}
        self.status = const.LpStatusNotSolved
        self.sol_status = const.LpSolutionNoSolutionFound
        self.noOverlap = 1
        self.solver = None
        self.modifiedVariables = []
        self.modifiedConstraints = []
        self.resolveOK = False
        self._variables = []
        self._variable_ids = {}  # old school using dict.keys() for a set
        self.dummyVar = None
        self.solutionTime = 0
        self.solutionCpuTime = 0

        # locals
        self.lastUnused = 0

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
        # Remove transient data prior to pickling.
        state = self.__dict__.copy()
        del state["_variable_ids"]
        return state

    def __setstate__(self, state):
        # Update transient data prior to unpickling.
        self.__dict__.update(state)
        self._variable_ids = {}
        for v in self._variables:
            self._variable_ids[v.hash] = v

    def copy(self):
        """Make a copy of self. Expressions are copied by reference"""
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        lpcopy.objective = self.objective
        lpcopy.constraints = self.constraints.copy()
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

    def toDict(self):
        """
        creates a dictionary from the model with as much data as possible.
        It replaces variables by variable names.
        So it requires to have unique names for variables.

        :return: dictionary with model data
        :rtype: dict
        """
        try:
            self.checkDuplicateVars()
        except const.PulpError:
            raise const.PulpError(
                "Duplicated names found in variables:\nto export the model, variable names need to be unique"
            )
        self.fixObjective()
        variables = self.variables()
        return dict(
            objective=dict(
                name=self.objective.name, coefficients=self.objective.toDict()
            ),
            constraints=[v.toDict() for v in self.constraints.values()],
            variables=[v.toDict() for v in variables],
            parameters=dict(
                name=self.name,
                sense=self.sense,
                status=self.status,
                sol_status=self.sol_status,
            ),
            sos1=list(self.sos1.values()),
            sos2=list(self.sos2.values()),
        )

    to_dict = toDict

    @classmethod
    def fromDict(cls, _dict):
        """
        Takes a dictionary with all necessary information to build a model.
        And returns a dictionary of variables and a problem object

        :param _dict: dictionary with the model stored
        :return: a tuple with a dictionary of variables and a :py:class:`LpProblem`
        """

        # we instantiate the problem
        params = _dict["parameters"]
        pb_params = {"name", "sense"}
        args = {k: params[k] for k in pb_params}
        pb = cls(**args)
        pb.status = params["status"]
        pb.sol_status = params["sol_status"]

        # recreate the variables.
        var = {v["name"]: LpVariable.fromDict(**v) for v in _dict["variables"]}

        # objective function.
        # we change the names for the objects:
        obj_e = {var[v["name"]]: v["value"] for v in _dict["objective"]["coefficients"]}
        pb += LpAffineExpression(e=obj_e, name=_dict["objective"]["name"])

        # constraints
        # we change the names for the objects:
        def edit_const(const):
            const = dict(const)
            const["coefficients"] = {
                var[v["name"]]: v["value"] for v in const["coefficients"]
            }
            return const

        constraints = [edit_const(v) for v in _dict["constraints"]]
        for c in constraints:
            pb += LpConstraint.fromDict(c)

        # last, parameters, other options
        list_to_dict = lambda v: {k: v for k, v in enumerate(v)}
        pb.sos1 = list_to_dict(_dict["sos1"])
        pb.sos2 = list_to_dict(_dict["sos2"])

        return var, pb

    from_dict = fromDict

    def toJson(self, filename, *args, **kwargs):
        """
        Creates a json file from the LpProblem information

        :param str filename: filename to write json
        :param args: additional arguments for json function
        :param kwargs: additional keyword arguments for json function
        :return: None
        """
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    to_json = toJson

    @classmethod
    def fromJson(cls, filename):
        """
        Creates a new Lp Problem from a json file with information

        :param str filename: json file name
        :return: a tuple with a dictionary of variables and an LpProblem
        :rtype: (dict, :py:class:`LpProblem`)
        """
        with open(filename) as f:
            data = json.load(f)
        return cls.fromDict(data)

    from_json = fromJson

    @classmethod
    def fromMPS(cls, filename, sense=const.LpMinimize, **kwargs):
        data = mpslp.readMPS(filename, sense=sense, **kwargs)
        return cls.fromDict(data)

    def normalisedNames(self):
        constraintsNames = {k: "C%07d" % i for i, k in enumerate(self.constraints)}
        _variables = self.variables()
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
        while 1:
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

    def addVariable(self, variable):
        """
        Adds a variable to the problem before a constraint is added

        :param variable: the variable to be added
        """
        if variable.hash not in self._variable_ids:
            self._variables.append(variable)
            self._variable_ids[variable.hash] = variable

    def addVariables(self, variables):
        """
        Adds variables to the problem before a constraint is added

        :param variables: the variables to be added
        """
        for v in variables:
            self.addVariable(v)

    def variables(self):
        """
        Returns the problem variables

        :return: A list containing the problem variables
        :rtype: (list, :py:class:`LpVariable`)
        """
        if self.objective:
            self.addVariables(list(self.objective.keys()))
        for c in self.constraints.values():
            self.addVariables(list(c.keys()))
        self._variables.sort(key=lambda v: v.name)
        return self._variables

    def variablesDict(self):
        variables = {}
        if self.objective:
            for v in self.objective:
                variables[v.name] = v
        for c in list(self.constraints.values()):
            for v in c:
                variables[v.name] = v
        return variables

    def add(self, constraint, name=None):
        self.addConstraint(constraint, name)

    def addConstraint(self, constraint, name=None):
        if not isinstance(constraint, LpConstraint):
            raise TypeError("Can only add LpConstraint objects")
        if name:
            constraint.name = name
        try:
            if constraint.name:
                name = constraint.name
            else:
                name = self.unusedConstraintName()
        except AttributeError:
            raise TypeError("Can only add LpConstraint objects")
            # removed as this test fails for empty constraints
        #        if len(constraint) == 0:
        #            if not constraint.valid():
        #                raise ValueError, "Cannot add false constraints"
        if name in self.constraints:
            if self.noOverlap:
                raise const.PulpError("overlapping constraint names: " + name)
            else:
                print("Warning: overlapping constraint names:", name)
        self.constraints[name] = constraint
        self.modifiedConstraints.append(constraint)
        self.addVariables(list(constraint.keys()))

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
        self.objective.name = name
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
            if name is not None:
                # we may keep the LpAffineExpression name
                self.objective.name = name
        elif isinstance(other, LpVariable) or isinstance(other, (int, float)):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression(other)
            self.objective.name = name
        else:
            raise TypeError(
                "Can only add LpConstraintVar, LpConstraint, LpAffineExpression or True objects"
            )
        return self

    def extend(self, other, use_objective=True):
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
            for name in other:
                self.constraints[name] = other[name]
        elif isinstance(other, LpProblem):
            for v in set(other.variables()).difference(self.variables()):
                v.name = other.name + v.name
            for name, c in other.constraints.items():
                c.name = other.name + name
                self.addConstraint(c)
            if use_objective:
                self.objective += other.objective
        else:
            for c in other:
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
        if translation == None:
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
            if name != "__dummy":
                variables[name].varValue = values[name]

    def assignVarsDj(self, values):
        variables = self.variablesDict()
        for name in values:
            if name != "__dummy":
                variables[name].dj = values[name]

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
            self.dummyVar = LpVariable("__dummy", 0, 0)
        return self.dummyVar

    def fixObjective(self):
        if self.objective is None:
            self.objective = 0
            wasNone = 1
        else:
            wasNone = 0
        if not isinstance(self.objective, LpAffineExpression):
            self.objective = LpAffineExpression(self.objective)
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
        return len(self._variable_ids)

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
        constraint,
        penalty=None,
        proportionFreeBound=None,
        proportionFreeBoundList=None,
    ):
        subProblemName = f"{constraint.name}_elastic_SubProblem"
        LpProblem.__init__(self, subProblemName, const.LpMinimize)
        self.objective = LpAffineExpression()
        self.constraint = constraint
        self.constant = constraint.constant
        self.RHS = -constraint.constant
        self.objective = LpAffineExpression()
        self += constraint, "_Constraint"
        # create and add these variables but disabled
        self.freeVar = LpVariable("_free_bound", upBound=0, lowBound=0)
        self.upVar = LpVariable("_pos_penalty_var", upBound=0, lowBound=0)
        self.lowVar = LpVariable("_neg_penalty_var", upBound=0, lowBound=0)
        constraint.addInPlace(self.freeVar + self.lowVar + self.upVar)
        if proportionFreeBound:
            proportionFreeBoundList = [proportionFreeBound, proportionFreeBound]
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

    def _findValue(self, attrib):
        """
        safe way to get the value of a variable that may not exist
        """
        var = getattr(self, attrib, 0)
        if var:
            if value(var) is not None:
                return value(var)
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

    def findDifferenceFromRHS(self):
        """
        The amount the actual value varies from the RHS (sense: LHS - RHS)
        """
        return self.findLHSValue() - self.RHS

    def findLHSValue(self):
        """
        for elastic constraints finds the LHS value of the constraint without
        the free variable and or penalty variable assumes the constant is on the
        rhs
        """
        upVar = self._findValue("upVar")
        lowVar = self._findValue("lowVar")
        freeVar = self._findValue("freeVar")
        return self.constraint.value() - self.constant - upVar - lowVar - freeVar

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

    def alterName(self, name):
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


def lpSum(vector):
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
