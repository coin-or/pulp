"""
The Sponge Roll Problem with Columnwise Column Generation for the PuLP Modeller

Authors: Antony Phillips,  Dr Stuart Mitchell  2008
"""

# Import Column Generation functions
from .CGcolumnwise import *

# The Master Problem is created
prob, obj, constraints = createMaster()

# A list of starting patterns is created
newPatterns = [[1,0,0],[0,1,0],[0,0,1]]

# New patterns will be added until newPatterns is an empty list
while newPatterns:
    # The new patterns are added to the problem
    addPatterns(obj,constraints,newPatterns)
    # The master problem is solved, and the dual variables are returned 
    duals = masterSolve(prob)
    # The sub problem is solved and a new pattern will be returned if there is one
    # which can reduce the master objective function
    newPatterns = subSolve(duals)

# The master problem is solved with Integer Constraints not relaxed
solution, varsdict = masterSolve(prob,relax = False)
    
# Display Solution
for i,j in list(varsdict.items()):
    print(i, "=", j)
    
print("objective = ", solution)