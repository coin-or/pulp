"""
The Full Sponge Roll Problem for the PuLP Modeller

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
    patterns = calculatePatterns(totalRollLength,lenOpts,[])
    
    # The list 'PatternNames' is created 
    PatternNames = []
    for i in range(len(patterns)):
        PatternNames += ["P"+str(i)]
    
    # The amount of trim (unused material) for each pattern is calculated and added to the dictionary
    # 'trim', with the reference key of the pattern name.
    trim = {}
    for name,pattern in zip(PatternNames,patterns):
        ssum = 0
        for rep,l in zip(pattern,lenOpts):
            ssum += rep*l
        trim[name] = totalRollLength - ssum
    # The different cutting lengths are printed, and the number of each roll of that length in each
    # pattern is printed below. This is so the user can see what each pattern contains.
    print "Lens: %s" %lenOpts 
    for name,pattern in zip(PatternNames,patterns):
        print name + "  = %s"%pattern  

    return (PatternNames,patterns,trim)


# Import PuLP modeler functions
from pulp import *

# The Total Roll Length is entered
totalRollLength = 20

# The cost of each 20cm long sponge roll used
cost = 1

# The sale value of each cm of trim
trimValue = 0.04

# A list of all the roll lengths is created
LenOpts = ["5","7","9"]

rollData = {#Length Demand SalePrice
              "5":   [150,   0.25],
              "7":   [200,   0.33],
              "9":   [300,   0.40]}

# The pattern names and the patterns are created as lists, and the associated trim with each pattern
# is created as a dictionary. The inputs are the total roll length and the list (as integers) of 
# cutting options.
(PatternNames,patterns,trim) = makePatterns(totalRollLength,[int(l) for l in LenOpts])

# The RollData is made into separate dictionaries
(rollDemand,surplusPrice) = splitDict(rollData)

# The pattern data  is made into a dictionary so it can be called by patterns["7"]["P3"] for example.
# This will return the number of rolls of length "7" in pattern "P3"
patterns = makeDict([PatternNames,LenOpts],patterns,0)

# The variable 'prob' is created
prob = LpProblem("Cutting Stock Problem",LpMinimize)

# The problem variables of the number of each pattern to make are created
pattVars = LpVariable.dicts("Patt",PatternNames,0,None,LpInteger)

# The problem variables of the number of surplus rolls for each length are created
surplusVars = LpVariable.dicts("Surp",LenOpts,0,None,LpInteger)

# The objective function is entered: (the total number of large rolls used * the cost of each) - (the value of the surplus stock) - (the value of the trim)
prob += lpSum([pattVars[i]*cost for i in PatternNames]) - lpSum([surplusVars[i]*surplusPrice[i] for i in LenOpts]) - lpSum([pattVars[i]*trim[i]*trimValue for i in PatternNames]),"Net Production Cost"

# The demand minimum constraint is entered
for j in LenOpts:
    prob += lpSum([pattVars[i]*patterns[i][j] for i in PatternNames]) - surplusVars[j]>=rollDemand[j],"Ensuring enough %s cm rolls"%j
    
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
