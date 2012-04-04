"""
The Beer Distribution Problem for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell  2007
"""

# Import PuLP modeler functions
import pulp

# Creates a list of all the supply nodes
warehouses = ["A", "B"]

# Creates a dictionary for the number of units of supply for each supply node
supply = {"A": 1000,
          "B": 4000}

# Creates a list of all demand nodes
bars = ["1", "2", "3", "4", "5"]

# Creates a dictionary for the number of units of demand for each demand node
demand = {"1":500,
          "2":900,
          "3":1800,
          "4":200,
          "5":700,}

# Creates a list of costs of each transportation path
costs = [   #Bars
         #1 2 3 4 5
         [2,4,5,2,1],#A   Warehouses
         [3,1,3,2,3] #B
         ]

# The cost data is made into a dictionary
costs = pulp.makeDict([warehouses, bars], costs,0)

# Creates the 'prob' variable to contain the problem data
prob = pulp.LpProblem("Beer Distribution Problem", pulp.LpMinimize)

# Creates a list of tuples containing all the possible routes for transport
routes = [(w,b) for w in warehouses for b in bars]

# A dictionary called x is created to contain quantity shipped on the routes
x = pulp.LpVariable.dicts("route", (warehouses, bars), 
                        lowBound = 0 
                        cat = pulp.LpInteger)

# The objective function is added to 'prob' first
prob += sum([x[w][b]*costs[w][b] for (w,b) in routes]), \
            "Sum_of_Transporting_Costs"

# Supply maximum constraints are added to prob for each supply node (warehouse)
for w in warehouses:
    prob += sum([x[w][b] for b in bars]) <= supply[w], \
            "Sum_of_Products_out_of_Warehouse_%s"%w

# Demand minimum constraints are added to prob for each demand node (bar)
for b in bars:
    prob += sum([x[w][b] for w in warehouses]) >= demand[b], \
    "Sum_of_Products_into_Bar%s"%b
                   
# The problem data is written to an .lp file
prob.writeLP("BeerDistributionProblem.lp")

# The problem is solved using PuLP's choice of Solver
prob.solve()

# The status of the solution is printed to the screen
print "Status:", pulp.LpStatus[prob.status]

# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print v.name, "=", v.varValue

# The optimised objective function value is printed to the screen    
print "Total Cost of Transportation = ", prob.objective.value()
