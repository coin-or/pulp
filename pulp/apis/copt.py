from __future__ import annotations

import ctypes
import math
import os
import subprocess
import sys
import warnings
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from ..core.lp_problem import LpProblem
    from ..core.lp_stats import LpSolveStats

from ..constants import (
    LpBinary,
    LpConstraintEQ,
    LpConstraintGE,
    LpConstraintLE,
    LpContinuous,
    LpInteger,
    LpMaximize,
    LpMinimize,
    LpSolveStatus,
)
from .core import (
    LpSolver,
    LpSolver_CMD,
    PulpSolverError,
    clock,
    clocks,
    ctypesArrayFill,
    import_optional,
    requires,
    sparse,
)

# COPT string convention
if sys.version_info >= (3, 0):

    def coptstr(x):
        return bytes(x, "utf-8")
else:

    def coptstr(x):
        return x


byref = ctypes.byref

coptpy_mod = import_optional("coptpy")


class COPT_CMD(LpSolver_CMD):
    """
    The COPT command-line solver
    """

    name = "COPT_CMD"

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
        LpSolver_CMD.__init__(self, path, bool(keepFiles), mip, msg, [])

        self.mipstart = warmStart
        self.logfile = logfile
        self.solverparams = params

    def defaultPath(self):
        """
        The default path of 'copt_cmd'
        """
        return self.executableExtension("copt_cmd")

    def available(self):
        """
        True if 'copt_cmd' is available
        """
        return self.executable(self.path)

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """
        Solve a well formulated LP problem

        This function borrowed implementation of CPLEX_CMD.actualSolve and
        GUROBI_CMD.actualSolve, with some modifications.
        """
        start = clocks()
        if not self.available():
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
        except Exception:
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
            status = LpSolveStatus.NotSolved
        else:
            status, values = self.readsol(tmpSol)

        if not self.keepFiles:
            for oldfile in [tmpLp, tmpSol, tmpMst]:
                try:
                    os.remove(oldfile)
                except Exception:
                    pass

        # the solution file carries no status: a solution counts as optimal
        has_solution = status == LpSolveStatus.Optimal
        if has_solution:
            lp.assignVarsVals(values)

        return self.buildStats(lp, status, has_solution, start=start)

    def readsol(self, filename):
        """
        Read COPT solution file
        """
        with open(filename) as solfile:
            try:
                next(solfile)
            except StopIteration:
                warnings.warn("COPT_PULP: No solution was returned")
                return LpSolveStatus.NotSolved, {}

            # TODO: No information about status, assumed to be optimal
            status = LpSolveStatus.Optimal

            values = {}
            for line in solfile:
                if line[0] != "#":
                    varname, varval = line.split()
                    values[varname] = float(varval)
        return status, values

    def writemst(self, filename, lpvars):
        """
        Write COPT MIP start file
        """
        mstvals = [(v.name, v.value()) for v in lpvars if v.value() is not None]
        mstline = []
        for varname, varval in mstvals:
            mstline.append("{0} {1}".format(varname, varval))

        with open(filename, "w") as mstfile:
            mstfile.write("\n".join(mstline))
        return True


def COPT_DLL_loadlib():
    """
    Load COPT shared library in all supported platforms
    """
    from glob import glob

    libfile = None
    libpath = None
    libhome = os.getenv("COPT_HOME")
    if libhome is None:
        libhome = ""

    if sys.platform == "win32":
        libfile = glob(os.path.join(libhome, "bin", "copt.dll"))
    elif sys.platform == "linux":
        libfile = glob(os.path.join(libhome, "lib", "libcopt.so"))
    elif sys.platform == "darwin":
        libfile = glob(os.path.join(libhome, "lib", "libcopt.dylib"))
    else:
        raise PulpSolverError("COPT_PULP: Unsupported operating system")

    # Find desired library in given search path
    if libfile:
        libpath = libfile[0]

    if libpath is None:
        raise PulpSolverError(
            "COPT_PULP: Failed to locate solver library, "
            "please refer to COPT manual for installation guide"
        )
    else:
        if sys.platform == "win32":
            coptlib = ctypes.windll.LoadLibrary(libpath)
        else:
            coptlib = ctypes.cdll.LoadLibrary(libpath)

    return coptlib


# COPT LP/MIP status map
coptlpstat = {
    0: LpSolveStatus.NotSolved,  # unstarted
    1: LpSolveStatus.Optimal,
    2: LpSolveStatus.Infeasible,
    3: LpSolveStatus.Unbounded,
    4: LpSolveStatus.Undefined,  # infeasible or unbounded
    5: LpSolveStatus.NumericalError,  # numerical
    6: LpSolveStatus.NodeLimit,
    7: LpSolveStatus.NumericalError,  # imprecise
    8: LpSolveStatus.TimeLimit,  # timeout
    9: LpSolveStatus.Stopped,  # unfinished
    10: LpSolveStatus.Interrupted,
}

# COPT variable types map
coptctype = {
    LpContinuous: coptstr("C"),
    LpBinary: coptstr("B"),
    LpInteger: coptstr("I"),
}

# COPT constraint types map
coptrsense = {
    LpConstraintEQ: coptstr("E"),
    LpConstraintLE: coptstr("L"),
    LpConstraintGE: coptstr("G"),
}

# COPT objective senses map
coptobjsen = {LpMinimize: 1, LpMaximize: -1}


class COPT_DLL(LpSolver):
    """
    The COPT dynamic library solver
    """

    name = "COPT_DLL"

    try:
        coptlib = COPT_DLL_loadlib()
    except Exception as e:
        err = e
        """The COPT dynamic library solver (DLL). Something went wrong!!!!"""

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
            """Solve a well formulated lp problem."""
            raise PulpSolverError(f"COPT_DLL: Not Available:\n{self.err}")

    else:
        # COPT API name map
        CreateEnv = coptlib.COPT_CreateEnv
        DeleteEnv = coptlib.COPT_DeleteEnv
        CreateProb = coptlib.COPT_CreateProb
        DeleteProb = coptlib.COPT_DeleteProb
        LoadProb = coptlib.COPT_LoadProb
        AddCols = coptlib.COPT_AddCols
        WriteMps = coptlib.COPT_WriteMps
        WriteLp = coptlib.COPT_WriteLp
        WriteBin = coptlib.COPT_WriteBin
        WriteSol = coptlib.COPT_WriteSol
        WriteBasis = coptlib.COPT_WriteBasis
        WriteMst = coptlib.COPT_WriteMst
        WriteParam = coptlib.COPT_WriteParam
        AddMipStart = coptlib.COPT_AddMipStart
        SolveLp = coptlib.COPT_SolveLp
        Solve = coptlib.COPT_Solve
        GetSolution = coptlib.COPT_GetSolution
        GetLpSolution = coptlib.COPT_GetLpSolution
        GetIntParam = coptlib.COPT_GetIntParam
        SetIntParam = coptlib.COPT_SetIntParam
        GetDblParam = coptlib.COPT_GetDblParam
        SetDblParam = coptlib.COPT_SetDblParam
        GetIntAttr = coptlib.COPT_GetIntAttr
        GetDblAttr = coptlib.COPT_GetDblAttr
        SearchParamAttr = coptlib.COPT_SearchParamAttr
        SetLogFile = coptlib.COPT_SetLogFile

        def __init__(
            self,
            mip=True,
            msg=True,
            mip_start=False,
            warmStart=False,
            logfile=None,
            **params,
        ):
            """
            Initialize COPT solver
            """

            LpSolver.__init__(self, mip, msg)

            # Initialize COPT environment and problem
            self.coptenv = None
            self.coptprob = None

            # Use MIP start information
            self.mipstart = warmStart

            # Create COPT environment and problem
            self.create()

            # Set log file
            if logfile is not None:
                rc = self.SetLogFile(self.coptprob, coptstr(logfile))
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to set log file")

            # Set parameters to problem
            if not self.msg:
                self.setParam("Logging", 0)

            for parname, parval in params.items():
                self.setParam(parname, parval)

        def available(self):
            """
            True if dynamic library is available
            """
            return True

        def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
            """
            Solve a well formulated LP/MIP problem

            This function borrowed implementation of CPLEX_DLL.actualSolve,
            with some modifications.
            """
            start = clocks()
            # Extract problem data and load it into COPT
            (
                ncol,
                nrow,
                nnonz,
                objsen,
                objconst,
                colcost,
                colbeg,
                colcnt,
                colind,
                colval,
                coltype,
                collb,
                colub,
                rowsense,
                rowrhs,
                colname,
                rowname,
            ) = self.extract(lp)

            rc = self.LoadProb(
                self.coptprob,
                ncol,
                nrow,
                objsen,
                objconst,
                colcost,
                colbeg,
                colcnt,
                colind,
                colval,
                coltype,
                collb,
                colub,
                rowsense,
                rowrhs,
                None,
                colname,
                rowname,
            )
            if rc != 0:
                raise PulpSolverError("COPT_PULP: Failed to load problem")

            if lp.isMIP() and self.mip:
                # Load MIP start information
                if self.mipstart:
                    mstdict = {
                        self.vname2n[v.name]: v.value()
                        for v in lp.exported_variables()
                        if v.value() is not None
                    }

                    if mstdict:
                        mstkeys = ctypesArrayFill(list(mstdict.keys()), ctypes.c_int)
                        mstvals = ctypesArrayFill(
                            list(mstdict.values()), ctypes.c_double
                        )

                        rc = self.AddMipStart(
                            self.coptprob, len(mstkeys), mstkeys, mstvals
                        )
                        if rc != 0:
                            raise PulpSolverError(
                                "COPT_PULP: Failed to add MIP start information"
                            )

                # Solve the problem
                rc = self.Solve(self.coptprob)
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to solve the MIP problem")
            elif lp.isMIP() and not self.mip:
                # Solve MIP as LP
                rc = self.SolveLp(self.coptprob)
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to solve MIP as LP")
            else:
                # Solve the LP problem
                rc = self.SolveLp(self.coptprob)
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to solve the LP problem")

            # Get problem status and solution
            status, has_solution = self.getsolution(lp, ncol, nrow)

            return self.buildStats(lp, status, has_solution, start=start)

        def extract(self, lp):
            """
            Extract data from PuLP lp structure

            This function borrowed implementation of LpSolver.getCplexStyleArrays,
            with some modifications.
            """
            cols = list(lp.exported_variables())
            ncol = len(cols)
            nrow = len(lp.constraints())

            collb = (ctypes.c_double * ncol)()
            colub = (ctypes.c_double * ncol)()
            colcost = (ctypes.c_double * ncol)()
            coltype = (ctypes.c_char * ncol)()
            colname = (ctypes.c_char_p * ncol)()

            rowrhs = (ctypes.c_double * nrow)()
            rowsense = (ctypes.c_char * nrow)()
            rowname = (ctypes.c_char_p * nrow)()

            spmat = sparse.Matrix(list(range(nrow)), list(range(ncol)))

            # Objective sense and constant offset
            objsen = coptobjsen[lp.sense]
            objconst = ctypes.c_double(0.0)

            # Associate each variable with a ordinal
            self.v2n = dict(((cols[i], i) for i in range(ncol)))
            self.vname2n = dict(((cols[i].name, i) for i in range(ncol)))
            self.n2v = dict((i, cols[i]) for i in range(ncol))
            self.c2n = {}
            self.n2c = {}
            self.addedVars = ncol
            self.addedRows = nrow

            # Extract objective cost
            for col, val in lp.objective.items():
                colcost[self.v2n[col]] = val

            # Extract variable types, names and lower/upper bounds
            for col in cols:
                colname[self.v2n[col]] = coptstr(col.name)

                if math.isfinite(col.lowBound):
                    collb[self.v2n[col]] = col.lowBound
                else:
                    collb[self.v2n[col]] = -1e30

                if math.isfinite(col.upBound):
                    colub[self.v2n[col]] = col.upBound
                else:
                    colub[self.v2n[col]] = 1e30

            # Extract column types
            if lp.isMIP():
                for var in cols:
                    coltype[self.v2n[var]] = coptctype[var.cat]
            else:
                coltype = None

            # Extract constraint rhs, senses and names
            idx = 0
            for constr in lp.constraints():
                row_key = constr.name
                rowrhs[idx] = -constr.constant
                rowsense[idx] = coptrsense[constr.sense]
                rowname[idx] = coptstr(row_key)

                self.c2n[row_key] = idx
                self.n2c[idx] = row_key
                idx += 1

            # Extract coefficient matrix and generate CSC-format matrix
            for col, row, coeff in lp.coefficients():
                spmat.add(self.c2n[row], self.vname2n[col], coeff)

            nnonz, _colbeg, _colcnt, _colind, _colval = spmat.col_based_arrays()

            colbeg = ctypesArrayFill(_colbeg, ctypes.c_int)
            colcnt = ctypesArrayFill(_colcnt, ctypes.c_int)
            colind = ctypesArrayFill(_colind, ctypes.c_int)
            colval = ctypesArrayFill(_colval, ctypes.c_double)

            return (
                ncol,
                nrow,
                nnonz,
                objsen,
                objconst,
                colcost,
                colbeg,
                colcnt,
                colind,
                colval,
                coltype,
                collb,
                colub,
                rowsense,
                rowrhs,
                colname,
                rowname,
            )

        def create(self):
            """
            Create COPT environment and problem

            This function borrowed implementation of CPLEX_DLL.grabLicense,
            with some modifications.
            """
            # In case recreate COPT environment and problem
            self.delete()

            self.coptenv = ctypes.c_void_p()
            self.coptprob = ctypes.c_void_p()

            # Create COPT environment
            rc = self.CreateEnv(byref(self.coptenv))
            if rc != 0:
                raise PulpSolverError("COPT_PULP: Failed to create environment")

            # Create COPT problem
            rc = self.CreateProb(self.coptenv, byref(self.coptprob))
            if rc != 0:
                raise PulpSolverError("COPT_PULP: Failed to create problem")

        def __del__(self):
            """
            Destructor of COPT_DLL class
            """
            self.delete()

        def delete(self):
            """
            Release COPT problem and environment

            This function borrowed implementation of CPLEX_DLL.releaseLicense,
            with some modifications.
            """
            # Valid environment and problem exist
            if self.coptenv is not None and self.coptprob is not None:
                # Delete problem
                rc = self.DeleteProb(byref(self.coptprob))
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to delete problem")

                # Delete environment
                rc = self.DeleteEnv(byref(self.coptenv))
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to delete environment")

                # Reset to None
                self.coptenv = None
                self.coptprob = None

        def getsolution(self, lp, ncols, nrows):
            """Get problem solution

            This function borrowed implementation of CPLEX_DLL.findSolutionValues,
            with some modifications.
            """
            status = ctypes.c_int()
            x = (ctypes.c_double * ncols)()
            dj = (ctypes.c_double * ncols)()
            pi = (ctypes.c_double * nrows)()
            slack = (ctypes.c_double * nrows)()

            var_x = {}
            var_dj = {}
            con_pi = {}
            con_slack = {}
            has_solution = False

            if lp.isMIP() and self.mip:
                hasmipsol = ctypes.c_int()
                # Get MIP problem satus
                rc = self.GetIntAttr(self.coptprob, coptstr("MipStatus"), byref(status))
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to get MIP status")
                # Has MIP solution
                rc = self.GetIntAttr(
                    self.coptprob, coptstr("HasMipSol"), byref(hasmipsol)
                )
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to check if MIP solution exists"
                    )

                # Optimal/Feasible MIP solution
                if status.value == 1 or hasmipsol.value == 1:
                    has_solution = True
                    rc = self.GetSolution(self.coptprob, byref(x))
                    if rc != 0:
                        raise PulpSolverError("COPT_PULP: Failed to get MIP solution")

                    for i in range(ncols):
                        var_x[self.n2v[i].name] = x[i]

                # Assign MIP solution to variables
                lp.assignVarsVals(var_x)
            else:
                # Get LP problem status
                rc = self.GetIntAttr(self.coptprob, coptstr("LpStatus"), byref(status))
                if rc != 0:
                    raise PulpSolverError("COPT_PULP: Failed to get LP status")

                # Optimal LP solution
                if status.value == 1:
                    has_solution = True
                    rc = self.GetLpSolution(
                        self.coptprob, byref(x), byref(slack), byref(pi), byref(dj)
                    )
                    if rc != 0:
                        raise PulpSolverError("COPT_PULP: Failed to get LP solution")

                    for i in range(ncols):
                        var_x[self.n2v[i].name] = x[i]
                        var_dj[self.n2v[i].name] = dj[i]

                    # NOTE: slacks in COPT are activities of rows
                    for i in range(nrows):
                        con_pi[self.n2c[i]] = pi[i]
                        con_slack[self.n2c[i]] = slack[i]

                # Assign LP solution to variables and constraints
                lp.assignVarsVals(var_x)
                lp.assignVarsDj(var_dj)
                lp.assignConsPi(con_pi)
                lp.assignConsSlack(con_slack)

            return coptlpstat.get(status.value, LpSolveStatus.Undefined), has_solution

        def write(self, filename):
            """
            Write problem, basis, parameter or solution to file
            """
            file_path = coptstr(filename)
            file_name, file_ext = os.path.splitext(file_path)

            if not file_ext:
                raise PulpSolverError("COPT_PULP: Failed to determine output file type")
            elif file_ext == coptstr(".mps"):
                rc = self.WriteMps(self.coptprob, file_path)
            elif file_ext == coptstr(".lp"):
                rc = self.WriteLp(self.coptprob, file_path)
            elif file_ext == coptstr(".bin"):
                rc = self.WriteBin(self.coptprob, file_path)
            elif file_ext == coptstr(".sol"):
                rc = self.WriteSol(self.coptprob, file_path)
            elif file_ext == coptstr(".bas"):
                rc = self.WriteBasis(self.coptprob, file_path)
            elif file_ext == coptstr(".mst"):
                rc = self.WriteMst(self.coptprob, file_path)
            elif file_ext == coptstr(".par"):
                rc = self.WriteParam(self.coptprob, file_path)
            else:
                raise PulpSolverError("COPT_PULP: Unsupported file type")

            if rc != 0:
                raise PulpSolverError(
                    "COPT_PULP: Failed to write file '{}'".format(filename)
                )

        def setParam(self, name, val):
            """
            Set parameter to COPT problem
            """
            par_type = ctypes.c_int()
            par_name = coptstr(name)

            rc = self.SearchParamAttr(self.coptprob, par_name, byref(par_type))
            if rc != 0:
                raise PulpSolverError(
                    "COPT_PULP: Failed to check type for '{}'".format(par_name)
                )

            if par_type.value == 0:
                rc = self.SetDblParam(self.coptprob, par_name, ctypes.c_double(val))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to set double parameter '{}'".format(
                            par_name
                        )
                    )
            elif par_type.value == 1:
                rc = self.SetIntParam(self.coptprob, par_name, ctypes.c_int(val))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to set integer parameter '{}'".format(
                            par_name
                        )
                    )
            else:
                raise PulpSolverError(
                    "COPT_PULP: Invalid parameter '{}'".format(par_name)
                )

        def getParam(self, name):
            """
            Get current value of parameter
            """
            par_dblval = ctypes.c_double()
            par_intval = ctypes.c_int()
            par_type = ctypes.c_int()
            par_name = coptstr(name)

            rc = self.SearchParamAttr(self.coptprob, par_name, byref(par_type))
            if rc != 0:
                raise PulpSolverError(
                    "COPT_PULP: Failed to check type for '{}'".format(par_name)
                )

            if par_type.value == 0:
                rc = self.GetDblParam(self.coptprob, par_name, byref(par_dblval))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to get double parameter '{}'".format(
                            par_name
                        )
                    )
                else:
                    retval = par_dblval.value
            elif par_type.value == 1:
                rc = self.GetIntParam(self.coptprob, par_name, byref(par_intval))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to get integer parameter '{}'".format(
                            par_name
                        )
                    )
                else:
                    retval = par_intval.value
            else:
                raise PulpSolverError(
                    "COPT_PULP: Invalid parameter '{}'".format(par_name)
                )

            return retval

        def getAttr(self, name):
            """
            Get attribute of the problem
            """
            attr_dblval = ctypes.c_double()
            attr_intval = ctypes.c_int()
            attr_type = ctypes.c_int()
            attr_name = coptstr(name)

            # Check attribute type by name
            rc = self.SearchParamAttr(self.coptprob, attr_name, byref(attr_type))
            if rc != 0:
                raise PulpSolverError(
                    "COPT_PULP: Failed to check type for '{}'".format(attr_name)
                )

            if attr_type.value == 2:
                rc = self.GetDblAttr(self.coptprob, attr_name, byref(attr_dblval))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to get double attribute '{}'".format(
                            attr_name
                        )
                    )
                else:
                    retval = attr_dblval.value
            elif attr_type.value == 3:
                rc = self.GetIntAttr(self.coptprob, attr_name, byref(attr_intval))
                if rc != 0:
                    raise PulpSolverError(
                        "COPT_PULP: Failed to get integer attribute '{}'".format(
                            attr_name
                        )
                    )
                else:
                    retval = attr_intval.value
            else:
                raise PulpSolverError(
                    "COPT_PULP: Invalid attribute '{}'".format(attr_name)
                )

            return retval


class COPT(LpSolver):
    """
    The COPT Optimizer via its python interface

    The COPT variables are available (after a solve) in var.solverVar
    Constraints in constraint.solverConstraint
    and the Model is in prob.solverModel
    """

    name = "COPT"

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
        self.coptenv: Any = None
        self.coptmdl: Any = None
        if coptpy_mod is None:
            return
        self.coptenv = coptpy_mod.Envr()
        self.coptmdl = self.coptenv.createModel()

        if not self.msg:
            self.coptmdl.setParam("Logging", 0)
        for key, value in solverParams.items():
            self.coptmdl.setParam(key, value)

    def findSolutionValues(self, lp):
        model = lp.solverModel
        solutionStatus = model.status

        CoptLpStatus = {
            coptpy_mod.COPT.UNSTARTED: LpSolveStatus.NotSolved,
            coptpy_mod.COPT.OPTIMAL: LpSolveStatus.Optimal,
            coptpy_mod.COPT.INFEASIBLE: LpSolveStatus.Infeasible,
            coptpy_mod.COPT.UNBOUNDED: LpSolveStatus.Unbounded,
            coptpy_mod.COPT.INF_OR_UNB: LpSolveStatus.Undefined,
            coptpy_mod.COPT.NUMERICAL: LpSolveStatus.NumericalError,
            coptpy_mod.COPT.NODELIMIT: LpSolveStatus.NodeLimit,
            coptpy_mod.COPT.IMPRECISE: LpSolveStatus.NumericalError,
            coptpy_mod.COPT.TIMEOUT: LpSolveStatus.TimeLimit,
            coptpy_mod.COPT.UNFINISHED: LpSolveStatus.Stopped,
            coptpy_mod.COPT.INTERRUPTED: LpSolveStatus.Interrupted,
        }

        if self.msg:
            print("COPT status=", solutionStatus)

        status = CoptLpStatus.get(solutionStatus, LpSolveStatus.Undefined)
        hasMipSol = bool(model.ismip and model.getAttr("HasMipSol"))
        has_solution = status == LpSolveStatus.Optimal or hasMipSol
        if not has_solution:
            return status, has_solution

        values = model.getInfo("Value", model.getVars())
        exported_vars = lp.exported_variables()
        for var, value in zip(exported_vars, values):
            var.varValue = value

        if not model.ismip:
            # COPT returns an error with an empty model
            try:
                # NOTE: slacks in COPT are activities of rows
                slacks = model.getInfo("Slack", model.getConstrs())
                for constr, value in zip(lp.constraints(), slacks):
                    constr.slack = value

                redcosts = model.getInfo("RedCost", model.getVars())
                for var, value in zip(exported_vars, redcosts):
                    var.dj = value

                duals = model.getInfo("Dual", model.getConstrs())
                for constr, value in zip(lp.constraints(), duals):
                    constr.pi = value
            except coptpy_mod.CoptError:
                # sometimes the model is not solved, and thus these infos are not available
                pass

        return status, has_solution

    def available(self):
        """True if the solver is available"""
        return coptpy_mod is not None

    def callSolver(self, lp, callback=None):
        """Solves the problem with COPT"""
        self.solveTime = -clock()
        if callback is not None:
            lp.solverModel.setCallback(
                callback,
                coptpy_mod.COPT.CBCONTEXT_MIPRELAX | coptpy_mod.COPT.CBCONTEXT_MIPSOL,
            )
        lp.solverModel.solve()
        self.solveTime += clock()

    @requires("coptpy")
    def buildSolverModel(self, lp):
        """
        Takes the pulp lp model and translates it into a COPT model
        """
        lp.solverModel = self.coptmdl

        if lp.sense == LpMaximize:
            lp.solverModel.objsense = coptpy_mod.COPT.MAXIMIZE
        if self.timeLimit:
            lp.solverModel.setParam("TimeLimit", self.timeLimit)

        gapRel = self.optionsDict.get("gapRel")
        logPath = self.optionsDict.get("logPath")
        if gapRel:
            lp.solverModel.setParam("RelGap", gapRel)
        if logPath:
            lp.solverModel.setLogFile(logPath)

        var_handles = []
        exported_vars = lp.exported_variables()
        id_to_col = {v.id: j for j, v in enumerate(exported_vars)}
        for var in exported_vars:
            lowBound = var.lowBound
            if not math.isfinite(lowBound):
                lowBound = -coptpy_mod.COPT.INFINITY
            upBound = var.upBound
            if not math.isfinite(upBound):
                upBound = coptpy_mod.COPT.INFINITY
            obj = lp.objective.get(var, 0.0)
            varType = coptpy_mod.COPT.CONTINUOUS
            if var.cat == LpInteger and self.mip:
                varType = coptpy_mod.COPT.INTEGER
            cvar = lp.solverModel.addVar(
                lowBound, upBound, vtype=varType, obj=obj, name=var.name
            )
            var_handles.append(cvar)

        if self.optionsDict.get("warmStart", False):
            for var in exported_vars:
                if var.varValue is not None:
                    lp.solverModel.setMipStart(
                        var_handles[id_to_col[var.id]], var.varValue
                    )
            lp.solverModel.loadMipStart()

        for constraint in lp.constraints():
            name = constraint.name
            solver_vars = [var_handles[id_to_col[v.id]] for v in constraint.keys()]
            expr = coptpy_mod.LinExpr(solver_vars, list(constraint.values()))
            if constraint.sense == LpConstraintLE:
                relation = coptpy_mod.COPT.LESS_EQUAL
            elif constraint.sense == LpConstraintGE:
                relation = coptpy_mod.COPT.GREATER_EQUAL
            elif constraint.sense == LpConstraintEQ:
                relation = coptpy_mod.COPT.EQUAL
            else:
                raise PulpSolverError("Detected an invalid constraint type")
            lp.solverModel.addConstr(expr, relation, -constraint.constant, name)

    @requires("coptpy")
    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> LpSolveStats:
        """
        Solve a well formulated lp problem

        creates a COPT model, variables and constraints and attaches
        them to the lp model which it then solves
        """
        start = clocks()
        callback = kwargs.get("callback")
        self.buildSolverModel(lp)
        self.callSolver(lp, callback=callback)

        status, has_solution = self.findSolutionValues(lp)
        return self.buildStats(lp, status, has_solution, start=start)
