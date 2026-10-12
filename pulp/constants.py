# PuLP : Python LP Modeler

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id:constants.py 1791 2008-04-23 22:54:34Z smit023 $

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
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

"""
This file contains the constant definitions for PuLP
Note that hopefully these will be changed into something more pythonic
"""

import enum

EPS = 1e-7

# variable categories
LpContinuous = "Continuous"
LpInteger = "Integer"
LpBinary = "Binary"
LpCategories = {LpContinuous: "Continuous", LpInteger: "Integer", LpBinary: "Binary"}

# objective sense
LpMinimize = 1
LpMaximize = -1
LpSenses = {LpMaximize: "Maximize", LpMinimize: "Minimize"}
LpSensesMPS = {LpMaximize: "MAX", LpMinimize: "MIN"}


class LpSolveStatus(enum.IntEnum):
    """Why the solver stopped.

    Whether a feasible solution came back is recorded separately, as
    :attr:`~pulp.LpSolveStats.has_solution`.
    """

    NotSolved = 0
    Optimal = 1
    Infeasible = -1
    Unbounded = -2
    #: the solver ran but its answer is inconclusive, e.g. infeasible or unbounded
    Undefined = -3
    #: time budget exhausted, including deterministic work limits
    TimeLimit = -4
    MemoryLimit = -5
    NodeLimit = -6
    #: gap tolerance met, or an objective cutoff, bound or target reached
    GapLimit = -7
    IterationLimit = -8
    SolutionLimit = -9
    #: stopped by the user or an abort
    Interrupted = -10
    #: stopped early for a reason the solver does not report
    Stopped = -11
    #: numerical trouble, or tolerances could not be met
    NumericalError = -12


# constraint sense
LpConstraintLE = -1
LpConstraintEQ = 0
LpConstraintGE = 1
LpConstraintTypeToMps = {LpConstraintLE: "L", LpConstraintEQ: "E", LpConstraintGE: "G"}
LpConstraintSenses = {LpConstraintEQ: "=", LpConstraintLE: "<=", LpConstraintGE: ">="}
# LP line size
LpCplexLPLineSize = 78


class PulpError(Exception):
    """
    Pulp Exception Class
    """

    pass
