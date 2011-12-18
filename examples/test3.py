#!/usr/bin/env python
# @(#) $Jeannot: test3.py,v 1.3 2004/03/20 17:06:54 js Exp $

# Deterministic generation planning using mixed integer linear programming.

# The goal is to minimise the cost of generation while satisfaying demand
# using a few thermal units and an hydro unit.
# The thermal units have a proportional cost and a startup cost.
# The hydro unit has an initial storage.

from pulp import *
from math import *

prob = LpProblem("test3", LpMinimize)

# The number of time steps
tmax = 9
# The number of thermal units
units = 5
# The minimum demand
dmin = 10.0
# The maximum demand
dmax = 150.0
# The maximum thermal production
tpmax = 150.0
# The maximum hydro production
hpmax = 100.0
# Initial hydro storage
sini = 50.0

# Time range
time = range(tmax)
# Time range (and one more step for the last state of plants)
xtime = range(tmax+1)
# Units range
unit = range(units)
# The demand
demand = [dmin+(dmax-dmin)*0.5 + 0.5*(dmax-dmin)*sin(4*t*2*3.1415/tmax) for t in time]
# Maximum output for the thermal units
pmax = [tpmax / units for i in unit]
# Minimum output for the thermal units
pmin = [tpmax / (units*3.0) for i in unit]
# Proportional cost of the thermal units
costs = [i+1 for i in unit]
# Startup cost of the thermal units.
startupcosts = [100*(i+1) for i in unit]

# Production variables for each time step and each thermal unit.
p = LpVariable.matrix("p", (time, unit), 0)
for t in time:
	for i in unit:
		p[t][i].upBound = pmax[i]

# State (started/stopped) variables for each time step and each thermal unit
d = LpVariable.matrix("d", (xtime, unit), 0, 1, LpInteger)

# Production constraint relative to the unit state (started/stoped)
for t in time:
	for i in unit:
		# If the unit is not started (d==0) then p<=0 else p<=pmax
		prob += p[t][i] <= pmax[i]*d[t][i]
		# If the unit is not started then p>=0 else p>= pmin
		prob += p[t][i] >= pmin[i]*d[t][i]

# Startup variables: 1 if the unit will be started next time step
u = LpVariable.matrix("u", (time, unit), 0)

# Dynamic startup constraints
# Initialy, all groups are started
for t in time:
	for i in unit:
		# u>=1 if the unit is started next time step
		prob += u[t][i] >= d[t+1][i] - d[t][i]

# Storage for the hydro plant (must not go below 0)
s = LpVariable.matrix("s", xtime, 0)

# Initial storage
s[0] = sini

# Hydro production
ph = [s[t]-s[t+1] for t in time]
for t in time:
	# Must be positive (no pumping)
	prob += ph[t] >= 0
	# And lower than hpmax
	prob += ph[t] <= hpmax

# Total production must equal demand
for t in time:
	prob += demand[t] == lpSum(p[t]) + ph[t]

# Thermal production cost
ctp = lpSum([lpSum([p[t][i] for t in time])*costs[i] for i in unit])
# Startup costs
cts = lpSum([lpSum([u[t][i] for t in time])*startupcosts[i] for i in unit])
# The objective is the total cost
prob += ctp + cts

# Solve the problem
prob.solve()

print "Minimum total cost:", prob.objective.value()

# Print the results
print "   D    S     U ",
for i in unit: print "  T%d    " %i,
print

for t in time:
	# Demand, hydro storage, hydro production
	print "%5.1f" % demand[t], "%5.1f" % value(s[t]), "%5.1f" % value(ph[t]),
	for i in unit:
		# Thermal production
		print "%4.1f" % value(p[t][i]),
		# The state of the unit
		if value(d[t][i]): print "+",
		else: print "-",
		# Wether the unit will be started
		if value(u[t][i]): print "*",
		else: print " ",
	print
