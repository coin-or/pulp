"""
The Computer Plant Problem for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell 2007
"""

# Import PuLP modeler functions
from pulp import *

# Creates a list of all the supply nodes
Plants = ["San Francisco",
          "Los Angeles",
          "Phoenix",
          "Denver"]

# Creates a dictionary of lists for the number of units of supply at
# each plant and the fixed cost of running each plant
supplyData = {#Plant     Supply  Fixed Cost
          "San Francisco":[1700, 70000],
          "Los Angeles"  :[2000, 70000],
          "Phoenix"      :[1700, 65000],
          "Denver"       :[2000, 70000]
          }

# Creates a list of all demand nodes
Stores = ["San Diego",
          "Barstow",
          "Tucson",
          "Dallas"]

# Creates a dictionary for the number of units of demand at each store
demand = { #Store    Demand
          "San Diego":1700,
          "Barstow"  :1000,
          "Tucson"   :1500,
          "Dallas"   :1200
          }

# Creates a list of costs for each transportation path
costs = [  #Stores
         #SD BA TU DA
         [5, 3, 2, 6], #SF
         [4, 7, 8, 10],#LA    Plants
         [6, 5, 3, 8], #PH
         [9, 8, 6, 5]  #DE         
         ]

# Creates a list of tuples containing all the possible routes for transport
Routes = [(p,s) for p in Plants for s in Stores]

# Splits the dictionaries to be more understandable
(supply,fixedCost) = splitDict(supplyData)

# The cost data is made into a dictionary
costs = makeDict([Plants,Stores],costs,0)

# Creates the problem variables of the Flow on the Arcs
flow = LpVariable.dicts("Route",(Plants,Stores),0,None,LpInteger)

# Creates the master problem variables of whether to build the Plants or not
build = LpVariable.dicts("BuildaPlant",Plants,0,1,LpInteger)

# Creates the 'prob' variable to contain the problem data
prob = LpProblem("Computer Plant Problem",LpMinimize)

# The objective function is added to prob - The sum of the transportation costs and the building fixed costs
prob += lpSum([flow[p][s]*costs[p][s] for (p,s) in Routes])+lpSum([fixedCost[p]*build[p] for p in Plants]),"Total Costs"

# The Supply maximum constraints are added for each supply node (plant)
for p in Plants:
    prob += lpSum([flow[p][s] for s in Stores])<=supply[p]*build[p], "Sum of Products out of Plant %s"%p

# The Demand minimum constraints are added for each demand node (store)
for s in Stores:
    prob += lpSum([flow[p][s] for p in Plants])>=demand[s], "Sum of Products into Stores %s"%s

# The problem data is written to an .lp file
prob.writeLP("ComputerPlantProblem.lp")

# The problem is solved using PuLP's choice of Solver
prob.solve()

# The status of the solution is printed to the screen
print "Status:", LpStatus[prob.status]

# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print v.name, "=", v.varValue

# The optimised objective function value is printed to the screen    
print "Total Costs = ", value(prob.objective)