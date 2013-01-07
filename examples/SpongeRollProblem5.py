"""
The Sponge Roll Problem with Column Generation for the PuLP Modeller

Authors: Antony Phillips,  Dr Stuart Mitchell  2008
"""

# Import Column Generation functions
from CG import *

# The roll data is created
rollData = {#Length Demand SalePrice
            "5":   [150,   0.25],
            "7":   [200,   0.33],
            "9":   [300,   0.40]}

# The boolean variable morePatterns is set to True to test for more patterns
morePatterns = True

# A list of starting patterns is created
patternslist = [[4,0,0],[0,2,0],[0,0,2]]

# The starting patterns are instantiated with the Pattern class
Patterns = []
for i in patternslist:
    Patterns += [Pattern("P" + str(len(Patterns)), i)]

# This loop will be repeated until morePatterns is set to False
while morePatterns == True:
    
    # Solve the problem as a Relaxed LP
    duals = masterSolve(Patterns, rollData)
    
    # Find another pattern
    Patterns, morePatterns = subSolve(Patterns, duals)
        
# Re-solve as an Integer Problem
solution, varsdict = masterSolve(Patterns, rollData, relax = False)

# Display Solution
for i,j in varsdict.items():
    print i, "=", j
    
print "objective = ", solution