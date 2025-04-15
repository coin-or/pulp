import ctypes
import os
import subprocess
import sys
import warnings
from uuid import uuid4
import numpy as np
from cuopt.utilities import setup

from ..constants import (
    LpBinary,
    LpConstraintEQ,
    LpConstraintGE,
    LpConstraintLE,
    LpContinuous,
    LpInteger,
    LpMaximize,
    LpMinimize,
    LpStatusInfeasible,
    LpStatusNotSolved,
    LpStatusOptimal,
    LpStatusUnbounded,
    LpStatusUndefined,
)
from .core import (
    LpSolver,
    LpSolver_CMD,
    PulpSolverError,
    clock,
    ctypesArrayFill,
    sparse,
)

# COPT string convention
if sys.version_info >= (3, 0):
    coptstr = lambda x: bytes(x, "utf-8")
else:
    coptstr = lambda x: x

byref = ctypes.byref

# Constraint Sense Converter
sense_conv = {LpConstraintLE: "L",
              LpConstraintGE: "G",
              LpConstraintEQ: "E",
             }

class CUOPT_CMD(LpSolver_CMD):
    """
    The CUOPT command-line solver
    """

    name = "CUOPT_CMD"

    def __init__(
        self,
        path=None,
        keepFiles=0,
        mip=True,
        msg=True,
        mip_start=False,
        warmStart=False,
        logfile=None,
        **params,
    ):
        """
        Initialize command-line solver
        """
        LpSolver_CMD.__init__(self, path, keepFiles, mip, msg, [])

        self.mipstart = warmStart
        self.logfile = logfile
        self.solverparams = params

    def defaultPath(self):
        """
        The default path of 'copt_cmd'
        """
        pass
        #return self.executableExtension("copt_cmd")

    def available(self):
        """
        True if 'copt_cmd' is available
        """
        pass
        #return self.executable(self.path)

    def actualSolve(self, lp):
        """
        Solve a well formulated LP problem

        This function borrowed implementation of CPLEX_CMD.actualSolve and
        GUROBI_CMD.actualSolve, with some modifications.
        """
        pass
        """if not self.available():
            raise PulpSolverError("COPT_PULP: Failed to execute '{}'".format(self.path))

        if not self.keepFiles:
            uuid = uuid4().hex
            tmpLp = os.path.join(self.tmpDir, "{}-pulp.lp".format(uuid))
            tmpSol = os.path.join(self.tmpDir, "{}-pulp.sol".format(uuid))
            tmpMst = os.path.join(self.tmpDir, "{}-pulp.mst".format(uuid))
        else:
            # Replace space with underscore to make filepath better
            tmpName = lp.name
            tmpName = tmpName.replace(" ", "_")

            tmpLp = tmpName + "-pulp.lp"
            tmpSol = tmpName + "-pulp.sol"
            tmpMst = tmpName + "-pulp.mst"

        lpvars = lp.writeLP(tmpLp, writeSOS=1)

        # Generate solving commands
        solvecmds = self.path
        solvecmds += " -c "
        solvecmds += '"read ' + tmpLp + ";"

        if lp.isMIP() and self.mipstart:
            self.writemst(tmpMst, lpvars)
            solvecmds += "read " + tmpMst + ";"

        if self.logfile is not None:
            solvecmds += "set logfile {};".format(self.logfile)

        if self.solverparams is not None:
            for parname, parval in self.solverparams.items():
                solvecmds += "set {0} {1};".format(parname, parval)

        if lp.isMIP() and not self.mip:
            solvecmds += "optimizelp;"
        else:
            solvecmds += "optimize;"

        solvecmds += "write " + tmpSol + ";"
        solvecmds += 'exit"'

        try:
            os.remove(tmpSol)
        except:
            pass

        if self.msg:
            msgpipe = None
        else:
            msgpipe = open(os.devnull, "w")

        rc = subprocess.call(solvecmds, shell=True, stdout=msgpipe, stderr=msgpipe)

        if msgpipe is not None:
            msgpipe.close()

        # Get and analyze result
        if rc != 0:
            raise PulpSolverError("COPT_PULP: Failed to execute '{}'".format(self.path))

        if not os.path.exists(tmpSol):
            status = LpStatusNotSolved
        else:
            status, values = self.readsol(tmpSol)

        if not self.keepFiles:
            for oldfile in [tmpLp, tmpSol, tmpMst]:
                try:
                    os.remove(oldfile)
                except:
                    pass

        if status == LpStatusOptimal:
            lp.assignVarsVals(values)

        # lp.assignStatus(status)
        lp.status = status

        return status"""

    def readsol(self, filename):
        """
        Read COPT solution file
        """
        pass
        """with open(filename) as solfile:
            try:
                next(solfile)
            except StopIteration:
                warnings.warn("COPT_PULP: No solution was returned")
                return LpStatusNotSolved, {}

            # TODO: No information about status, assumed to be optimal
            status = LpStatusOptimal

            values = {}
            for line in solfile:
                if line[0] != "#":
                    varname, varval = line.split()
                    values[varname] = float(varval)
        return status, values"""

    def writemst(self, filename, lpvars):
        """
        Write COPT MIP start file
        """
        """mstvals = [(v.name, v.value()) for v in lpvars if v.value() is not None]
        mstline = []
        for varname, varval in mstvals:
            mstline.append("{0} {1}".format(varname, varval))

        with open(filename, "w") as mstfile:
            mstfile.write("\n".join(mstline))"""
        return True


class CUOPT(LpSolver):
    """
    The CUOPT Optimizer via its python interface
    """

    name = "CUOPT"

    try:
        global cuopt
        import cuopt  # type: ignore[import-not-found]
    except:

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp, callback=None):
            """Solve a well formulated lp problem"""
            raise PulpSolverError("CUOPT: Not available")

    else:

        def __init__(
            self,
            mip=True,
            msg=True,
            timeLimit=None,
            gapRel=None,
            warmStart=False,
            logPath=None,
            **solverParams,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param float timeLimit: maximum time for solver (in seconds)
            :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
            :param bool warmStart: if True, the solver will use the current value of variables as a start
            :param str logPath: path to the log file
            """

            LpSolver.__init__(
                self,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                gapRel=gapRel,
                logPath=logPath,
                warmStart=warmStart,
            )

            from cuopt.linear_programming import data_model, solver_settings, solver
            self.model = data_model.DataModel()
            self.settings = solver_settings.SolverSettings()
            self.solver = solver
            self.solution = None
            self.solver_params = solverParams

            ## TODO: Disable logging if self.msg = False
            for key, value in solverParams.items():
                if key == "optimality_tolerance":
                    self.settings.set_optimality_tolerance(value)

        def findSolutionValues(self, lp):
            model = lp.solverModel
            solution = self.solution
            print(solution)
            solutionStatus = solution.get_termination_reason()

            CuoptLpStatus = {
                0: LpStatusNotSolved,
                1: LpStatusOptimal,
                2: LpStatusInfeasible,
                3: LpStatusInfeasible,
                4: LpStatusNotSolved,
                5: LpStatusNotSolved,
                6: LpStatusNotSolved, # Primal Feasible?
            }

            CuoptMipStatus = {
                0: LpStatusNotSolved,
                1: LpStatusOptimal,
                2: LpStatusNotSolved, # Feasible Solution Found ??
                3: LpStatusInfeasible,
                4: LpStatusUnbounded,
            }

            if self.msg:
                print("CUOPT status=", solutionStatus)

            lp.resolveOK = True
            for var in lp._variables:
                var.isModified = False

            if solution.get_problem_category() is 0:
                status = CuoptLpStatus.get(solutionStatus, LpStatusUndefined)
            else:
                status = CuoptMipStatus.get(solutionStatus, LpStatusUndefined)

            lp.assignStatus(status)

            values = solution.get_primal_solution()

            for var, value in zip(lp._variables, values):
                var.varValue = value

            if not solution.get_problem_category():
                # TODO: Compute Slack
                """slacks = model.getInfo("Slack", model.getConstrs())
                for constr, value in zip(lp.constraints.values(), slacks):
                    constr.slack = value
                """

                redcosts = solution.get_lp_stats()["reduced_cost"]
                for var, value in zip(lp._variables, redcosts):
                    var.dj = value

                duals = solution.get_dual_solution()
                for constr, value in zip(lp.constraints.values(), duals):
                    constr.pi = value

            return status

        def available(self):
            """True if the solver is available"""
            return True

        def callSolver(self, lp, callback=None):
            """Solves the problem with COPT"""
            self.solveTime = -clock()
            ## Add callback
            """if callback is not None:
                lp.solverModel.setCallback(
                    callback,
                    coptpy.COPT.CBCONTEXT_MIPRELAX | coptpy.COPT.CBCONTEXT_MIPSOL,
                )"""
            log_file = self.optionsDict.get("logPath") or ""
            setup()

            self.settings.set_infeasibility_detection(True)
            self.solution = self.solver.Solve(lp.solverModel, self.settings, log_file)

            self.solveTime += clock()

        def buildSolverModel(self, lp):
            """
            Takes the pulp lp model and translates it into a COPT model
            """
            lp.solverModel = self.model

            if lp.sense == LpMaximize:
                lp.solverModel.set_maximize(True)
            if self.timeLimit:
                self.settings.set_time_limit(self.timeLimit)

            gapRel = self.optionsDict.get("gapRel")
            if gapRel:
                self.settings.set_relative_gap_tolerance(gapRel)

            var_lb, var_ub, var_type, var_name = [], [], [], []
            obj_coeff = []

            for var in lp.variables():
                obj_coeff.append(lp.objective.get(var) or 0)
                lowBound = var.lowBound
                if lowBound is None:
                    lowBound = -np.inf
                upBound = var.upBound
                if upBound is None:
                    upBound = np.inf
                varType = "C"
                if var.cat == LpInteger and self.mip:
                    varType = "I"
                if var.cat == LpBinary and self.mip:
                    varType = "I"
                    lowBound = 0
                    upBound  = 1
                var_lb.append(lowBound)
                var_ub.append(upBound)
                var_type.append(varType)
                var_name.append(var.name)
                var.solverVar = {var.name: {"lb": var_lb, "ub": var_ub, "type": var_type}}

            lp.solverModel.set_variable_lower_bounds(np.array(var_lb))
            lp.solverModel.set_variable_upper_bounds(np.array(var_ub))
            lp.solverModel.set_variable_types(np.array(var_type))
            lp.solverModel.set_variable_names(np.array(var_name))

            var_warmstart = []
            if self.optionsDict.get("warmStart", False):
                for var in lp._variables:
                    if var.varValue is not None:
                        var_warmstart.append(var.varValue)
                    else:
                        var_warmstart = None
                        break

            if var_warmstart:
                lp.solverModel.set_initial_primal_solution(np.array(var_warmstart))

            var_list = lp.variables()
            rhs, sense  = [], []
            matrix_data, matrix_indices, matrix_indptr = [], [], [0]

            for name, constraint in lp.constraints.items():
                row_coeffs = []
                for i, x in enumerate(var_list):
                    con_coeff = constraint.get(x, 0)
                    row_coeffs.append(con_coeff)
                    if con_coeff:
                        row_coeffs.append(con_coeff)
                        matrix_data.append(con_coeff)
                        matrix_indices.append(i)
                matrix_indptr.append(len(matrix_data))
                try:
                    c_sense = sense_conv[constraint.sense]
                except:
                    raise PulpSolverError("Detected an invalid constraint type")
                rhs.append(-constraint.constant)
                sense.append(c_sense)
                constraint.solverConstraint = {name: {"bound": -constraint.constant, "sense": c_sense, "coefficients": row_coeffs}}

            lp.solverModel.set_csr_constraint_matrix(np.array(matrix_data), np.array(matrix_indices), np.array(matrix_indptr))
            lp.solverModel.set_constraint_bounds(np.array(rhs))
            lp.solverModel.set_row_types(np.array(sense))

            lp.solverModel.set_objective_coefficients(np.array(obj_coeff))


        def actualSolve(self, lp, callback=None):
            """
            Solve a well formulated lp problem

            creates a COPT model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)
            self.callSolver(lp, callback=callback)

            solutionStatus = self.findSolutionValues(lp)
            for var in lp._variables:
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

        def actualResolve(self, lp, callback=None):
            """
            Solve a well formulated lp problem

            uses the old solver and modifies the rhs of the modified constraints
            """
            rhs = lp.solverModel.get_constraint_bounds()
            sense = lp.solverModel.get_row_types()

            for i, name, constraint in enumerate(lp.constraints.items()):
                if constraint.modified:
                    sense[i] = sense_conv[constraint.sense]
                    rhs[i] = -constraint.constant
                    constraint.solverConstraint[name]["bound"] = rhs[i]
                    constraint.solverConstraint[name]["sense"] = sense[i]
            lp.solverModel.set_constraint_bounds(rhs)
            lp.solverModel.set_row_types(sense)

            self.callSolver(lp, callback=callback)

            solutionStatus = self.findSolutionValues(lp)
            for var in lp._variables:
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus
