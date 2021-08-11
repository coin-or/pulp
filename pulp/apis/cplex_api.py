from .core import LpSolver_CMD, LpSolver, subprocess, PulpSolverError, clock, log
from .core import (
    cplex_dll_path,
    ctypesArrayFill,
    ilm_cplex_license,
    ilm_cplex_license_signature,
    to_string,
)
from .. import constants, sparse
import os
import warnings
import re


class CPLEX_CMD(LpSolver_CMD):
    """The CPLEX LP solver"""

    name = "CPLEX_CMD"

    def __init__(
        self,
        timelimit=None,
        mip=True,
        msg=True,
        timeLimit=None,
        gapRel=None,
        gapAbs=None,
        options=None,
        warmStart=False,
        keepFiles=False,
        path=None,
        threads=None,
        logPath=None,
        maxMemory=None,
        maxNodes=None,
        mip_start=False,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param list options: list of additional options to pass to solver
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary
        :param str logPath: path to the log file
        :param float maxMemory: max memory to use during the solving. Stops the solving when reached.
        :param int maxNodes: max number of nodes during branching. Stops the solving when reached.
        :param bool mip_start: deprecated for warmStart
        :param float timelimit: deprecated for timeLimit
        """
        if timelimit is not None:
            warnings.warn("Parameter timelimit is being depreciated for timeLimit")
            if timeLimit is not None:
                warnings.warn(
                    "Parameter timeLimit and timelimit passed, using timeLimit "
                )
            else:
                timeLimit = timelimit
        if mip_start:
            warnings.warn("Parameter mip_start is being depreciated for warmStart")
            if warmStart:
                warnings.warn(
                    "Parameter mipStart and mip_start passed, using warmStart"
                )
            else:
                warmStart = mip_start
        LpSolver_CMD.__init__(
            self,
            gapRel=gapRel,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            maxMemory=maxMemory,
            maxNodes=maxNodes,
            warmStart=warmStart,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            gapAbs=gapAbs,
            logPath=logPath,
        )

    def defaultPath(self):
        return self.executableExtension("cplex")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpMst = self.create_tmp_files(lp.name, "lp", "sol", "mst")
        vs = lp.writeLP(tmpLp, writeSOS=1)
        try:
            os.remove(tmpSol)
        except:
            pass
        if not self.msg:
            cplex = subprocess.Popen(
                self.path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            cplex = subprocess.Popen(self.path, stdin=subprocess.PIPE)
        cplex_cmds = "read " + tmpLp + "\n"
        if self.optionsDict.get("warmStart", False):
            self.writesol(filename=tmpMst, vs=vs)
            cplex_cmds += "read " + tmpMst + "\n"
            cplex_cmds += "set advance 1\n"

        if self.timeLimit is not None:
            cplex_cmds += "set timelimit " + str(self.timeLimit) + "\n"
        options = self.options + self.getOptions()
        for option in options:
            cplex_cmds += option + "\n"
        if lp.isMIP():
            if self.mip:
                cplex_cmds += "mipopt\n"
                cplex_cmds += "change problem fixed\n"
            else:
                cplex_cmds += "change problem lp\n"
        cplex_cmds += "optimize\n"
        cplex_cmds += "write " + tmpSol + "\n"
        cplex_cmds += "quit\n"
        cplex_cmds = cplex_cmds.encode("UTF-8")
        cplex.communicate(cplex_cmds)
        if cplex.returncode != 0:
            raise PulpSolverError("PuLP: Error while trying to execute " + self.path)
        if not os.path.exists(tmpSol):
            status = constants.LpStatusInfeasible
            values = reducedCosts = shadowPrices = slacks = solStatus = None
        else:
            (
                status,
                values,
                reducedCosts,
                shadowPrices,
                slacks,
                solStatus,
            ) = self.readsol(tmpSol)
        self.delete_tmp_files(tmpLp, tmpMst, tmpSol)
        if self.optionsDict.get("logPath") != "cplex.log":
            self.delete_tmp_files("cplex.log")
        if status != constants.LpStatusInfeasible:
            lp.assignVarsVals(values)
            lp.assignVarsDj(reducedCosts)
            lp.assignConsPi(shadowPrices)
            lp.assignConsSlack(slacks)
        lp.assignStatus(status, solStatus)
        return status

    def getOptions(self):
        # CPLEX parameters: https://www.ibm.com/support/knowledgecenter/en/SSSA5P_12.6.0/ilog.odms.cplex.help/CPLEX/GettingStarted/topics/tutorials/InteractiveOptimizer/settingParams.html
        # CPLEX status: https://www.ibm.com/support/knowledgecenter/en/SSSA5P_12.10.0/ilog.odms.cplex.help/refcallablelibrary/macros/Solution_status_codes.html
        params_eq = dict(
            logPath="set logFile {}",
            gapRel="set mip tolerances mipgap {}",
            gapAbs="set mip tolerances absmipgap {}",
            maxMemory="set mip limits treememory {}",
            threads="set threads {}",
            maxNodes="set mip limits nodes {}",
        )
        return [
            v.format(self.optionsDict[k])
            for k, v in params_eq.items()
            if k in self.optionsDict and self.optionsDict[k] is not None
        ]

    def readsol(self, filename):
        """Read a CPLEX solution file"""
        # CPLEX solution codes: http://www-eio.upc.es/lceio/manuals/cplex-11/html/overviewcplex/statuscodes.html
        try:
            import xml.etree.ElementTree as et
        except ImportError:
            import elementtree.ElementTree as et
        solutionXML = et.parse(filename).getroot()
        solutionheader = solutionXML.find("header")
        statusString = solutionheader.get("solutionStatusString")
        statusValue = solutionheader.get("solutionStatusValue")
        cplexStatus = {
            "1": constants.LpStatusOptimal,  #  optimal
            "101": constants.LpStatusOptimal,  #  mip optimal
            "102": constants.LpStatusOptimal,  #  mip optimal tolerance
            "104": constants.LpStatusOptimal,  #  max solution limit
            "105": constants.LpStatusOptimal,  #  node limit feasible
            "107": constants.LpStatusOptimal,  # time lim feasible
            "109": constants.LpStatusOptimal,  #  fail but feasible
            "113": constants.LpStatusOptimal,  # abort feasible
        }
        if statusValue not in cplexStatus:
            raise PulpSolverError(
                "Unknown status returned by CPLEX: \ncode: '{}', string: '{}'".format(
                    statusValue, statusString
                )
            )
        status = cplexStatus[statusValue]
        # we check for integer feasible status to differentiate from optimal in solution status
        cplexSolStatus = {
            "104": constants.LpSolutionIntegerFeasible,  # max solution limit
            "105": constants.LpSolutionIntegerFeasible,  # node limit feasible
            "107": constants.LpSolutionIntegerFeasible,  # time lim feasible
            "109": constants.LpSolutionIntegerFeasible,  # fail but feasible
            "111": constants.LpSolutionIntegerFeasible,  # memory limit feasible
            "113": constants.LpSolutionIntegerFeasible,  # abort feasible
        }
        solStatus = cplexSolStatus.get(statusValue)
        shadowPrices = {}
        slacks = {}
        constraints = solutionXML.find("linearConstraints")
        for constraint in constraints:
            name = constraint.get("name")
            shadowPrice = constraint.get("dual")
            slack = constraint.get("slack")
            shadowPrices[name] = float(shadowPrice)
            slacks[name] = float(slack)

        values = {}
        reducedCosts = {}
        for variable in solutionXML.find("variables"):
            name = variable.get("name")
            value = variable.get("value")
            reducedCost = variable.get("reducedCost")
            values[name] = float(value)
            reducedCosts[name] = float(reducedCost)

        return status, values, reducedCosts, shadowPrices, slacks, solStatus

    def writesol(self, filename, vs):
        """Writes a CPLEX solution file"""
        try:
            import xml.etree.ElementTree as et
        except ImportError:
            import elementtree.ElementTree as et
        root = et.Element("CPLEXSolution", version="1.2")
        attrib_head = dict()
        attrib_quality = dict()
        et.SubElement(root, "header", attrib=attrib_head)
        et.SubElement(root, "header", attrib=attrib_quality)
        variables = et.SubElement(root, "variables")

        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        for index, (name, value) in enumerate(values):
            attrib_vars = dict(name=name, value=str(value), index=str(index))
            et.SubElement(variables, "variable", attrib=attrib_vars)
        mst = et.ElementTree(root)
        mst.write(filename, encoding="utf-8", xml_declaration=True)

        return True


class CPLEX_PY(LpSolver):
    """
    The CPLEX LP/MIP solver (via a Python Binding)

    This solver wraps the python api of cplex.
    It has been tested against cplex 12.3.
    For api functions that have not been wrapped in this solver please use
    the base cplex classes
    """

    name = "CPLEX_PY"
    try:
        global cplex
        import cplex
    except (Exception) as e:
        err = e
        """The CPLEX LP/MIP solver from python PHANTOM Something went wrong!!!!"""

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp):
            """Solve a well formulated lp problem"""
            raise PulpSolverError("CPLEX_PY: Not Available:\n{}".format(self.err))

    else:

        def __init__(
            self,
            mip=True,
            msg=True,
            timeLimit=None,
            gapRel=None,
            warmStart=False,
            logPath=None,
            epgap=None,
            logfilename=None,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param float timeLimit: maximum time for solver (in seconds)
            :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
            :param bool warmStart: if True, the solver will use the current value of variables as a start
            :param str logPath: path to the log file
            :param float epgap: deprecated for gapRel
            :param str logfilename: deprecated for logPath
            """
            if epgap is not None:
                warnings.warn("Parameter epgap is being depreciated for gapRel")
                if gapRel is not None:
                    warnings.warn("Parameter gapRel and epgap passed, using gapRel")
                else:
                    gapRel = epgap
            if logfilename is not None:
                warnings.warn("Parameter logfilename is being depreciated for logPath")
                if logPath is not None:
                    warnings.warn(
                        "Parameter logPath and logfilename passed, using logPath"
                    )
                else:
                    logPath = logfilename

            LpSolver.__init__(
                self,
                gapRel=gapRel,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                warmStart=warmStart,
                logPath=logPath,
            )

        def available(self):
            """True if the solver is available"""
            return True

        def actualSolve(self, lp, callback=None):
            """
            Solve a well formulated lp problem

            creates a cplex model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)
            # set the initial solution
            log.debug("Solve the Model using cplex")
            self.callSolver(lp)
            # get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp._variables:
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

        def buildSolverModel(self, lp):
            """
            Takes the pulp lp model and translates it into a cplex model
            """
            model_variables = lp.variables()
            self.n2v = dict((var.name, var) for var in model_variables)
            if len(self.n2v) != len(model_variables):
                raise PulpSolverError(
                    "Variables must have unique names for cplex solver"
                )
            log.debug("create the cplex model")
            self.solverModel = lp.solverModel = cplex.Cplex()
            log.debug("set the name of the problem")
            if not self.mip:
                self.solverModel.set_problem_name(lp.name)
            log.debug("set the sense of the problem")
            if lp.sense == constants.LpMaximize:
                lp.solverModel.objective.set_sense(
                    lp.solverModel.objective.sense.maximize
                )
            obj = [float(lp.objective.get(var, 0.0)) for var in model_variables]

            def cplex_var_lb(var):
                if var.lowBound is not None:
                    return float(var.lowBound)
                else:
                    return -cplex.infinity

            lb = [cplex_var_lb(var) for var in model_variables]

            def cplex_var_ub(var):
                if var.upBound is not None:
                    return float(var.upBound)
                else:
                    return cplex.infinity

            ub = [cplex_var_ub(var) for var in model_variables]
            colnames = [var.name for var in model_variables]

            def cplex_var_types(var):
                if var.cat == constants.LpInteger:
                    return "I"
                else:
                    return "C"

            ctype = [cplex_var_types(var) for var in model_variables]
            ctype = "".join(ctype)
            lp.solverModel.variables.add(
                obj=obj, lb=lb, ub=ub, types=ctype, names=colnames
            )
            rows = []
            senses = []
            rhs = []
            rownames = []
            for name, constraint in lp.constraints.items():
                # build the expression
                expr = [(var.name, float(coeff)) for var, coeff in constraint.items()]
                if not expr:
                    # if the constraint is empty
                    rows.append(([], []))
                else:
                    rows.append(list(zip(*expr)))
                if constraint.sense == constants.LpConstraintLE:
                    senses.append("L")
                elif constraint.sense == constants.LpConstraintGE:
                    senses.append("G")
                elif constraint.sense == constants.LpConstraintEQ:
                    senses.append("E")
                else:
                    raise PulpSolverError("Detected an invalid constraint type")
                rownames.append(name)
                rhs.append(float(-constraint.constant))
            lp.solverModel.linear_constraints.add(
                lin_expr=rows, senses=senses, rhs=rhs, names=rownames
            )
            log.debug("set the type of the problem")
            if not self.mip:
                self.solverModel.set_problem_type(cplex.Cplex.problem_type.LP)
            log.debug("set the logging")
            if not self.msg:
                self.setlogfile(None)
            logPath = self.optionsDict.get("logPath")
            if logPath is not None:
                if self.msg:
                    warnings.warn(
                        "`logPath` argument replaces `msg=1`. The output will be redirected to the log file."
                    )
                self.setlogfile(open(logPath, "w"))
            gapRel = self.optionsDict.get("gapRel")
            if gapRel is not None:
                self.changeEpgap(gapRel)
            if self.timeLimit is not None:
                self.setTimeLimit(self.timeLimit)
            if self.optionsDict.get("warmStart", False):
                # We assume "auto" for the effort_level
                effort = self.solverModel.MIP_starts.effort_level.auto
                start = [
                    (k, v.value()) for k, v in self.n2v.items() if v.value() is not None
                ]
                if not start:
                    warnings.warn("No variable with value found: mipStart aborted")
                    return
                ind, val = zip(*start)
                self.solverModel.MIP_starts.add(
                    cplex.SparsePair(ind=ind, val=val), effort, "1"
                )

        def setlogfile(self, fileobj):
            """
            sets the logfile for cplex output
            """
            self.solverModel.set_error_stream(fileobj)
            self.solverModel.set_log_stream(fileobj)
            self.solverModel.set_warning_stream(fileobj)
            self.solverModel.set_results_stream(fileobj)

        def changeEpgap(self, epgap=10 ** -4):
            """
            Change cplex solver integer bound gap tolerence
            """
            self.solverModel.parameters.mip.tolerances.mipgap.set(epgap)

        def setTimeLimit(self, timeLimit=0.0):
            """
            Make cplex limit the time it takes --added CBM 8/28/09
            """
            self.solverModel.parameters.timelimit.set(timeLimit)

        def callSolver(self, isMIP):
            """Solves the problem with cplex"""
            # solve the problem
            self.solveTime = -clock()
            self.solverModel.solve()
            self.solveTime += clock()

        def findSolutionValues(self, lp):
            CplexLpStatus = {
                lp.solverModel.solution.status.MIP_optimal: constants.LpStatusOptimal,
                lp.solverModel.solution.status.optimal: constants.LpStatusOptimal,
                lp.solverModel.solution.status.optimal_tolerance: constants.LpStatusOptimal,
                lp.solverModel.solution.status.infeasible: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.infeasible_or_unbounded: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.MIP_infeasible: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.MIP_infeasible_or_unbounded: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.unbounded: constants.LpStatusUnbounded,
                lp.solverModel.solution.status.MIP_unbounded: constants.LpStatusUnbounded,
                lp.solverModel.solution.status.abort_dual_obj_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_iteration_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_obj_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_relaxed: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_time_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_user: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.MIP_abort_feasible: constants.LpStatusOptimal,
                lp.solverModel.solution.status.MIP_time_limit_feasible: constants.LpStatusOptimal,
                lp.solverModel.solution.status.MIP_time_limit_infeasible: constants.LpStatusInfeasible,
            }
            lp.cplex_status = lp.solverModel.solution.get_status()
            status = CplexLpStatus.get(lp.cplex_status, constants.LpStatusUndefined)
            CplexSolStatus = {
                lp.solverModel.solution.status.MIP_time_limit_feasible: constants.LpSolutionIntegerFeasible,
                lp.solverModel.solution.status.MIP_abort_feasible: constants.LpSolutionIntegerFeasible,
                lp.solverModel.solution.status.MIP_feasible: constants.LpSolutionIntegerFeasible,
            }
            # TODO: I did not find the following status: CPXMIP_NODE_LIM_FEAS, CPXMIP_MEM_LIM_FEAS
            sol_status = CplexSolStatus.get(lp.cplex_status)
            lp.assignStatus(status, sol_status)
            var_names = [var.name for var in lp._variables]
            con_names = [con for con in lp.constraints]
            try:
                objectiveValue = lp.solverModel.solution.get_objective_value()
                variablevalues = dict(
                    zip(var_names, lp.solverModel.solution.get_values(var_names))
                )
                lp.assignVarsVals(variablevalues)
                constraintslackvalues = dict(
                    zip(con_names, lp.solverModel.solution.get_linear_slacks(con_names))
                )
                lp.assignConsSlack(constraintslackvalues)
                if lp.solverModel.get_problem_type() == cplex.Cplex.problem_type.LP:
                    variabledjvalues = dict(
                        zip(
                            var_names,
                            lp.solverModel.solution.get_reduced_costs(var_names),
                        )
                    )
                    lp.assignVarsDj(variabledjvalues)
                    constraintpivalues = dict(
                        zip(
                            con_names,
                            lp.solverModel.solution.get_dual_values(con_names),
                        )
                    )
                    lp.assignConsPi(constraintpivalues)
            except cplex.exceptions.CplexSolverError:
                # raises this error when there is no solution
                pass
            # put pi and slack variables against the constraints
            # TODO: clear up the name of self.n2c
            if self.msg:
                print("Cplex status=", lp.cplex_status)
            lp.resolveOK = True
            for var in lp._variables:
                var.isModified = False
            return status

        def actualResolve(self, lp, **kwargs):
            """
            looks at which variables have been modified and changes them
            """
            raise NotImplementedError("Resolves in CPLEX_PY not yet implemented")


CPLEX = CPLEX_CMD
