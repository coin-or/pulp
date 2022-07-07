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
        warmStart=False
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
        tmpLp, tmpSol, tmpCmd, tmpAttr, tmpStart = \
            self.create_tmp_files(lp.name, "lp", "prt", "cmd", "attr", "slx")
        variables = lp.writeLP(tmpLp, writeSOS=1, mip=self.mip)
        if self.optionsDict.get("warmStart", False):
            start = [(v.name, v.value()) for v in variables if v.value() is not None]
            self.writeslxsol(tmpStart, start)
        # Explicitly capture some attributes so that we can easily get
        # information about the solution.
        attrNames = []
        if lp.isMIP() and self.mip:
            attrNames.extend(['mipobjval', 'bestbound', 'mipstatus'])
            statusmap = { 0: constants.LpStatusUndefined,  # XPRS_MIP_NOT_LOADED
                          1: constants.LpStatusUndefined,  # XPRS_MIP_LP_NOT_OPTIMAL
                          2: constants.LpStatusUndefined,  # XPRS_MIP_LP_OPTIMAL
                          3: constants.LpStatusUndefined,  # XPRS_MIP_NO_SOL_FOUND
                          4: constants.LpStatusUndefined,  # XPRS_MIP_SOLUTION
                          5: constants.LpStatusInfeasible, # XPRS_MIP_INFEAS
                          6: constants.LpStatusOptimal,    # XPRS_MIP_OPTIMAL
                          7: constants.LpStatusUndefined   # XPRS_MIP_UNBOUNDED
            }
            statuskey = 'mipstatus'
        else:
            attrNames.extend(['lpobjval', 'lpstatus'])
            statusmap = { 0: constants.LpStatusNotSolved,  # XPRS_LP_UNSTARTED
                          1: constants.LpStatusOptimal,    # XPRS_LP_OPTIMAL
                          2: constants.LpStatusInfeasible, # XPRS_LP_INFEAS
                          3: constants.LpStatusUndefined,  # XPRS_LP_CUTOFF
                          4: constants.LpStatusUndefined,  # XPRS_LP_UNFINISHED
                          5: constants.LpStatusUnbounded,  # XPRS_LP_UNBOUNDED
                          6: constants.LpStatusUndefined,  # XPRS_LP_CUTOFF_IN_DUAL
                          7: constants.LpStatusNotSolved,  # XPRS_LP_UNSOLVED
                          8: constants.LpStatusUndefined   # XPRS_LP_NONCONVEX
            }
            statuskey = 'lpstatus'
        with open(tmpCmd, 'w') as cmd:
            if not self.msg:
                cmd.write("OUTPUTLOG=0\n")
            # The readprob command must be in lower case for correct filename handling
            cmd.write("readprob {" + tmpLp + "}\n")
            if self.timeLimit:
                cmd.write("MAXTIME=%d\n" % self.timeLimit)
            targetGap = self.optionsDict.get("gapRel")
            if targetGap:
                cmd.write("MIPRELSTOP=%f\n" % targetGap)
            heurFreq = self.optionsDict.get("heurFreq")
            if heurFreq:
                cmd.write("HEURFREQ=%d\n" % heurFreq)
            heurStra = self.optionsDict.get("heurStra")
            if heurStra:
                cmd.write("HEURSTRATEGY=%d\n" % heurStra)
            coverCuts = self.optionsDict.get("coverCuts")
            if coverCuts:
                cmd.write("COVERCUTS=%d\n" % coverCuts)
            preSolve = self.optionsDict.get("preSolve")
            if preSolve:
                cmd.write("PRESOLVE=%d\n" % preSolve)
            if self.optionsDict.get("warmStart", False):
                cmd.write("readslxsol {" + tmpStart + "}\n")
            for option in self.options:
                cmd.write(option + "\n")
            if lp.sense == constants.LpMaximize:
                cmd.write("MAXIM\n")
            else:
                cmd.write("MINIM\n")
            if lp.isMIP() and self.mip:
                cmd.write("GLOBAL\n")
            # The writeprtsol command must be in lower case for correct filename handling
            cmd.write("writeprtsol {" + tmpSol + "}\n")
            for attr in attrNames:
                cmd.write('exec echo "%s=$%s" >> %s\n' % (attr, attr, tmpAttr))
            cmd.write("QUIT\n")
        with open(tmpCmd, 'r') as cmd:        
            xpress = subprocess.Popen(
                [self.path, lp.name],
                shell=True,
                stdin=cmd,
                universal_newlines=True,
            )

            if xpress.wait() != 0:
                raise PulpSolverError("PuLP: Error while executing " + self.path)
        values, attrs = self.readsol(tmpSol, tmpAttr)
        self.delete_tmp_files(tmpLp, tmpSol, tmpCmd, tmpAttr)
        status = statusmap.get(attrs.get(statuskey, -1),
                               constants.LpStatusUndefined)
        lp.assignVarsVals(values)
        lp.assignStatus(status)
        return status

    @staticmethod
    def readsol(filename, attrfile):
        """Read an XPRESS solution file"""
        with open(filename) as f:
            for i in range(6):
                f.readline()
            _line = f.readline().split()

            rows = int(_line[2])
            cols = int(_line[5])
            for i in range(3):
                f.readline()
            statusString = f.readline().split()[0]
            values = {}
            while 1:
                _line = f.readline()
                if _line == "":
                    break
                line = _line.split()
                if len(line) and line[0] == "C":
                    name = line[2]
                    value = float(line[4])
                    values[name] = value
        # Read the attributes that we wrote explicitly
        attrs = dict()
        with open(attrfile) as f:
            for line in f:
                fields = line.strip().split('=')
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
        return values, attrs

    @staticmethod
    def writeslxsol(name, *values):
        """
        Write a solution file in SLX format.

        :param string name: file name
        :param list values: list of lists of (name,value) pairs
        """
        with open(name, 'w') as slx:
            for i, sol in enumerate(values):
                slx.write("NAME solution%d\n" % i)
                for name, value in sol:
                    slx.write(' C      %s %.16f\n' % (name, value))
            slx.write('ENDATA\n')
