#!/usr/bin/env python
# @(#) $Jeannot: test5.py,v 1.2 2004/03/20 17:06:54 js Exp $

# Market splitting problems from:
# G. Cornuejols, M. Dawande, A class of hard small 0-1 programs, 1998.

# With m>=4, these problems are often *very* difficult.

# Import PuLP modeler functions
from pulp import *

# Import random number generation functions
from random import *

# A new LP problem
prob = LpProblem("test5", LpMinimize)

# Parameters
# Number of constraints
m = 3
# Size of the integers involved
D = 100

# Number of variables
n = 10*(m-1)

# A vector of n binary variables
x = LpVariable.matrix("x", range(n), 0, 1, LpInteger)

# Slacks
s = LpVariable.matrix("s", range(m), 0)
w = LpVariable.matrix("w", range(m), 0)

# Objective
prob += lpSum(s) + lpSum(w)

# Constraints
d = [[randint(0,D) for i in range(n)] for j in range(m)]
for j in range(m):
	prob += lpDot(d[j], x) + s[j] - w[j] == lpSum(d[j])/2

# Resolution
prob.solve()

# Print the status of the solved LP
print "Status:", LpStatus[prob.status]

# Print the value of the variables at the optimum
for v in prob.variables():
	print v.name, "=", v.varValue

# Print the value of the objective
print "objective=", value(prob.objective)
