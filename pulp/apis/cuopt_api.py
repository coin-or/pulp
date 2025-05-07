import ctypes
import os
import subprocess
import sys
import warnings
from uuid import uuid4
import numpy as np
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

def process_constraint(args):
    local_data = []
    local_vars = []
    local_sense = []
    local_rhs = []
    for constraints in args:
        name, constraint = constraints
        local_data.extend(list(constraint.values()))
        local_vars.extend(list(constraint.keys()))
        local_sense.append(sense_conv[constraint.sense])
        local_rhs.append(-constraint.constant)
    return local_data, local_vars, local_sense, local_rhs


def process_variables(var):
    #obj_coeff = lp.objective.get(var, 0.0))
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
    return lowBound, upBound, varType, var.name


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
            self.var_list = None
            self.solver_params = solverParams

            ## TODO: Disable logging if self.msg = False
            for key, value in solverParams.items():
                if key == "optimality_tolerance":
                    self.settings.set_optimality_tolerance(value)


        def findSolutionValues(self, lp):
            model = lp.solverModel
            solution = self.solution
            solutionStatus = solution.get_termination_reason()
            print("CUOPT status=", solutionStatus)

            CuoptLpStatus = {
                0: LpStatusNotSolved,
                1: LpStatusOptimal,
                2: LpStatusInfeasible,
                3: LpStatusUnbounded,
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

            if solution.get_problem_category() == 0:
                status = CuoptLpStatus.get(solutionStatus, LpStatusUndefined)
            else:
                status = CuoptMipStatus.get(solutionStatus, LpStatusUndefined)

            lp.assignStatus(status)

            values = solution.get_primal_solution()

            for var, value in zip(lp._variables, values):
                var.varValue = value

            if not solution.get_problem_category():
                # TODO: Compute Slack

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
            """Solves the problem with CUOPT"""
            self.solveTime = -clock()
            # TODO: Add callback
            log_file = self.optionsDict.get("logPath") or ""

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
            var_dict = {}

            for i, var in enumerate(lp.variables()):
                obj_coeff.append(lp.objective.get(var, 0.0))
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
                var_dict[var.name] = i
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

            #if var_warmstart:
            #    print("Setting variable warmstart: ", var_warmstart)
            #    lp.solverModel.set_initial_primal_solution(np.array(var_warmstart))

            rhs, sense  = [], []
            matrix_data, matrix_indices, matrix_indptr = [], [], [0]

            for name, constraint in lp.constraints.items():
                row_coeffs = []
                matrix_data.extend(list(constraint.values()))
                matrix_indices.extend([var_dict[v.name] for v in constraint.keys()])
                matrix_indptr.append(len(matrix_data))
                try:
                    c_sense = sense_conv[constraint.sense]
                except:
                    raise PulpSolverError("Detected an invalid constraint type")
                rhs.append(-constraint.constant)
                sense.append(c_sense)
                #constraint.solverConstraint = {name: {"bound": -constraint.constant, "sense": c_sense, "coefficients": row_coeffs}}

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
