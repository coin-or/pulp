"""
Tests for pulp
"""
from pulp import *

def pulpTestCheck(prob, solver, okstatus, sol = {},
                   reducedcosts = None,
                   duals = None,
                   slacks = None,
                   eps = 10**-3,
                   status = None):
    
    if status is None:
        status = prob.solve(solver)
    if status not in okstatus:
        prob.writeLP("debug.lp")
        prob.writeMPS("debug.mps")
        print "Failure: status ==", status, "not in", okstatus
        print "Failure: status ==", LpStatus[status], "not in", \
                                [LpStatus[s] for s in okstatus]
        raise PulpError, "Tests failed for solver %s"%solver
    if sol:
        for v,x in sol.iteritems():
            if abs(v.varValue - x) > eps:
                prob.writeLP("debug.lp")
                prob.writeMPS("debug.mps")
                print "Test failed: var", v, "==", v.varValue, "!=", x
                raise PulpError, "Tests failed for solver %s"%solver
    if reducedcosts:
        for v,dj in reducedcosts.iteritems():
            if abs(v.dj - dj) > eps:
                prob.writeLP("debug.lp")
                prob.writeMPS("debug.mps")
                print "Test failed: var.dj", v, "==", v.dj, "!=", dj
                raise PulpError, "Tests failed for solver %s"%solver
    if duals:
        for cname,p in duals.iteritems():
            c = prob.constraints[cname]
            if abs(c.pi - p) > eps:
                prob.writeLP("debug.lp")
                prob.writeMPS("debug.mps")
                print "Test failed: constraint.pi", cname , "==", c.pi, "!=", p
                raise PulpError, "Tests failed for solver %s"%solver
    if slacks:
        for cname,slack in slacks.iteritems():
            c = prob.constraints[cname]
            if abs(c.slack - slack) > eps:
                prob.writeLP("debug.lp")
                prob.writeMPS("debug.mps")
                print ("Test failed: constraint.slack", cname , "==",
                        c.slack, "!=", slack)
                raise PulpError, "Tests failed for solver %s"%solver
        
def pulpTest001(solver):
    """
    Test that a variable is deleted when it is suptracted to 0
    """
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    c1 = x+y <= 5
    c2 = c1 + z -z
    print "\t Testing zero subtraction"
    assert str(c2)  #will raise an exception

def pulpTest010(solver):
    # Continuous
    prob = LpProblem("test010", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w", 0)
    prob += x + 4*y + 9*z, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob += w >= 0, "c4"
    print "\t Testing continuous LP solution"
    pulpTestCheck(prob, solver, [LpStatusOptimal], {x:4, y:-1, z:6, w:0})

def pulpTest011(solver):
    # Continuous Maximisation
    prob = LpProblem("test011", LpMaximize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w", 0)
    prob += x + 4*y + 9*z, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob += w >= 0, "c4"
    print "\t Testing maximize continuous LP solution"
    pulpTestCheck(prob, solver, [LpStatusOptimal], {x:4, y:1, z:8, w:0})

def pulpTest012(solver):
    # Unbounded
    prob = LpProblem("test012", LpMaximize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w", 0)
    prob += x + 4*y + 9*z + w, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob += w >= 0, "c4"
    print "\t Testing unbounded continuous LP solution"
    if solver.__class__ in [GUROBI, CPLEX_CMD, YAPOSIB]:
        # These solvers report infeasible or unbounded
        pulpTestCheck(prob, solver, [LpStatusInfeasible])
    elif solver.__class__ in [COINMP_DLL,]:
        # COINMP_DLL is just plain wrong
        print '\t\t Error in CoinMP it reports Optimal'
        pulpTestCheck(prob, solver, [LpStatusOptimal])
    elif solver.__class__ is GLPK_CMD:
        # GLPK_CMD Does not report unbounded problems, correctly
         pulpTestCheck(prob, solver, [LpStatusUndefined])
    elif solver.__class__ in [CPLEX_DLL,]:
        # CPLEX_DLL Does not report unbounded problems, correctly
         pulpTestCheck(prob, solver, [LpStatusNotSolved])
    else:
        pulpTestCheck(prob, solver, [LpStatusUnbounded])

def pulpTest020(solver):
    # MIP
    prob = LpProblem("test020", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0, None, LpInteger)
    prob += x + 4*y + 9*z, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7.5, "c3"
    print "\t Testing MIP solution"
    pulpTestCheck(prob, solver, [LpStatusOptimal], {x:3, y:-0.5, z:7})

def pulpTest030(solver):
    # relaxed MIP
    prob = LpProblem("test030", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0, None, LpInteger)
    prob += x + 4*y + 9*z, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7.5, "c3"
    solver.mip = 0
    print "\t Testing MIP relaxation"
    pulpTestCheck(prob, solver, [LpStatusOptimal], {x:3.5, y:-1, z:6.5})


def pulpTest040(solver):
    # Feasibility only
    prob = LpProblem("test040", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0, None, LpInteger)
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7.5, "c3"
    print "\t Testing feasibility problem (no objective)"
    pulpTestCheck(prob, solver, [LpStatusOptimal])


def pulpTest050(solver):
    # Infeasible
    prob = LpProblem("test050", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0, 10)
    prob += x+y <= 5.2, "c1"
    prob += x+z >= 10.3, "c2"
    prob += -y+z == 17.5, "c3"
    print "\t Testing an infeasible problem"
    if solver.__class__ is GLPK_CMD:
        # GLPK_CMD return codes are not informative enough
        pulpTestCheck(prob, solver, [LpStatusUndefined])
    elif solver.__class__ is CPLEX_DLL:
        # CPLEX_DLL Does not solve the problem
        pulpTestCheck(prob, solver, [LpStatusNotSolved])
    else:
        pulpTestCheck(prob, solver, [LpStatusInfeasible])

def pulpTest060(solver):
    # Integer Infeasible
    prob = LpProblem("test060", LpMinimize)
    x = LpVariable("x", 0, 4, LpInteger)
    y = LpVariable("y", -1, 1, LpInteger)
    z = LpVariable("z", 0, 10, LpInteger)
    prob += x+y <= 5.2, "c1"
    prob += x+z >= 10.3, "c2"
    prob += -y+z == 7.4, "c3"
    print "\t Testing an integer infeasible problem"
    if solver.__class__ in [GLPK_CMD, COIN_CMD]:
        # GLPK_CMD returns InfeasibleOrUnbounded
        pulpTestCheck(prob, solver, [LpStatusInfeasible, LpStatusUndefined])
    elif solver.__class__ in [COINMP_DLL]:
        #Currently there is an error in COINMP for problems where
        #presolve eliminates too many variables
        print "\t\t Error in CoinMP to be fixed, reports Optimal"
        pulpTestCheck(prob, solver, [LpStatusOptimal])
    else:
        pulpTestCheck(prob, solver, [LpStatusInfeasible])

def pulpTest070(solver):
    #Column Based modelling of PulpTest1
    prob = LpProblem("test070", LpMinimize)
    obj = LpConstraintVar("obj")
    # constraints
    a = LpConstraintVar("C1", LpConstraintLE, 5)
    b = LpConstraintVar("C2", LpConstraintGE, 10)
    c = LpConstraintVar("C3", LpConstraintEQ, 7)

    prob.setObjective(obj)
    prob += a
    prob += b
    prob += c
    # Variables
    x = LpVariable("x", 0, 4, LpContinuous, obj + a + b)
    y = LpVariable("y", -1, 1, LpContinuous, 4*obj + a - c)
    z = LpVariable("z", 0, None, LpContinuous, 9*obj + b + c)
    print "\t Testing column based modelling"
    pulpTestCheck(prob, solver, [LpStatusOptimal], {x:4, y:-1, z:6})

def pulpTest075(solver):
    #Column Based modelling of PulpTest1 with empty constraints
    prob = LpProblem("test075", LpMinimize)
    obj = LpConstraintVar("obj")
    # constraints
    a = LpConstraintVar("C1", LpConstraintLE, 5)
    b = LpConstraintVar("C2", LpConstraintGE, 10)
    c = LpConstraintVar("C3", LpConstraintEQ, 7)

    prob.setObjective(obj)
    prob += a
    prob += b
    prob += c
    # Variables
    x = LpVariable("x", 0, 4, LpContinuous, obj + b)
    y = LpVariable("y", -1, 1, LpContinuous, 4*obj - c)
    z = LpVariable("z", 0, None, LpContinuous, 9*obj + b + c)
    if solver.__class__ in [CPLEX_DLL, CPLEX_CMD, COINMP_DLL]:
        print "\t Testing column based modelling with empty constraints"
        pulpTestCheck(prob, solver, [LpStatusOptimal], {x:4, y:-1, z:6})

def pulpTest080(solver):
    """
    Test the reporting of dual variables slacks and reduced costs
    """
    prob = LpProblem("test080", LpMinimize)
    x = LpVariable("x", 0, 5)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    c1 = x+y <= 5
    c2 = x+z >= 10
    c3 = -y+z == 7
    
    prob += x + 4*y + 9*z, "obj"
    prob += c1, "c1"
    prob += c2,"c2"
    prob += c3,"c3"
    
    if solver.__class__ in [CPLEX_DLL, CPLEX_CMD, COINMP_DLL]:
        print "\t Testing dual variables and slacks reporting"
        pulpTestCheck(prob, solver, [LpStatusOptimal],
                  sol = {x:4, y:-1, z:6}, 
                  reducedcosts = {x:0, y:12, z:0},
                  duals = {"c1":0, "c2":1, "c3":8}, 
                  slacks = {"c1":2, "c2":0, "c3":0})

def pulpTest090(solver):
    #Column Based modelling of PulpTest1 with a resolve
    prob = LpProblem("test090", LpMinimize)
    obj = LpConstraintVar("obj")
    # constraints
    a = LpConstraintVar("C1", LpConstraintLE, 5)
    b = LpConstraintVar("C2", LpConstraintGE, 10)
    c = LpConstraintVar("C3", LpConstraintEQ, 7)

    prob.setObjective(obj)
    prob += a
    prob += b
    prob += c
    
    prob.setSolver(solver)# Variables
    x = LpVariable("x", 0, 4, LpContinuous, obj + a + b)
    y = LpVariable("y", -1, 1, LpContinuous, 4*obj + a - c)
    prob.resolve()
    z = LpVariable("z", 0, None, LpContinuous, 9*obj + b + c)
    if solver.__class__ in [CPLEX_DLL, COINMP_DLL]:
        print "\t Testing resolve of problem"
        prob.resolve()
        #difficult to check this is doing what we want as the resolve is 
        #over ridden if it is not implemented
        #pulpTestCheck(prob, solver, [LpStatusOptimal], {x:4, y:-1, z:6})

def pulpTest100(solver):
    """
    Test the ability to sequentially solve a problem
    """
    # set up a cubic feasible region
    prob = LpProblem("test100", LpMinimize)
    x = LpVariable("x", 0, 1)
    y = LpVariable("y", 0, 1)
    z = LpVariable("z", 0, 1)
    
    obj1 = x+0*y+0*z
    obj2 = 0*x-1*y+0*z
    prob += x <= 1, "c1"
    
    if solver.__class__ in [CPLEX_DLL, COINMP_DLL, GUROBI]:
        print "\t Testing Sequential Solves"
        status = prob.sequentialSolve([obj1,obj2], solver = solver)
        pulpTestCheck(prob, solver, [[LpStatusOptimal,LpStatusOptimal]],
                  sol = {x:0, y:1}, 
                  status = status)

def pulpTest110(solver):
    """
    Test the ability to use fractional constraints
    """
    prob = LpProblem("test110", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w", 0)
    prob += x + 4*y + 9*z, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob += w >= 0, "c4"
    prob += LpFractionConstraint(x, z, LpConstraintEQ, 0.5, name = 'c5')
    print "\t Testing fractional constraints"
    pulpTestCheck(prob, solver, [LpStatusOptimal], 
                    {x:10/3.0, y:-1/3.0, z:20/3.0, w:0})

def pulpTest120(solver):
    """
    Test the ability to use Elastic constraints
    """
    prob = LpProblem("test120", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w")
    prob += x + 4*y + 9*z + w, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob.extend((w >= -1).makeElasticSubProblem())
    print "\t Testing elastic constraints (no change)"
    pulpTestCheck(prob, solver, [LpStatusOptimal], 
                    {x:4, y:-1, z:6, w:-1})

def pulpTest121(solver):
    """
    Test the ability to use Elastic constraints
    """
    prob = LpProblem("test121", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w")
    prob += x + 4*y + 9*z + w, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob.extend((w >= -1).makeElasticSubProblem(proportionFreeBound = 0.1))
    print "\t Testing elastic constraints (freebound)"
    pulpTestCheck(prob, solver, [LpStatusOptimal], 
                    {x:4, y:-1, z:6, w:-1.1})

def pulpTest122(solver):
    """
    Test the ability to use Elastic constraints (penalty unchanged)
    """
    prob = LpProblem("test122", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w")
    prob += x + 4*y + 9*z + w, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob.extend((w >= -1).makeElasticSubProblem(penalty = 1.1))
    print "\t Testing elastic constraints (penalty unchanged)"
    prob.writeLP('debug.lp')
    pulpTestCheck(prob, solver, [LpStatusOptimal], 
                    {x:4, y:-1, z:6, w:-1.0})

def pulpTest123(solver):
    """
    Test the ability to use Elastic constraints (penalty unbounded)
    """
    prob = LpProblem("test123", LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0)
    w = LpVariable("w")
    prob += x + 4*y + 9*z + w, "obj"
    prob += x+y <= 5, "c1"
    prob += x+z >= 10, "c2"
    prob += -y+z == 7, "c3"
    prob.extend((w >= -1).makeElasticSubProblem(penalty = 0.9))
    print "\t Testing elastic constraints (penalty unbounded)"
    prob.writeLP('debug.lp')
    if solver.__class__ in [COINMP_DLL, GUROBI, CPLEX_CMD, YAPOSIB]:
        # COINMP_DLL Does not report unbounded problems, correctly
         pulpTestCheck(prob, solver, [LpStatusInfeasible])
    elif solver.__class__ is GLPK_CMD:
        # GLPK_CMD Does not report unbounded problems, correctly
         pulpTestCheck(prob, solver, [LpStatusUndefined])
    elif solver.__class__ in [CPLEX_DLL]:
        # GLPK_CMD Does not report unbounded problems, correctly
         pulpTestCheck(prob, solver, [LpStatusNotSolved])
    else:
        pulpTestCheck(prob, solver, [LpStatusUnbounded])


def pulpTestSolver(solver, msg = 0):
    tests = [pulpTest001,
            pulpTest010, pulpTest011, pulpTest012, 
            pulpTest020, 
            pulpTest030, 
            pulpTest040,
            pulpTest050, 
            pulpTest060, 
            pulpTest070, pulpTest075,
            pulpTest080, 
            pulpTest090, 
            pulpTest100, 
            pulpTest110, 
            pulpTest120, pulpTest121, pulpTest122, pulpTest123
            ]
    for t in tests:
        t(solver(msg=msg))

