"""
The Simplified Sponge Roll Problem with Surplus and Trim for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell   2007
"""

# Import PuLP modeler functions
from pulp import *

# A list of all the roll lengths is created
LenOpts = ["5","7","9"]

rollData = {#Length Demand SalePrice
              "5":   [150,   0.25],
              "7":   [200,   0.33],
              "9":   [300,   0.40]}

# A list of all the patterns is created
PatternNames = ["A","B","C"]

# Creates a list of the number of rolls in each pattern for each different roll length
patterns = [#A B C
            [0,2,2],# 5
            [1,1,0],# 7
            [1,0,1] # 9
            ]

# A dictionary of the number of cms of trim in each pattern is created
trim = {"A": 4,
        "B": 2,
        "C": 1}

# The cost of each 20cm long sponge roll used
cost = 1

# The sale value of each cm of trim
trimValue = 0.04

# The rollData is made into separate dictionaries
(rollDemand,surplusPrice) = splitDict(rollData)

# The pattern data is made into a dictionary
patterns = makeDict([LenOpts,PatternNames],patterns,0)

# The problem variables of the number of each pattern to make are created
pattVars = LpVariable.dicts("Patt",PatternNames,0,None,LpInteger)

# The problem variables of the number of surplus rolls for each length are created
surplusVars = LpVariable.dicts("Surp",LenOpts,0,None,LpInteger)

# The variable 'prob' is created
prob = LpProblem("Cutting Stock Problem",LpMinimize)

# The objective function is entered: the total number of large rolls used * the fixed cost of each minus the surplus
# sales and the trim sales
prob += lpSum([pattVars[i]*cost for i in PatternNames]) - lpSum([surplusVars[i]*surplusPrice[i] for i in LenOpts]) \
- lpSum([pattVars[i]*trim[i]*trimValue for i in PatternNames]),"Net Production Cost"

# The demand minimum constraint is entered
for i in LenOpts:
    prob += lpSum([pattVars[j]*patterns[i][j] for j in PatternNames]) - surplusVars[i]\
    >= rollDemand[i],"Ensuring enough %s cm rolls"%i
    
# The problem data is written to an .lp file
prob.writeLP("SpongeRollProblem.lp")

# The problem is solved using PuLP's choice of Solver
prob.solve()

# The status of the solution is printed to the screen
print "Status:", LpStatus[prob.status]

# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print v.name, "=", v.varValue

# The optimised objective function value is printed to the screen    
print "Production Costs = ", value(prob.objective)
