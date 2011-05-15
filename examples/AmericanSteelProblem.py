"""
The American Steel Problem for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell  2007
"""

# Import PuLP modeller functions
from pulp import *

# List of all the nodes
Nodes = ["Youngstown",
         "Pittsburgh",
         "Cincinatti",
         "Kansas City",
         "Chicago",
         "Albany",
         "Houston",
         "Tempe",
         "Gary"]

nodeData = {# NODE        Supply Demand
         "Youngstown":    [10000,0],
         "Pittsburgh":    [15000,0],
         "Cincinatti":    [0,0],
         "Kansas City":   [0,0],
         "Chicago":       [0,0],
         "Albany":        [0,3000],
         "Houston":       [0,7000],
         "Tempe":         [0,4000],
         "Gary":          [0,6000]}

# List of all the arcs
Arcs = [("Youngstown","Albany"),
        ("Youngstown","Cincinatti"),
        ("Youngstown","Kansas City"),
        ("Youngstown","Chicago"),
        ("Pittsburgh","Cincinatti"),
        ("Pittsburgh","Kansas City"),
        ("Pittsburgh","Chicago"),
        ("Pittsburgh","Gary"),
        ("Cincinatti","Albany"),
        ("Cincinatti","Houston"),
        ("Kansas City","Houston"),
        ("Kansas City","Tempe"),
        ("Chicago","Tempe"),
        ("Chicago","Gary")]

arcData = { #      ARC                Cost Min Max
        ("Youngstown","Albany"):      [0.5,0,1000],
        ("Youngstown","Cincinatti"):  [0.35,0,3000],
        ("Youngstown","Kansas City"): [0.45,1000,5000],
        ("Youngstown","Chicago"):     [0.375,0,5000],
        ("Pittsburgh","Cincinatti"):  [0.35,0,2000],
        ("Pittsburgh","Kansas City"): [0.45,2000,3000],
        ("Pittsburgh","Chicago"):     [0.4,0,4000],
        ("Pittsburgh","Gary"):        [0.45,0,2000],
        ("Cincinatti","Albany"):      [0.35,1000,5000],
        ("Cincinatti","Houston"):     [0.55,0,6000],
        ("Kansas City","Houston"):    [0.375,0,4000],
        ("Kansas City","Tempe"):      [0.65,0,4000],
        ("Chicago","Tempe"):          [0.6,0,2000],
        ("Chicago","Gary"):           [0.12,0,4000]}

# Splits the dictionaries to be more understandable
(supply, demand) = splitDict(nodeData)
(costs, mins, maxs) = splitDict(arcData)

# Creates the boundless Variables as Integers
vars = LpVariable.dicts("Route",Arcs,None,None,LpInteger)

# Creates the upper and lower bounds on the variables
for a in Arcs:
    vars[a].bounds(mins[a], maxs[a])

# Creates the 'prob' variable to contain the problem data    
prob = LpProblem("American Steel Problem",LpMinimize)

# Creates the objective function
prob += lpSum([vars[a]* costs[a] for a in Arcs]), "Total Cost of Transport"

# Creates all problem constraints - this ensures the amount going into each node is at least equal to the amount leaving
for n in Nodes:
    prob += (supply[n]+ lpSum([vars[(i,j)] for (i,j) in Arcs if j == n]) >=
             demand[n]+ lpSum([vars[(i,j)] for (i,j) in Arcs if i == n])), "Steel Flow Conservation in Node %s"%n

# The problem data is written to an .lp file
prob.writeLP("AmericanSteelProblem.lp")

# The problem is solved using PuLP's choice of Solver
prob.solve()

# The status of the solution is printed to the screen
print "Status:", LpStatus[prob.status]

# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print v.name, "=", v.varValue

# The optimised objective function value is printed to the screen    
print "Total Cost of Transportation = ", value(prob.objective)
