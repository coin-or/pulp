"""
Columnwise Column Generation Functions

Authors: Antony Phillips,  Dr Stuart Mitchell  2008
"""

# Import PuLP modeler functions
from pulp import *

class Pattern:
    """
    Information on a specific pattern in the SpongeRoll Problem
    """
    cost = 1
    trimValue = 0.04
    totalRollLength = 20
    lenOpts = ["5", "7", "9"]
    numPatterns = 0
    
    def __init__(self, name, lengths = None):
        self.name = name
        self.lengthsdict = dict(zip(self.lenOpts,lengths))
        Pattern.numPatterns += 1
        
    def __str__(self):
        return self.name
    
    def trim(self):
        return Pattern.totalRollLength - sum([int(i)*int(self.lengthsdict[i]) for i in self.lengthsdict])
    
def createMaster():
    
    rollData = {#Length Demand SalePrice
              "5":   [150,   0.25],
              "7":   [200,   0.33],
              "9":   [300,   0.40]}

    (rollDemand,surplusPrice) = splitDict(rollData)
    
    # The variable 'prob' is created
    prob = LpProblem("MasterSpongeRollProblem",LpMinimize)
    
    # The variable 'obj' is created and set as the LP's objective function
    obj = LpConstraintVar("Obj")
    prob.setObjective(obj)
    
    # The constraints are initialised and added to prob
    constraints = {}
    for l in Pattern.lenOpts:
        constraints[l]= LpConstraintVar("Min" + str(l), LpConstraintGE, rollDemand[l])
        prob += constraints[l]
    
    # The surplus variables are created
    surplusVars = []    
    for i in Pattern.lenOpts:
        surplusVars += [LpVariable("Surplus "+ i,0,None,LpContinuous, -surplusPrice[i] * obj - constraints[i])]
        
    return prob,obj,constraints

def addPatterns(obj,constraints,newPatterns):
    
    # A list called Patterns is created to contain all the Pattern class
    # objects created in this function call
    Patterns = []
    for i in newPatterns:
        
        # The new patterns are checked to see that their length does not exceed
        # the total roll length
        lsum = 0
        for j,k in zip(i,Pattern.lenOpts):
            lsum += j * int(k)
        if lsum > Pattern.totalRollLength:
            raise "Length Options too large for Roll"
        
        # The number of rolls of each length in each new pattern is printed          
        print "P"+str(Pattern.numPatterns),"=",i
        
        # The patterns are instantiated as Pattern objects
        Patterns += [Pattern("P" + str(Pattern.numPatterns),i)]
        
    # The pattern variables are created
    pattVars = []
    for i in Patterns:        
        pattVars += [LpVariable("Pattern "+i.name,0,None,LpContinuous, (i.cost - Pattern.trimValue*i.trim()) * obj\
         + lpSum([constraints[l]*i.lengthsdict[l] for l in Pattern.lenOpts]))]
        
def masterSolve(prob,relax = True):
    
    # Unrelaxes the Integer Constraint
    if not relax:
        for v in prob.variables():
            v.cat = LpInteger

    # The problem is solved and rounded
    prob.solve()
    prob.roundSolution()
    
    if relax:
        # A dictionary of dual variable values is returned
        duals = {}
        for i,name in zip(Pattern.lenOpts,["Min5","Min7","Min9"]):
            duals[i] = prob.constraints[name].pi        
        return duals
    else:
        # A dictionary of variable values and the objective value are returned
        varsdict = {}
        for v in prob.variables():
            varsdict[v.name] = v.varValue
            
        return value(prob.objective), varsdict
    
def subSolve(duals):
    
    # The variable 'prob' is created
    prob = LpProblem("SubProb",LpMinimize)
    
    # The problem variables are created
    vars = LpVariable.dicts("Roll Length", Pattern.lenOpts, 0, None, LpInteger)
    
    trim = LpVariable("Trim", 0 ,None,LpInteger)
    
    # The objective function is entered: the reduced cost of a new pattern
    prob += (Pattern.cost - Pattern.trimValue*trim) - lpSum([vars[i]*duals[i] for i in Pattern.lenOpts]), "Objective"
    
    # The conservation of length constraint is entered
    prob += lpSum([vars[i]*int(i) for i in Pattern.lenOpts]) + trim == Pattern.totalRollLength, "lengthEquate"
    
    # The problem is solved 
    prob.solve()

    # The variable values are rounded
    prob.roundSolution()
    
    newPatterns = []
    # Check if there are more patterns which would reduce the master LP objective function further
    if value(prob.objective) < -10**-5:
        varsdict = {}
        for v in prob.variables():
            varsdict[v.name] = v.varValue
        # Adds the new pattern to the newPatterns list
        newPatterns += [[int(varsdict["Roll_Length_5"]),int(varsdict["Roll_Length_7"]),int(varsdict["Roll_Length_9"])]]
                    
    return newPatterns
