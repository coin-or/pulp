# PuLP : Python LP Modeler
# Version 1.4.2

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id:solvers.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""


from .core import LpSolver_CMD, LpSolver, subprocess, PulpSolverError, clock, log
from .core import gurobi_path
import os
from uuid import uuid4
import sys
from .. import constants
import warnings

# to import the gurobipy name into the module scope
gurobipy = None
class GUROBI(LpSolver):
    """
    The Gurobi LP/MIP solver (via its python interface)

    The Gurobi variables are available (after a solve) in var.solverVar
    Constriaints in constraint.solverConstraint
    and the Model is in prob.solverModel
    """
    try:
        sys.path.append(gurobi_path)
        # to import the name into the module scope
        global gurobipy
        import gurobipy
    except: # FIXME: Bug because gurobi returns
            #a gurobi exception on failed imports
        def available(self):
            """True if the solver is available"""
            return False
        def actualSolve(self, lp, callback = None):
            """Solve a well formulated lp problem"""
            raise PulpSolverError("GUROBI: Not Available")
    else:
        def __init__(self,
                    mip = True,
                    msg = True,
                    timeLimit = None,
                    epgap = None,
                    **solverParams):
            """
            Initializes the Gurobi solver.

            @param mip: if False the solver will solve a MIP as an LP
            @param msg: displays information from the solver to stdout
            @param timeLimit: sets the maximum time for solution
            @param epgap: sets the integer bound gap
            """
            LpSolver.__init__(self, mip, msg)
            self.timeLimit = timeLimit
            self.epgap = epgap
            #set the output of gurobi
            if not self.msg:
                gurobipy.setParam("OutputFlag", 0)
            #set the gurobi parameter values
            for key,value in solverParams.items():
                gurobipy.setParam(key, value)

        def findSolutionValues(self, lp):
            model = lp.solverModel
            solutionStatus = model.Status
            GRB = gurobipy.GRB
            # TODO: check status for Integer Feasible
            gurobiLpStatus = {GRB.OPTIMAL: constants.LpStatusOptimal,
                                   GRB.INFEASIBLE: constants.LpStatusInfeasible,
                                   GRB.INF_OR_UNBD: constants.LpStatusInfeasible,
                                   GRB.UNBOUNDED: constants.LpStatusUnbounded,
                                   GRB.ITERATION_LIMIT: constants.LpStatusNotSolved,
                                   GRB.NODE_LIMIT: constants.LpStatusNotSolved,
                                   GRB.TIME_LIMIT: constants.LpStatusNotSolved,
                                   GRB.SOLUTION_LIMIT: constants.LpStatusNotSolved,
                                   GRB.INTERRUPTED: constants.LpStatusNotSolved,
                                   GRB.NUMERIC: constants.LpStatusNotSolved,
                                   }
            #populate pulp solution values
            try:
                for var, value in zip(lp.variables(), model.getAttr(GRB.Attr.X, model.getVars())):
                    var.varValue = value
            except (gurobipy.GurobiError, AttributeError):
                pass

            try:
                for var, value in zip(lp.variables(), model.getAttr(GRB.Attr.RC, model.getVars())):
                    var.dj = value
            except (gurobipy.GurobiError, AttributeError):
                pass

            #put pi and slack variables against the constraints
            try:
                for constr, value in zip(lp.constraints.values(), model.getAttr(GRB.Pi, model.getConstrs())):
                    constr.pi = value
            except (gurobipy.GurobiError, AttributeError):
                pass

            try:
                for constr, value in zip(lp.constraints.values(), model.getAttr(GRB.Slack, model.getConstrs())):
                    constr.slack = value
            except (gurobipy.GurobiError, AttributeError):
                pass

            if self.msg:
                print("Gurobi status=", solutionStatus)
            lp.resolveOK = True
            for var in lp.variables():
                var.isModified = False
            status = gurobiLpStatus.get(solutionStatus, constants.LpStatusUndefined)
            lp.assignStatus(status)
            return status

        def available(self):
            """True if the solver is available"""
            return True

        def callSolver(self, lp, callback = None):
            """Solves the problem with gurobi
            """
            #solve the problem
            self.solveTime = -clock()
            lp.solverModel.optimize(callback = callback)
            self.solveTime += clock()

        def buildSolverModel(self, lp):
            """
            Takes the pulp lp model and translates it into a gurobi model
            """
            log.debug("create the gurobi model")
            lp.solverModel = gurobipy.Model(lp.name)
            log.debug("set the sense of the problem")
            if lp.sense == constants.LpMaximize:
                lp.solverModel.setAttr("ModelSense", -1)
            if self.timeLimit:
                lp.solverModel.setParam("TimeLimit", self.timeLimit)
            if self.epgap:
                lp.solverModel.setParam("MIPGap", self.epgap)
            log.debug("add the variables to the problem")
            for var in lp.variables():
                lowBound = var.lowBound
                if lowBound is None:
                    lowBound = -gurobipy.GRB.INFINITY
                upBound = var.upBound
                if upBound is None:
                    upBound = gurobipy.GRB.INFINITY
                obj = lp.objective.get(var, 0.0)
                varType = gurobipy.GRB.CONTINUOUS
                if var.cat == constants.LpInteger and self.mip:
                    varType = gurobipy.GRB.INTEGER
                var.solverVar = lp.solverModel.addVar(lowBound, upBound,
                            vtype = varType,
                            obj = obj, name = var.name)
            lp.solverModel.update()
            log.debug("add the Constraints to the problem")
            for name,constraint in lp.constraints.items():
                #build the expression
                expr = gurobipy.LinExpr(list(constraint.values()),
                            [v.solverVar for v in constraint.keys()])
                if constraint.sense == constants.LpConstraintLE:
                    relation = gurobipy.GRB.LESS_EQUAL
                elif constraint.sense == constants.LpConstraintGE:
                    relation = gurobipy.GRB.GREATER_EQUAL
                elif constraint.sense == constants.LpConstraintEQ:
                    relation = gurobipy.GRB.EQUAL
                else:
                    raise PulpSolverError('Detected an invalid constraint type')
                constraint.solverConstraint = lp.solverModel.addConstr(expr,
                    relation, -constraint.constant, name)
            lp.solverModel.update()

        def actualSolve(self, lp, callback = None):
            """
            Solve a well formulated lp problem

            creates a gurobi model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)
            #set the initial solution
            log.debug("Solve the Model using gurobi")
            self.callSolver(lp, callback = callback)
            #get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp.variables():
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

        def actualResolve(self, lp, callback = None):
            """
            Solve a well formulated lp problem

            uses the old solver and modifies the rhs of the modified constraints
            """
            log.debug("Resolve the Model using gurobi")
            for constraint in lp.constraints.values():
                if constraint.modified:
                    constraint.solverConstraint.setAttr(gurobipy.GRB.Attr.RHS,
                                                        -constraint.constant)
            lp.solverModel.update()
            self.callSolver(lp, callback = callback)
            #get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp.variables():
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

class GUROBI_CMD(LpSolver_CMD):
    """The GUROBI_CMD solver"""
    def defaultPath(self):
        return self.executableExtension("gurobi_cl")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        # TODO: workaround for python not reading LD_LIBRARY_PATH
        # in my version of ubuntu
        if 'GUROBI_HOME' in os.environ:
            if 'LD_LIBRARY_PATH' not in os.environ:
                os.environ['LD_LIBRARY_PATH'] = ""
            os.environ['LD_LIBRARY_PATH'] += ':' + os.environ['GUROBI_HOME'] + "/lib"

        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute "+self.path)

        if not self.keepFiles:
            uuid = uuid4().hex
            tmpLp = os.path.join(self.tmpDir, "%s-pulp.lp" % uuid)
            tmpSol = os.path.join(self.tmpDir, "%s-pulp.sol" % uuid)
            tmpMst = os.path.join(self.tmpDir, "%s-pulp.mst" % uuid)
        else:
            tmpLp = lp.name+"-pulp.lp"
            tmpSol = lp.name+"-pulp.sol"
            tmpMst = lp.name + "-pulp.mst"

        vs = lp.writeLP(tmpLp, writeSOS = 1)
        try: os.remove(tmpSol)
        except: pass
        cmd = self.path
        cmd += ' ' + ' '.join(['%s=%s' % (key, value)
                    for key, value in self.options])
        cmd += ' ResultFile=%s' % tmpSol
        if self.mip_start:
            self.writesol(filename=tmpMst, vs=vs)
            cmd += ' InputFile=%s' % tmpMst

        if lp.isMIP():
            if not self.mip:
                warnings.warn('GUROBI_CMD does not allow a problem to be relaxed')
        cmd += ' %s' % tmpLp
        if self.msg:
            pipe = None
        else:
            pipe = open(os.devnull, 'w')

        return_code = subprocess.call(cmd.split(), stdout = pipe, stderr = pipe)

        # Close the pipe now if we used it.
        if pipe is not None:
            pipe.close()

        if return_code != 0:
            raise PulpSolverError("PuLP: Error while trying to execute "+self.path)
        if not os.path.exists(tmpSol):
            warnings.warn('GUROBI_CMD does provide good solution status of non optimal solutions')
            status = constants.LpStatusNotSolved
            values = reducedCosts = shadowPrices = slacks = None
        else:
            status, values, reducedCosts, shadowPrices, slacks = self.readsol(tmpSol)
        if not self.keepFiles:
            for f in [tmpSol, tmpMst, tmpLp, "gurobi.log"]:
                try: os.remove(f)
                except: pass
        if status != constants.LpStatusInfeasible:
            lp.assignVarsVals(values)
            lp.assignVarsDj(reducedCosts)
            lp.assignConsPi(shadowPrices)
            lp.assignConsSlack(slacks)
        lp.assignStatus(status)
        return status

    def readsol(self, filename):
        """Read a Gurobi solution file"""
        with open(filename) as my_file:
            try:
                next(my_file) # skip the objective value
            except StopIteration:
                # Empty file not solved
                warnings.warn('GUROBI_CMD does provide good solution status of non optimal solutions')
                status = constants.LpStatusNotSolved
                return status, {}, {}, {}, {}
            #We have no idea what the status is assume optimal
            # TODO: check status for Integer Feasible
            status = constants.LpStatusOptimal

            shadowPrices = {}
            slacks = {}
            shadowPrices = {}
            slacks = {}
            values = {}
            reducedCosts = {}
            for line in my_file:
                    if line[0] != '#': #skip comments
                        name, value  = line.split()
                        values[name] = float(value)
        return status, values, reducedCosts, shadowPrices, slacks

    def writesol(self, filename, vs):
        """Writes a GUROBI solution file"""

        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        rows = []
        for name, value in values:
            rows.append('{} {}'.format(name, value))
        with open(filename, 'w') as f:
            f.write('\n'.join(rows))
        return True

