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

from .core import LpSolver_CMD, subprocess, PulpSolverError
from .. import constants
import warnings
import sys
import re


class XPRESS(LpSolver_CMD):
    """The XPRESS LP solver"""

    name = "XPRESS"

    def __init__(
        self,
        mip=True,
        msg=True,
        timeLimit=None,
        gapRel=None,
        options=None,
        keepFiles=False,
        path=None,
        maxSeconds=None,
        targetGap=None,
        heurFreq=None,
        heurStra=None,
        coverCuts=None,
        preSolve=None,
        warmStart=False,
    ):
        """
        Initializes the Xpress solver.

        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param maxSeconds: deprecated for timeLimit
        :param targetGap: deprecated for gapRel
        :param heurFreq: the frequency at which heuristics are used in the tree search
        :param heurStra: heuristic strategy
        :param coverCuts: the number of rounds of lifted cover inequalities at the top node
        :param preSolve: whether presolving should be performed before the main algorithm
        :param options: Adding more options, e.g. options = ["NODESELECTION=1", "HEURDEPTH=5"]
                        More about Xpress options and control parameters please see
                        https://www.fico.com/fico-xpress-optimization/docs/latest/solver/optimizer/HTML/chapter7.html
        :param bool warmStart: if True, then use current variable values as start
        """
        if maxSeconds:
            warnings.warn("Parameter maxSeconds is being depreciated for timeLimit")
            if timeLimit is not None:
                warnings.warn(
                    "Parameter timeLimit and maxSeconds passed, using timeLimit"
                )
            else:
                timeLimit = maxSeconds
        if targetGap is not None:
            warnings.warn("Parameter targetGap is being depreciated for gapRel")
            if gapRel is not None:
                warnings.warn("Parameter gapRel and epgap passed, using gapRel")
            else:
                gapRel = targetGap
        LpSolver_CMD.__init__(
            self,
            gapRel=gapRel,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            path=path,
            keepFiles=keepFiles,
            heurFreq=heurFreq,
            heurStra=heurStra,
            coverCuts=coverCuts,
            preSolve=preSolve,
            warmStart=warmStart,
        )

    def defaultPath(self):
        return self.executableExtension("optimizer")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpCmd, tmpAttr, tmpStart = self.create_tmp_files(
            lp.name, "lp", "prt", "cmd", "attr", "slx"
        )
        variables = lp.writeLP(tmpLp, writeSOS=1, mip=self.mip)
        if self.optionsDict.get("warmStart", False):
            start = [(v.name, v.value()) for v in variables if v.value() is not None]
            self.writeslxsol(tmpStart, start)
        # Explicitly capture some attributes so that we can easily get
        # information about the solution.
        attrNames = []
        if lp.isMIP() and self.mip:
            attrNames.extend(["mipobjval", "bestbound", "mipstatus"])
            statusmap = {
                0: constants.LpStatusUndefined,  # XPRS_MIP_NOT_LOADED
                1: constants.LpStatusUndefined,  # XPRS_MIP_LP_NOT_OPTIMAL
                2: constants.LpStatusUndefined,  # XPRS_MIP_LP_OPTIMAL
                3: constants.LpStatusUndefined,  # XPRS_MIP_NO_SOL_FOUND
                4: constants.LpStatusUndefined,  # XPRS_MIP_SOLUTION
                5: constants.LpStatusInfeasible,  # XPRS_MIP_INFEAS
                6: constants.LpStatusOptimal,  # XPRS_MIP_OPTIMAL
                7: constants.LpStatusUndefined,  # XPRS_MIP_UNBOUNDED
            }
            statuskey = "mipstatus"
        else:
            attrNames.extend(["lpobjval", "lpstatus"])
            statusmap = {
                0: constants.LpStatusNotSolved,  # XPRS_LP_UNSTARTED
                1: constants.LpStatusOptimal,  # XPRS_LP_OPTIMAL
                2: constants.LpStatusInfeasible,  # XPRS_LP_INFEAS
                3: constants.LpStatusUndefined,  # XPRS_LP_CUTOFF
                4: constants.LpStatusUndefined,  # XPRS_LP_UNFINISHED
                5: constants.LpStatusUnbounded,  # XPRS_LP_UNBOUNDED
                6: constants.LpStatusUndefined,  # XPRS_LP_CUTOFF_IN_DUAL
                7: constants.LpStatusNotSolved,  # XPRS_LP_UNSOLVED
                8: constants.LpStatusUndefined,  # XPRS_LP_NONCONVEX
            }
            statuskey = "lpstatus"
        with open(tmpCmd, "w") as cmd:
            if not self.msg:
                cmd.write("OUTPUTLOG=0\n")
            # The readprob command must be in lower case for correct filename handling
            cmd.write("readprob " + self.quote_path(tmpLp) + "\n")
            if self.timeLimit is not None:
                cmd.write("MAXTIME=%d\n" % self.timeLimit)
            targetGap = self.optionsDict.get("gapRel")
            if targetGap is not None:
                cmd.write("MIPRELSTOP=%f\n" % targetGap)
            heurFreq = self.optionsDict.get("heurFreq")
            if heurFreq is not None:
                cmd.write("HEURFREQ=%d\n" % heurFreq)
            heurStra = self.optionsDict.get("heurStra")
            if heurStra is not None:
                cmd.write("HEURSTRATEGY=%d\n" % heurStra)
            coverCuts = self.optionsDict.get("coverCuts")
            if coverCuts is not None:
                cmd.write("COVERCUTS=%d\n" % coverCuts)
            preSolve = self.optionsDict.get("preSolve")
            if preSolve is not None:
                cmd.write("PRESOLVE=%d\n" % preSolve)
            if self.optionsDict.get("warmStart", False):
                cmd.write("readslxsol " + self.quote_path(tmpStart) + "\n")
            for option in self.options:
                cmd.write(option + "\n")
            if lp.sense == constants.LpMaximize:
                cmd.write("MAXIM\n")
            else:
                cmd.write("MINIM\n")
            if lp.isMIP() and self.mip:
                cmd.write("GLOBAL\n")
            # The writeprtsol command must be in lower case for correct filename handling
            cmd.write("writeprtsol " + self.quote_path(tmpSol) + "\n")
            cmd.write(
                'set fh [open "%s" w]; list\n' % tmpAttr
            )  # `list` to suppress output

            for attr in attrNames:
                cmd.write('puts $fh "%s=$%s"\n' % (attr, attr))
            cmd.write("close $fh\n")
            cmd.write("QUIT\n")
        with open(tmpCmd, "r") as cmd:
            consume = False
            subout = None
            suberr = None
            if not self.msg:
                # Xpress writes a banner before we can disable output. So
                # we have to explicitly consume the banner.
                if sys.hexversion >= 0x03030000:
                    subout = subprocess.DEVNULL
                    suberr = subprocess.DEVNULL
                else:
                    # We could also use open(os.devnull, 'w') but then we
                    # would be responsible for closing the file.
                    subout = subprocess.PIPE
                    suberr = subprocess.STDOUT
                    consume = True
            xpress = subprocess.Popen(
                [self.path, lp.name],
                shell=True,
                stdin=cmd,
                stdout=subout,
                stderr=suberr,
                universal_newlines=True,
            )
            if consume:
                # Special case in which messages are disabled and we have
                # to consume any output
                for _ in xpress.stdout:
                    pass

            if xpress.wait() != 0:
                raise PulpSolverError("PuLP: Error while executing " + self.path)
        values, redcost, slacks, duals, attrs = self.readsol(tmpSol, tmpAttr)
        self.delete_tmp_files(tmpLp, tmpSol, tmpCmd, tmpAttr)
        status = statusmap.get(attrs.get(statuskey, -1), constants.LpStatusUndefined)
        lp.assignVarsVals(values)
        lp.assignVarsDj(redcost)
        lp.assignConsSlack(slacks)
        lp.assignConsPi(duals)
        lp.assignStatus(status)
        return status

    @staticmethod
    def readsol(filename, attrfile):
        """Read an XPRESS solution file"""
        values = {}
        redcost = {}
        slacks = {}
        duals = {}
        with open(filename) as f:
            for lineno, _line in enumerate(f):
                # The first 6 lines are status information
                if lineno < 6:
                    continue
                elif lineno == 6:
                    # Line with status information
                    _line = _line.split()
                    rows = int(_line[2])
                    cols = int(_line[5])
                elif lineno < 10:
                    # Empty line, "Solution Statistics", objective direction
                    pass
                elif lineno == 10:
                    # Solution status
                    pass
                else:
                    # There is some more stuff and then follows the "Rows" and
                    # "Columns" section. That other stuff does not match the
                    # format of the rows/columns lines, so we can keep the
                    # parser simple
                    line = _line.split()
                    if len(line) > 1:
                        if line[0] == "C":
                            # A column
                            # (C, Number, Name, At, Value, Input Cost, Reduced Cost)
                            name = line[2]
                            values[name] = float(line[4])
                            redcost[name] = float(line[6])
                        elif len(line[0]) == 1 and line[0] in "LGRE":
                            # A row
                            # ([LGRE], Number, Name, At, Value, Slack, Dual, RHS)
                            name = line[2]
                            slacks[name] = float(line[5])
                            duals[name] = float(line[6])
        # Read the attributes that we wrote explicitly
        attrs = dict()
        with open(attrfile) as f:
            for line in f:
                fields = line.strip().split("=")
                if len(fields) == 2 and fields[0].lower() == fields[0]:
                    value = fields[1].strip()
                    try:
                        value = int(fields[1].strip())
                    except ValueError:
                        try:
                            value = float(fields[1].strip())
                        except ValueError:
                            pass
                    attrs[fields[0].strip()] = value
        return values, redcost, slacks, duals, attrs

    def writeslxsol(self, name, *values):
        """
        Write a solution file in SLX format.
        The function can write multiple solutions to the same file, each
        solution must be passed as a list of (name,value) pairs. Solutions
        are written in the order specified and are given names "solutionN"
        where N is the index of the solution in the list.

        :param string name: file name
        :param list values: list of lists of (name,value) pairs
        """
        with open(name, "w") as slx:
            for i, sol in enumerate(values):
                slx.write("NAME solution%d\n" % i)
                for name, value in sol:
                    slx.write(" C      %s %.16f\n" % (name, value))
            slx.write("ENDATA\n")

    @staticmethod
    def quote_path(path):
        """
        Quotes a path for the Xpress optimizer console, by wrapping it in
        double quotes and escaping the following characters, which would
        otherwise be interpreted by the Tcl shell: \ $ " [
        """
        return '"' + re.sub(r'([\\$"[])', r"\\\1", path) + '"'
