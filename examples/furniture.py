"""
 The Furniture problem from EngSci391 for the PuLP Modeller
 Author: Dr Stuart Mitchell    2007
"""
from pulp import *
Chairs = ["A","B"]
costs = {"A":100,
         "B":150}
Resources = ["Lathe","Polisher"]
capacity = {"Lathe"    : 40,
              "Polisher" : 48}
activity = [  #Chairs
              #A  B
              [1, 2],  #Lathe
              [3, 1.5] #Polisher
              ]
activity = makeDict([Resources,Chairs],activity)
prob = LpProblem("Furniture Manufacturing Problem", LpMaximize)
vars = LpVariable.dicts("Number of Chairs",Chairs, lowBound = 0)
#objective
prob += lpSum([costs[c]*vars[c] for c in Chairs])
for r in Resources:
    prob += lpSum([activity[r][c]*vars[c] for c in Chairs]) <= capacity[r], \
     "capacity_of_%s"%r 
prob.writeLP("furniture.lp")
prob.solve()
# Each of the variables is printed with it's value
for v in prob.variables():
    print v.name, "=", v.varValue
# The optimised objective function value is printed to the screen    
print "Total Revenue from Production = ", value(prob.objective)