#!/usr/bin/env python
# @(#) $Jeannot: test4.py,v 1.5 2004/03/20 17:06:54 js Exp $

# A two stage stochastic planification problem

# Example taken from:
# "On Optimal Allocation of Indivisibles under Incertainty"
# Vladimir I. Norkin, Yuri M. Ermoliev, Andrzej Ruszczynski
# IIASA, WP-94-021, April 1994 (revised October 1995).

from pulp import *
from random import *

C = 50
B = 500 # Resources available for the two years
s = 20 # Number of scenarios
n = 10 # Number of projects

N = range(n)
S = range(s)

# First year costs
c = [randint(0,C) for i in N]
# First year resources
d = [randint(0,C) for i in N]
# a=debut, b=taille
interval = [[(randint(0,C), randint(0,C)) for i in N] for j in S]
# Final earnings
q = [[randint(ai, ai+bi) for ai,bi in ab] for ab in interval]
# Second year resources
delta = [[randint(ai, ai+bi) for ai,bi in ab] for ab in interval]

# Variables
# x : Whether or not to start a project
x = LpVariable.matrix("x", (N,), 0, 1, LpInteger)
# y : Whether or not to finish it, in each scenario
y = LpVariable.matrix("y", (S, N), 0, 1, LpInteger)

# Problem
lp = LpProblem("Planification", LpMinimize)

# Objective: expected earnings
lp += lpDot(x, c) - lpDot(q, y)/float(s)

# Resources constraints for each scenario
for j in S:
	lp += lpDot(d, x) + lpDot(delta[j], y[j]) <= B

# We can only finish a project that was started
for i in N:
	for j in S:
		lp += y[j][i] <= x[i]

# Resolution
lp.solve()

# Solution printing
for i in N:
	print x[i], "=", x[i].value()
