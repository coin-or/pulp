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

from .core import LpSolver_CMD, LpSolver, PulpSolverError, log
from io import StringIO
from contextlib import redirect_stdout
import os
import sys
from .. import constants
import warnings
from typing import Union

from uuid import uuid4

# The maximum length of the names of variables and constraints.
MAX_NAME_LENGTH = 256

# This combines all status codes from OPTLP/solvelp and OPTMILP/solvemilp
SOLSTATUS_TO_STATUS = {
    "OPTIMAL": constants.LpStatusOptimal,
    "OPTIMAL_AGAP": constants.LpStatusOptimal,
    "OPTIMAL_RGAP": constants.LpStatusOptimal,
    "OPTIMAL_COND": constants.LpStatusOptimal,
    "TARGET": constants.LpStatusOptimal,
    "CONDITIONAL_OPTIMAL": constants.LpStatusOptimal,
    "FEASIBLE": constants.LpStatusNotSolved,
    "INFEASIBLE": constants.LpStatusInfeasible,
    "UNBOUNDED": constants.LpStatusUnbounded,
    "INFEASIBLE_OR_UNBOUNDED": constants.LpStatusUnbounded,
    "SOLUTION_LIM": constants.LpStatusNotSolved,
    "NODE_LIM_SOL": constants.LpStatusNotSolved,
    "NODE_LIM_NOSOL": constants.LpStatusNotSolved,
    "ITERATION_LIMIT_REACHED": constants.LpStatusNotSolved,
    "TIME_LIM_SOL": constants.LpStatusNotSolved,
    "TIME_LIM_NOSOL": constants.LpStatusNotSolved,
    "TIME_LIMIT_REACHED": constants.LpStatusNotSolved,
    "ABORTED": constants.LpStatusNotSolved,
    "ABORT_SOL": constants.LpStatusNotSolved,
    "ABORT_NOSOL": constants.LpStatusNotSolved,
    "OUTMEM_SOL": constants.LpStatusNotSolved,
    "OUTMEM_NOSOL": constants.LpStatusNotSolved,
    "FAILED": constants.LpStatusNotSolved,
    "FAIL_SOL": constants.LpStatusNotSolved,
    "FAIL_NOSOL": constants.LpStatusNotSolved,
    "ERROR": constants.LpStatusNotSolved,
}

CAS_OPTION_NAMES = [
    "hostname",
    "port",
    "username",
    "password",
    "session",
    "locale",
    "name",
    "nworkers",
    "authinfo",
    "protocol",
    "path",
    "ssl_ca_list",
    "authcode",
]


class SASsolver(LpSolver_CMD):
    name = "SASsolver"

    def __init__(
        self,
        mip=True,
        msg=True,
        warmStart=False,
        keepFiles=False,
        timeLimit=None,
        **solverParams,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param bool warmStart: if False, no warm start
        :param bool keepFiles: if False, the generated mps mst files will be removed
        :param solverParams: SAS proc OPTMILP or OPTLP parameters
        """
        LpSolver_CMD.__init__(
            self, mip=mip, msg=msg, warmStart=warmStart, keepFiles=keepFiles
        )
        self.timeLimit = timeLimit
        # Only named options are allowed in SAS solvers.
        self.solverOptions = {key: value for key, value in solverParams.items()}

    def _create_statement_str(self, statement):
        """Helper function to create the strings for the statements of the proc OPTLP/OPTMILP code."""
        stmt = self.solverOptions.pop(statement, None)
        if stmt:
            return (
                statement.strip()
                + " "
                + " ".join(option + "=" + str(value) for option, value in stmt.items())
                + ";"
            )
        else:
            return ""

    def defaultPath(self):
        return os.path.abspath(os.getcwd())

    def _write_sol(self, filename, vs):
        """Writes a SAS solution file"""
        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        with open(filename, "w") as f:
            f.write("_VAR_,_VALUE_\n")
            for name, value in values:
                f.write(f"{name},{value}\n")
        return True

    def _get_max_upload_len(self, fileName):
        maxLen = 0
        with open(fileName, "r") as f:
            for line in f.readlines():
                maxLen = max(maxLen, max([len(word) for word in line.split(" ")]))
        return maxLen + 1

    def _read_solution(self, lp, primal_out, dual_out):
        status = SOLSTATUS_TO_STATUS[self._macro.get("SOLUTION_STATUS", "ERROR")]

        if self.proc == "OPTLP":
            # TODO: Check whether there is better implementation than zip().
            values = dict(zip(primal_out["_VAR_"], primal_out["_VALUE_"]))
            rc = dict(zip(primal_out["_VAR_"], primal_out["_R_COST_"]))
            lp.assignVarsVals(values)
            lp.assignVarsDj(rc)

            prices = dict(zip(dual_out["_ROW_"], dual_out["_VALUE_"]))
            slacks = dict(zip(dual_out["_ROW_"], dual_out["_ACTIVITY_"]))
            lp.assignConsPi(prices)
            lp.assignConsSlack(slacks, activity=True)
        else:
            # Convert primal out data set to variable dictionary
            # Use pandas functions for efficiency
            values = dict(zip(primal_out["_VAR_"], primal_out["_VALUE_"]))
            lp.assignVarsVals(values)
        lp.assignStatus(status)
        return status


class SAS94(SASsolver):
    name = "SAS94"

    try:
        global saspy
        import saspy

    except:

        def available(self):
            """True if SAS94 is available."""
            return False

        def sasAvailable(self):
            return False

        def actualSolve(self, lp, callback=None):
            """Solves a well-formulated lp problem."""
            raise PulpSolverError("SAS94 : Not Available")

    else:
        saspy.logger.setLevel(log.level)

        def __init__(
            self,
            mip=True,
            msg=True,
            keepFiles=False,
            warmStart=False,
            timeLimit=None,
            sas=None,
            **solverParams,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param bool keepFiles: if False, mps and mst files will not be saved
            :param bool warmStart: if False, no warmstart or initial primal solution provided
            :param object sas: sas session. It must be provided by the user.
            :param solverParams: SAS proc OPTMILP or OPTLP parameters
            """
            SASsolver.__init__(
                self,
                mip=mip,
                msg=msg,
                keepFiles=keepFiles,
                warmStart=warmStart,
                timeLimit=timeLimit,
                **solverParams,
            )

            self.sas = sas

        def available(self):
            """True if SAS94 is available."""
            return True

        def sasAvailable(self):
            if not self.sas:
                return False
            try:
                self.sas.sasver
                return True
            except:
                return False

        def toDict(self):
            data = dict(solver=self.name)
            for k in ["mip", "msg", "keepFiles", "warmStart"]:
                try:
                    data[k] = getattr(self, k)
                except AttributeError:
                    pass
            for k in ["sas", "timeLimit"]:
                # with these ones, we only export if it has some content:
                try:
                    value = getattr(self, k)
                    if value:
                        data[k] = value
                except AttributeError:
                    pass
            data.update(self.solverOptions)
            return data

        def actualSolve(self, lp):
            """Solve a well formulated lp problem"""
            log.debug("Running SAS")
            if not self.sasAvailable():
                raise PulpSolverError(
                    "SAS94: Provide a valid SAS session by parameter sas=."
                )
            if len(lp.sos1) or len(lp.sos2):
                raise PulpSolverError(
                    "SAS94: Currently SAS doesn't support SOS1 and SOS2."
                )

            postfix = uuid4().hex[:16]
            tmpMps, tmpMst = self.create_tmp_files(lp.name, "mps", "mst")

            vs = lp.writeMPS(tmpMps, with_objsense=False)

            nameLen = self._get_max_upload_len(tmpMps)
            if nameLen > MAX_NAME_LENGTH:
                raise PulpSolverError(
                    f"SAS94: The lengths of the variable or constraint names \
                                    (including indices) should not exceed {MAX_NAME_LENGTH}."
                )

            proc = self.proc = "OPTMILP" if self.mip else "OPTLP"

            # Get Obj Sense
            if lp.sense == constants.LpMaximize:
                self.solverOptions["objsense"] = "max"
            elif lp.sense == constants.LpMinimize:
                self.solverOptions["objsense"] = "min"
            else:
                raise PulpSolverError("SAS94 : Objective sense should be min or max.")

            # Get timeLimit. SAS solvers use MAXTIME instead of timeLimit as a parameter.
            if self.timeLimit:
                self.solverOptions["MAXTIME"] = self.timeLimit
            # Get the rootnode options
            decomp_str = self._create_statement_str("decomp")
            decompmaster_str = self._create_statement_str("decompmaster")
            decompmasterip_str = self._create_statement_str("decompmasterip")
            decompsubprob_str = self._create_statement_str("decompsubprob")
            rootnode_str = self._create_statement_str("rootnode")

            if lp.isMIP() and not self.mip:
                warnings.warn(
                    "SAS94 will solve the relaxed problem of the MILP instance."
                )
            # Handle warmstart
            warmstart_str = ""
            if self.optionsDict.get("warmStart", False):
                self._write_sol(filename=tmpMst, vs=vs)

                # Set the warmstart basis option
                if proc == "OPTMILP":
                    warmstart_str = """
                                    proc import datafile='{primalin}'
                                        out=primalin{postfix}
                                        dbms=csv
                                        replace;
                                        getnames=yes;
                                        run;
                                    """.format(
                        primalin=tmpMst,
                        postfix=postfix,
                    )
                elif proc == "OPTLP":
                    pass

            # Convert options to string
            opt_str = " ".join(
                option + "=" + str(value)
                for option, value in self.solverOptions.items()
            )
            sas = self.sas

            # Find the version of 9.4 we are using
            if sas.sasver.startswith("9.04.01M5"):
                # In 9.4M5 we have to create an MPS data set from an MPS file first
                # Earlier versions will not work because the MPS format in incompatible'
                res = sas.submit(
                    """
                                option notes nonumber nodate nosource pagesize=max;
                                {warmstart}
                                %MPS2SASD(MPSFILE="{mpsfile}", OUTDATA=mpsdata{postfix}, MAXLEN={maxLen}, FORMAT=FREE);
                                proc {proc} data=mpsdata{postfix} {options} primalout=primalout{postfix} dualout=dualout{postfix};
                                {decomp}
                                {decompmaster}
                                {decompmasterip}
                                {decompsubprob}
                                {rootnode}
                                proc delete data=mpsdata{postfix};
                                run;
                                """.format(
                        warmstart=warmstart_str,
                        postfix=postfix,
                        mpsfile=tmpMps,
                        proc=proc,
                        maxLen=min(nameLen, MAX_NAME_LENGTH),
                        options=opt_str,
                        decomp=decomp_str,
                        decompmaster=decompmaster_str,
                        decompmasterip=decompmasterip_str,
                        decompsubprob=decompsubprob_str,
                        rootnode=rootnode_str,
                    ),
                    results="TEXT",
                )
            else:
                # Since 9.4M6+ optlp/optmilp can read mps files directly
                # TODO: Check whether there are limits for length of variable and constraint names
                res = sas.submit(
                    """
                                option notes nonumber nodate nosource pagesize=max;
                                {warmstart}
                                proc {proc} mpsfile=\"{mpsfile}\" {options} primalout=primalout{postfix} dualout=dualout{postfix};
                                {decomp}
                                {decompmaster}
                                {decompmasterip}
                                {decompsubprob}
                                {rootnode}
                                run;
                                """.format(
                        warmstart=warmstart_str,
                        postfix=postfix,
                        proc=proc,
                        mpsfile=tmpMps,
                        options=opt_str,
                        decomp=decomp_str,
                        decompmaster=decompmaster_str,
                        decompmasterip=decompmasterip_str,
                        decompsubprob=decompsubprob_str,
                        rootnode=rootnode_str,
                    ),
                    results="TEXT",
                )

            self.delete_tmp_files(tmpMps, tmpMst)

            # Store SAS output
            if self.msg:
                print(res["LOG"])
            self._macro = dict(
                (key.strip(), value.strip())
                for key, value in (
                    pair.split("=") for pair in sas.symget("_OR" + proc + "_").split()
                )
            )

            primal_out = sas.sd2df(f"primalout{postfix}")
            dual_out = sas.sd2df(f"dualout{postfix}")

            if self._macro.get("STATUS", "ERROR") != "OK":
                raise PulpSolverError(
                    "PuLP: Error ({err_name}) \
                        while trying to solve the instance: {name}".format(
                        err_name=self._macro.get("STATUS", "ERROR"), name=lp.name
                    )
                )
            status = self._read_solution(lp, primal_out, dual_out)

            return status


class SASCAS(SASsolver):
    name = "SASCAS"

    try:
        global swat
        import swat

    except ImportError:

        def available(self):
            """True if SASCAS is available."""
            return False

        def sasAvailable(self):
            return False

        def actualSolve(self, lp, callback=None):
            """Solves a well-formulated lp problem."""
            raise PulpSolverError("SASCAS : Not Available")

    else:

        def __init__(
            self,
            mip=True,
            msg=True,
            keepFiles=False,
            warmStart=False,
            timeLimit=None,
            cas=None,
            **solverParams,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param bool keepFiles: if False, mps and mst files will not be saved
            :param bool warmStart: if False, no warmstart or initial primal solution provided
            :param cas: CAS object. See swat.CAS
            :param solverParams: SAS proc OPTMILP or OPTLP parameters
            """
            SASsolver.__init__(
                self,
                mip=mip,
                msg=msg,
                keepFiles=keepFiles,
                warmStart=warmStart,
                timeLimit=timeLimit,
                **solverParams,
            )
            self.cas = cas

        def available(self):
            return True

        def sasAvailable(self):
            if self.cas == None:
                return False
            try:
                with redirect_stdout(SASLogWriter(self.msg)) as self._log_writer:
                    # Load the optimization action set
                    self.cas.loadactionset("optimization")
                    return True
            except:
                return False

        def toDict(self):
            data = dict(solver=self.name)
            for k in ["mip", "msg", "warmStart", "keepFiles"]:
                try:
                    data[k] = getattr(self, k)
                except AttributeError:
                    pass
            for k in ["cas", "timeLimit"]:
                # with these ones, we only export if it has some content:
                try:
                    value = getattr(self, k)
                    if value:
                        data[k] = value
                except AttributeError:
                    pass
            data.update(self.solverOptions)
            return data

        def actualSolve(self, lp):
            """Solve a well formulated lp problem"""
            log.debug("Running SAS")

            if not self.sasAvailable():
                raise PulpSolverError(
                    """SASCAS: Provide a valid CAS session by parameter cas=."""
                )

            # if (self.cas_options == {}):
            #     raise PulpSolverError("""SASCAS: Provide cas_options with
            #         {port: , host: , authinfo: }
            #         or {port: , host: , username: , password: }.""")

            if len(lp.sos1) or len(lp.sos2):
                raise PulpSolverError(
                    "SASCAS: Currently SAS doesn't support SOS1 and SOS2."
                )

            s = self.cas
            proc = self.proc = "OPTMILP" if self.mip else "OPTLP"
            # Get Obj Sense
            if lp.sense == constants.LpMaximize:
                self.solverOptions["objsense"] = "max"
            elif lp.sense == constants.LpMinimize:
                self.solverOptions["objsense"] = "min"
            else:
                raise PulpSolverError("SASCAS : Objective sense should be min or max.")

            # Get timeLimit. SAS solvers use MAXTIME instead of timeLimit as a parameter.
            if self.timeLimit:
                self.solverOptions["MAXTIME"] = self.timeLimit

            status = None
            with redirect_stdout(SASLogWriter(self.msg)) as self._log_writer:

                # Used for naming the data structure in SAS.
                postfix = uuid4().hex[:16]
                tmpMps, tmpMpsCsv, tmpMstCsv = self.create_tmp_files(
                    lp.name, "mps", "mps.csv", "mst.csv"
                )
                vs = lp.writeMPS(tmpMps, with_objsense=False)

                nameLen = self._get_max_upload_len(tmpMps)
                if nameLen > MAX_NAME_LENGTH:
                    raise PulpSolverError(
                        f"SASCAS: The lengths of the variable or constraint names \
                                        (including indices) should not exceed {MAX_NAME_LENGTH}."
                    )
                try:
                    # # Load the optimization action set
                    # s.loadactionset('optimization')
                    if lp.isMIP() and not self.mip:
                        warnings.warn(
                            "SASCAS will solve the relaxed problem of the MILP instance."
                        )
                    # load_mps
                    self._load_mps(s, tmpMps, tmpMpsCsv, postfix, nameLen)

                    if self.optionsDict.get("warmStart", False) and (proc == "OPTMILP"):
                        self._write_sol(filename=tmpMstCsv, vs=vs)
                        # Upload warmstart file to CAS
                        s.upload_file(
                            tmpMstCsv,
                            casout={"name": f"primalin{postfix}", "replace": True},
                            importoptions={"filetype": "CSV"},
                        )
                        self.solverOptions["primalin"] = f"primalin{postfix}"
                    # Delete the temp files.
                    self.delete_tmp_files(tmpMps, tmpMstCsv, tmpMpsCsv)

                    # Solve the problem in CAS
                    if proc == "OPTMILP":
                        r = s.optimization.solveMilp(
                            data={"name": f"mpsdata{postfix}"},
                            primalOut={"name": f"primalout{postfix}", "replace": True},
                            **self.solverOptions,
                        )
                    else:
                        r = s.optimization.solveLp(
                            data={"name": f"mpsdata{postfix}"},
                            primalOut={"name": f"primalout{postfix}", "replace": True},
                            dualOut={"name": f"dualout{postfix}", "replace": True},
                            **self.solverOptions,
                        )
                    if r:
                        primal_out, dual_out = self._get_output(lp, s, r, proc, postfix)
                        status = self._read_solution(lp, primal_out, dual_out)
                finally:
                    self.delete_tmp_files(tmpMps, tmpMstCsv, tmpMpsCsv)

            if self.msg:
                print(self._log_writer.log())
            if status:
                return status
            else:
                raise PulpSolverError(
                    f"PuLP: Error while trying to solve the instance: \
                                {lp.name} via SASCAS."
                )

    def _get_output(self, lp, s, r, proc, postfix):
        self._macro = {
            "STATUS": r.get("status", "ERROR").upper(),
            "SOLUTION_STATUS": r.get("solutionStatus", "ERROR").upper(),
        }
        if self._macro.get("STATUS", "ERROR") != "OK":
            raise PulpSolverError(
                "PuLP: Error ({err_name}) while trying to solve the instance: {name}".format(
                    err_name=self._macro.get("STATUS", "ERROR"), name=lp.name
                )
            )
        # If we get solution successfully.
        if proc == "OPTMILP":
            primal_out = s.CASTable(name=f"primalout{postfix}")
            primal_out = primal_out[["_VAR_", "_VALUE_", "_STATUS_", "_R_COST_"]]
            dual_out = None
        else:
            primal_out = s.CASTable(name=f"primalout{postfix}")
            primal_out = primal_out[["_VAR_", "_VALUE_", "_STATUS_", "_R_COST_"]]
            dual_out = s.CASTable(name=f"dualout{postfix}")
            dual_out = dual_out[["_ROW_", "_VALUE_", "_STATUS_", "_ACTIVITY_"]]
        return primal_out, dual_out

    def _load_mps(self, s, tmpMps, tmpMpsCsv, postfix, nameLen):
        if os.stat(tmpMps).st_size >= 2 * 1024**3:
            # For large files, use convertMPS, first create file for upload
            with open(tmpMpsCsv, "w") as mpsWithId:
                mpsWithId.write("_ID_\tText\n")
                with open(tmpMps, "r") as f:
                    id = 0
                    for line in f:
                        id += 1
                        mpsWithId.write(str(id) + "\t" + line.rstrip() + "\n")

            # Upload .mps.csv file
            s.upload_file(
                tmpMpsCsv,
                casout={"name": f"mpscsv{postfix}", "replace": True},
                importoptions={"filetype": "CSV", "delimiter": "\t"},
            )

            # Convert .mps.csv file to .mps
            s.optimization.convertMps(
                data=f"mpscsv{postfix}",
                casOut={"name": f"mpsdata{postfix}", "replace": True},
                format="FREE",
                maxLength=min(nameLen, MAX_NAME_LENGTH),
            )
        else:
            # For small files, use loadMPS
            with open(tmpMps, "r") as mps_file:
                s.optimization.loadMps(
                    mpsFileString=mps_file.read(),
                    casout={"name": f"mpsdata{postfix}", "replace": True},
                    format="FREE",
                    maxLength=min(nameLen, MAX_NAME_LENGTH),
                )


class SASLogWriter:
    # Helper class to take the log from stdout and put it also in a StringIO.
    def __init__(self, tee):
        # Set up the two outputs.
        self.tee = tee
        self._log = StringIO()
        self.stdout = sys.stdout

    def write(self, message):
        # If the tee options is specified, write to both outputs.
        if self.tee:
            self.stdout.write(message)
        self._log.write(message)

    def flush(self):
        # Do nothing since we flush right away
        pass

    def log(self):
        # Get the log as a string.
        return self._log.getvalue()
