from __future__ import annotations

from .core import LpSolver_CMD, LpSolver, subprocess, PulpSolverError, log
from .. import constants
import os
import warnings
from time import monotonic as clock
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pulp.pulp import LpProblem, LpVariable
    from _typeshed import FileDescriptorOrPath, SupportsRead, SupportsWrite


class CPLEX_CMD(LpSolver_CMD):
    """The CPLEX LP solver"""

    name = "CPLEX_CMD"

    def __init__(
        self,
        mip: bool = True,
        msg: bool = True,
        timeLimit: float | None = None,
        gapRel: float | None = None,
        gapAbs: float | None = None,
        options: list[str] | None = None,
        warmStart: bool = False,
        keepFiles: bool = False,
        path: str | None = None,
        threads: int | None = None,
        logPath: str | None = None,
        maxMemory: float | None = None,
        maxNodes: int | None = None,
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
        """
        super().__init__(
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

    def available(self) -> bool:
        """True if the solver is available"""
        return self.executable(self.path) is not None

    def actualSolve(self, lp: LpProblem):
        """Solve a well formulated lp problem"""
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpMst = self.create_tmp_files(lp.name, "lp", "sol", "mst")
        vs = lp.writeLP(tmpLp, writeSOS=True)
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

    def readsol(
        self, filename: FileDescriptorOrPath | SupportsRead[bytes] | SupportsRead[str]
    ):
        """Read a CPLEX solution file"""
        # CPLEX solution codes: http://www-eio.upc.es/lceio/manuals/cplex-11/html/overviewcplex/statuscodes.html
        import xml.etree.ElementTree as et

        solutionXML = et.parse(filename).getroot()
        solutionheader = solutionXML.find("header")
        if solutionheader is None:
            raise constants.PulpError("Failed to find header")
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
        shadowPrices: dict[str, float | None] = {}
        slacks: dict[str, float] = {}
        constraints = solutionXML.find("linearConstraints")
        if constraints is None:
            raise constants.PulpError("Failed to find linearConstraints")
        for constraint in constraints:
            name = constraint.get("name")
            assert name is not None

            slack = constraint.get("slack")
            assert slack is not None
            slacks[name] = float(slack)

            shadowPrice = constraint.get("dual")
            try:
                # See issue #508
                shadowPrices[name] = float(shadowPrice)
            except TypeError:
                shadowPrices[name] = None

        values: dict[str, float] = {}
        reducedCosts: dict[str, float | None] = {}

        variables = solutionXML.find("variables")
        assert variables is not None
        for variable in variables:
            name = variable.get("name")
            assert name is not None

            value = variable.get("value")
            assert value is not None
            values[name] = float(value)

            reducedCost = variable.get("reducedCost")
            try:
                # See issue #508
                reducedCosts[name] = float(reducedCost)
            except TypeError:
                reducedCosts[name] = None

        return status, values, reducedCosts, shadowPrices, slacks, solStatus

    def writesol(self, filename: str, vs: list[LpVariable]):
        """Writes a CPLEX solution file"""
        import xml.etree.ElementTree as et

        root = et.Element("CPLEXSolution", version="1.2")
        attrib_head = {}
        attrib_quality = {}
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
    except Exception as e:
        err = e
        """The CPLEX LP/MIP solver from python. Something went wrong!!!!"""

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp: LpProblem):
            """Solve a well formulated lp problem"""
            raise PulpSolverError(f"CPLEX_PY: Not Available:\n{self.err}")

    else:

        def __init__(
            self,
            mip: bool = True,
            msg: bool = True,
            timeLimit: float | None = None,
            gapRel: float | None = None,
            warmStart: bool = False,
            logPath: str | None = None,
            threads: int | None = None,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param float timeLimit: maximum time for solver (in seconds)
            :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
            :param bool warmStart: if True, the solver will use the current value of variables as a start
            :param str logPath: path to the log file
            :param int threads: number of threads to be used by CPLEX to solve a problem (default None uses all available)
            """

            super().__init__(
                gapRel=gapRel,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                warmStart=warmStart,
                logPath=logPath,
                threads=threads,
            )
            self.solverModel: cplex.Cplex | None = None

        def available(self) -> bool:
            """True if the solver is available"""
            return True

        def actualSolve(self, lp: LpProblem, callback: None = None) -> int:
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

        def buildSolverModel(self, lp: LpProblem):
            """
            Takes the pulp lp model and translates it into a cplex model
            """
            model_variables = lp.variables()
            self.n2v = {var.name: var for var in model_variables}
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
                self.solverModel.objective.set_sense(
                    self.solverModel.objective.sense.maximize
                )
            if lp.objective is None:
                raise PulpSolverError("No objective set")
            obj = [float(lp.objective.get(var, 0.0)) for var in model_variables]

            def cplex_var_lb(var: LpVariable):
                if var.lowBound is not None:
                    return float(var.lowBound)
                else:
                    return -cplex.infinity

            lb = [cplex_var_lb(var) for var in model_variables]

            def cplex_var_ub(var: LpVariable):
                if var.upBound is not None:
                    return float(var.upBound)
                else:
                    return cplex.infinity

            ub = [cplex_var_ub(var) for var in model_variables]
            colnames = [var.name for var in model_variables]

            def cplex_var_types(var: LpVariable):
                if var.cat == constants.LpInteger:
                    return "I"
                else:
                    return "C"

            ctype = [cplex_var_types(var) for var in model_variables]
            ctype = "".join(ctype)
            self.solverModel.variables.add(
                obj=obj, lb=lb, ub=ub, types=ctype, names=colnames
            )
            rows: list[tuple[list[str | None], list[float]]] = []
            senses: list[str] = []
            rhs: list[float] = []
            rownames = list(lp.constraints.keys())
            for constraint in lp.constraints.values():
                # build the expression
                if len(constraint) == 0:
                    # if the constraint is empty
                    rows.append(([], []))
                else:
                    expr1 = [var.name for var in constraint.keys()]
                    expr2 = [float(coeff) for coeff in constraint.values()]
                    rows.append((expr1, expr2))
                if constraint.sense == constants.LpConstraintLE:
                    senses.append("L")
                elif constraint.sense == constants.LpConstraintGE:
                    senses.append("G")
                elif constraint.sense == constants.LpConstraintEQ:
                    senses.append("E")
                else:
                    raise PulpSolverError("Detected an invalid constraint type")
                rhs.append(float(-constraint.constant))
            self.solverModel.linear_constraints.add(
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
            self.setThreads(self.optionsDict.get("threads", None))
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

        def setlogfile(self, fileobj: SupportsWrite[str] | None):
            """
            sets the logfile for cplex output
            """
            assert self.solverModel is not None
            self.solverModel.set_error_stream(fileobj)
            self.solverModel.set_log_stream(fileobj)
            self.solverModel.set_warning_stream(fileobj)
            self.solverModel.set_results_stream(fileobj)

        def setThreads(self, threads: int | None = None):
            """
            Change cplex thread count used (None is default which uses all available resources)
            """
            assert self.solverModel is not None
            self.solverModel.parameters.threads.set(threads or 0)

        def changeEpgap(self, epgap: float = 10**-4):
            """
            Change cplex solver integer bound gap tolerence
            """
            assert self.solverModel is not None
            self.solverModel.parameters.mip.tolerances.mipgap.set(epgap)

        def setTimeLimit(self, timeLimit: float = 0.0):
            """
            Make cplex limit the time it takes --added CBM 8/28/09
            """
            assert self.solverModel is not None
            self.solverModel.parameters.timelimit.set(timeLimit)

        def callSolver(self, lp: LpProblem):
            """Solves the problem with cplex"""
            # solve the problem
            assert self.solverModel is not None
            self.solveTime = -clock()
            self.solverModel.solve()
            self.solveTime += clock()

        def findSolutionValues(self, lp: LpProblem) -> int:
            assert lp.solverModel is not None
            model = cast(cplex.Cplex, lp.solverModel)
            CplexLpStatus = {
                model.solution.status.MIP_optimal: constants.LpStatusOptimal,
                model.solution.status.optimal: constants.LpStatusOptimal,
                model.solution.status.optimal_tolerance: constants.LpStatusOptimal,
                model.solution.status.infeasible: constants.LpStatusInfeasible,
                model.solution.status.infeasible_or_unbounded: constants.LpStatusInfeasible,
                model.solution.status.MIP_infeasible: constants.LpStatusInfeasible,
                model.solution.status.MIP_infeasible_or_unbounded: constants.LpStatusInfeasible,
                model.solution.status.unbounded: constants.LpStatusUnbounded,
                model.solution.status.MIP_unbounded: constants.LpStatusUnbounded,
                model.solution.status.abort_dual_obj_limit: constants.LpStatusNotSolved,
                model.solution.status.abort_iteration_limit: constants.LpStatusNotSolved,
                model.solution.status.abort_obj_limit: constants.LpStatusNotSolved,
                model.solution.status.abort_relaxed: constants.LpStatusNotSolved,
                model.solution.status.abort_time_limit: constants.LpStatusNotSolved,
                model.solution.status.abort_user: constants.LpStatusNotSolved,
                model.solution.status.MIP_abort_feasible: constants.LpStatusOptimal,
                model.solution.status.MIP_time_limit_feasible: constants.LpStatusOptimal,
                model.solution.status.MIP_time_limit_infeasible: constants.LpStatusInfeasible,
            }
            lp.cplex_status = model.solution.get_status()
            status = CplexLpStatus.get(lp.cplex_status, constants.LpStatusUndefined)
            CplexSolStatus = {
                model.solution.status.MIP_time_limit_feasible: constants.LpSolutionIntegerFeasible,
                model.solution.status.MIP_abort_feasible: constants.LpSolutionIntegerFeasible,
                model.solution.status.MIP_feasible: constants.LpSolutionIntegerFeasible,
            }
            # TODO: I did not find the following status: CPXMIP_NODE_LIM_FEAS, CPXMIP_MEM_LIM_FEAS
            sol_status = CplexSolStatus.get(lp.cplex_status)
            lp.assignStatus(status, sol_status)
            var_names = [var.name for var in lp._variables]
            con_names = [con for con in lp.constraints]
            try:
                objectiveValue = model.solution.get_objective_value()
                variablevalues: dict[str, float] = dict(
                    zip(var_names, model.solution.get_values(var_names))
                )
                lp.assignVarsVals(variablevalues)
                constraintslackvalues: dict[str, float] = dict(
                    zip(con_names, model.solution.get_linear_slacks(con_names))
                )
                lp.assignConsSlack(constraintslackvalues)
                if model.get_problem_type() == cplex.Cplex.problem_type.LP:
                    variabledjvalues: dict[str, float] = dict(
                        zip(
                            var_names,
                            model.solution.get_reduced_costs(var_names),
                        )
                    )
                    lp.assignVarsDj(variabledjvalues)
                    constraintpivalues: dict[str, float] = dict(
                        zip(
                            con_names,
                            model.solution.get_dual_values(con_names),
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

        def actualResolve(self, lp: LpProblem, **kwargs: Any):
            """
            looks at which variables have been modified and changes them
            """
            raise NotImplementedError("Resolves in CPLEX_PY not yet implemented")


CPLEX = CPLEX_CMD
