#!/usr/bin/env python
# Test for output of dual variables

# Import PuLP modeler functions
from pulp import *

# A new LP problem
prob = LpProblem("test7", LpMinimize)

x = LpVariable("x", 0, 4)

y = LpVariable("y", -1, 1)

z = LpVariable("z", 0)

prob += x + 4*y + 9*z, "obj"

prob += x + y <= 5, "c1"
prob += x + z >= 10,"c2"
prob += -y+ z == 7,"c3"

prob.writeLP("test7.lp")

prob.solve()

print("Status:", LpStatus[prob.status])

for v in prob.variables():
	print(v.name, "=", v.varValue, "\tReduced Cost =", v.dj)

print("objective=", value(prob.objective))

print("\nSensitivity Analysis\nConstraint\t\tShadow Price\tSlack")
for name, c in list(prob.constraints.items()):
	print(name, ":", c, "\t", c.pi, "\t\t", c.slack)
