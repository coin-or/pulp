"""
The Full Sponge Roll Problem using Classes for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell    2007
"""

def calculatePatterns(totalRollLength,lenOpts,head):
    """
     Recursively calculates the list of options lists for a cutting stock problem. The input
     'tlist' is a pointer, and will be the output of the function call.

     The inputs are:
     totalRollLength - the length of the roll
     lenOpts - a list of the sizes of remaining cutting options
     head - the current list that has been passed down though the recusion

     Returns the list of patterns

     Authors: Bojan Blazevic, Dr Stuart Mitchell    2007
    """
    if lenOpts:
        patterns =[]
        #take the first option off lenOpts
        opt = lenOpts[0]
        for rep in range(int(totalRollLength/opt)+1):
            #reduce the length
            l = totalRollLength - rep*opt
            h = head[:]
            h.append(rep)

            patterns.extend(calculatePatterns(l, lenOpts[1:], h))
    else:
        #end of the recursion
        patterns = [head]
    return patterns

def makePatterns(totalRollLength,lenOpts):
    """
     Makes the different cutting patterns for a cutting stock problem.

     The inputs are:
     totalRollLength : the length of the roll
     lenOpts: a list of the sizes of cutting options as strings

     Authors: Antony Phillips, Dr Stuart Mitchell    2007
    """

    # calculatePatterns is called to create a list of the feasible cutting options in 'tlist'
    patternslist = calculatePatterns(totalRollLength,lenOpts,[])

    # The list 'PatternNames' is created
    PatternNames = []
    for i in range(len(patternslist)):
        PatternNames += ["P"+str(i)]

    #Patterns = [0 for i in range(len(PatternNames))]
    Patterns = []

    for i,j in enumerate(PatternNames):
        Patterns += [Pattern(j, patternslist[i])]

    # The different cutting lengths are printed, and the number of each roll of that length in each
    # pattern is printed below. This is so the user can see what each pattern contains.
    print("Lens: %s" %lenOpts)
    for i in Patterns:
        print(i, " = %s"%[i.lengthsdict[j] for j in lenOpts])

    return Patterns


class Pattern:
    """
    Information on a specific pattern in the SpongeRoll Problem
    """
    cost = 1
    trimValue = 0.04
    totalRollLength = 20
    lenOpts = [5, 7, 9]

    def __init__(self,name,lengths = None):
        self.name = name
        self.lengthsdict = dict(zip(self.lenOpts,lengths))

    def __str__(self):
        return self.name

    def trim(self):
        return Pattern.totalRollLength - sum([int(i)*self.lengthsdict[i] for i in self.lengthsdict])


# Import PuLP modeler functions
from pulp import *

rollData = {#Length Demand SalePrice
              5:   [150,   0.25],
              7:   [200,   0.33],
              9:   [300,   0.40]}

# The pattern names and the patterns are created as lists, and the associated trim with each pattern
# is created as a dictionary. The inputs are the total roll length and the list (as integers) of
# cutting options.
Patterns = makePatterns(Pattern.totalRollLength,Pattern.lenOpts)

# The rollData is made into separate dictionaries
(rollDemand,surplusPrice) = splitDict(rollData)

# The variable 'prob' is created
prob = LpProblem("Cutting Stock Problem",LpMinimize)

# The problem variables of the number of each pattern to make are created
pattVars = LpVariable.dicts("Patt",Patterns,0,None,LpInteger)

# The problem variables of the number of surplus rolls for each length are created
surplusVars = LpVariable.dicts("Surp",Pattern.lenOpts,0,None,LpInteger)

# The objective function is entered: (the total number of large rolls used * the cost of each) - (the value of the surplus stock) - (the value of the trim)
prob += lpSum([pattVars[i]*Pattern.cost for i in Patterns]) - lpSum([surplusVars[i]*surplusPrice[i] for i in Pattern.lenOpts]) - lpSum([pattVars[i]*i.trim()*Pattern.trimValue for i in Patterns]),"Net Production Cost"

# The demand minimum constraint is entered
for j in Pattern.lenOpts:
    prob += lpSum([pattVars[i]*i.lengthsdict[j] for i in Patterns]) - surplusVars[j] >= rollDemand[j],"Ensuring enough %s cm rolls"%j

# The problem data is written to an .lp file
prob.writeLP("SpongeRollProblem.lp")

# The problem is solved
prob.solve()

# The status of the solution is printed to the screen
print("Status:", LpStatus[prob.status])

# Each of the variables is printed with it's resolved optimum value
for v in prob.variables():
    print(v.name, "=", v.varValue)

# The optimised objective function value is printed to the screen
print("Production Costs = ", value(prob.objective))
