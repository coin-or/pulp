"""
The Beer Distribution Problem for the PuLP Modeller
Illustrates changing a constraint and solving

Authors: Antony Phillips, Dr Stuart Mitchell  2007
"""

# Import PuLP modeler functions
from pulp import *

# Creates a list of all the supply nodes
Warehouses = ["A", "B"]

# Creates a dictionary for the number of units of supply for each supply node
supply = {"A": 1000, "B": 4000}

# Creates a list of all demand nodes
Bars = ["1", "2", "3", "4", "5"]

# Creates a dictionary for the number of units of demand for each demand node
demand = {
    "1": 500,
    "2": 900,
    "3": 1800,
    "4": 200,
    "5": 700,
}

# Creates a list of costs of each transportation path
costs = [  # Bars
    # 1 2 3 4 5
    [2, 4, 5, 2, 1],  # A   Warehouses
    [3, 1, 3, 2, 3],  # B
]

# The cost data is made into a dictionary
costs_dict = makeDict([Warehouses, Bars], costs, 0)

# Creates the 'prob' variable to contain the problem data
prob = LpProblem("Beer Distribution Problem", LpMinimize)

# Creates a list of tuples containing all the possible routes for transport
Routes = [(w, b) for w in Warehouses for b in Bars]

# A dictionary called 'Vars' is created to contain the referenced variables(the routes)
vars = LpVariable.dicts("Route", (Warehouses, Bars), 0, None, LpInteger)

# The objective function is added to 'prob' first
prob += (
    lpSum([vars[w][b] * costs_dict[w][b] for (w, b) in Routes]),
    "Sum_of_Transporting_Costs",
)

# The supply maximum constraints are added to prob for each supply node (warehouse)
for w in Warehouses:
    prob += (
        lpSum([vars[w][b] for b in Bars]) <= supply[w],
        f"Sum_of_Products_out_of_Warehouse_{w}",
    )

# The demand minimum constraints are added to prob for each demand node (bar)
# These constraints are stored for resolve later
bar_demand_constraint = {}
for b in Bars:
    constraint = lpSum([vars[w][b] for w in Warehouses]) >= demand[b]
    prob += constraint, f"Sum_of_Products_into_Bar_{b}"
    bar_demand_constraint[b] = constraint

# The problem data is written to an .lp file
prob.writeLP("BeerDistributionProblem.lp")
for demand_value in range(500, 601, 10):
    # reoptimise the problem by increasing demand at bar '1'
    # note the constant is stored as the LHS constant not the RHS of the constraint
    bar_demand_constraint["1"].constant = -demand_value
    # or alternatively,
    # prob.constraints["Sum_of_Products_into_Bar_1"].constant = - demand

    # The problem is solved using PuLP's choice of Solver
    prob.solve()

    # The status of the solution is printed to the screen
    print("Status:", LpStatus[prob.status])

    # Each of the variables is printed with it's resolved optimum value
    for v in prob.variables():
        print(v.name, "=", v.varValue)

    # The optimised objective function value is printed to the screen
    print("Total Cost of Transportation = ", value(prob.objective))
