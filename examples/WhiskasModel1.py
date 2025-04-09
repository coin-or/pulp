# BEGIN file_docstring
"""
The Simplified Whiskas Model Python Formulation for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell  2007
"""
# END file_docstring

# BEGIN import_pulp
# Import PuLP modeler functions
from pulp import *

# END import_pulp

# BEGIN define_prob
# Create the 'prob' variable to contain the problem data
prob = LpProblem("The Whiskas Problem", LpMinimize)
# END define_prob

# BEGIN chicken_beef_vars
# The 2 variables Beef and Chicken are created with a lower limit of zero
x1 = LpVariable("ChickenPercent", 0, None, LpInteger)
x2 = LpVariable("BeefPercent", 0)
# END chicken_beef_vars

# BEGIN obj_func
# The objective function is added to 'prob' first
prob += 0.013 * x1 + 0.008 * x2, "Total Cost of Ingredients per can"
# END obj_func

# BEGIN constraints
# The five constraints are entered
prob += x1 + x2 == 100, "PercentagesSum"
prob += 0.100 * x1 + 0.200 * x2 >= 8.0, "ProteinRequirement"
prob += 0.080 * x1 + 0.100 * x2 >= 6.0, "FatRequirement"
prob += 0.001 * x1 + 0.005 * x2 <= 2.0, "FibreRequirement"
prob += 0.002 * x1 + 0.005 * x2 <= 0.4, "SaltRequirement"
# END constraints

# BEGIN lp_file
# The problem data is written to an .lp file
prob.writeLP("WhiskasModel.lp")
# END lp_file

# BEGIN prob_solve
# The problem is solved using PuLP's choice of Solver
prob.solve()
# END prob_solve

# BEGIN print_status
# The status of the solution is printed to the screen
print("Status:", LpStatus[prob.status])
# END print_status

# BEGIN print_var_value
# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print(v.name, "=", v.varValue)
# END print_var_value

# BEGIN print_obj
# The optimised objective function value is printed to the screen
print("Total Cost of Ingredients per can = ", value(prob.objective))
# END print_obj
