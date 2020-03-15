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
import os
from uuid import uuid4
from .. import constants


class XPRESS(LpSolver_CMD):
    """The XPRESS LP solver"""
    def __init__(self, path=None, keepFiles=0, mip=1,
            msg=0, maxSeconds=None, targetGap=None, heurFreq=None,
            heurStra=None, coverCuts=None, preSolve=None,
            options=None):
        """
        Initializes the Xpress solver.

        @param maxSeconds: the maximum time that the Optimizer will run before it terminates
        @param targetGap: global search will terminate if:
                          abs(MIPOBJVAL - BESTBOUND) <= MIPRELSTOP * BESTBOUND
        @param heurFreq: the frequency at which heuristics are used in the tree search
        @param heurStra: heuristic strategy
        @param coverCuts: the number of rounds of lifted cover inequalities at the top node
        @param preSolve: whether presolving should be performed before the main algorithm
        @param options: Adding more options, e.g. options = ["NODESELECTION=1", "HEURDEPTH=5"]
                        More about Xpress options and control parameters please see
                        http://tomopt.com/docs/xpress/tomlab_xpress008.php
        """
        LpSolver_CMD.__init__(self, path, keepFiles, mip, msg, options)
        self.maxSeconds = maxSeconds
        self.targetGap = targetGap
        self.heurFreq = heurFreq
        self.heurStra = heurStra
        self.coverCuts = coverCuts
        self.preSolve = preSolve

    def defaultPath(self):
        return self.executableExtension("optimizer")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute "+self.path)
        if not self.keepFiles:
            uuid = uuid4().hex
            tmpLp = os.path.join(self.tmpDir, "%s-pulp.lp" % uuid)
            tmpSol = os.path.join(self.tmpDir, "%s-pulp.prt" % uuid)
        else:
            tmpLp = lp.name+"-pulp.lp"
            tmpSol = lp.name+"-pulp.prt"
        lp.writeLP(tmpLp, writeSOS=1, mip=self.mip)
        xpress = subprocess.Popen([self.path, lp.name], shell=True, stdin=subprocess.PIPE, universal_newlines=True)
        if not self.msg:
            xpress.stdin.write("OUTPUTLOG=0\n")
        xpress.stdin.write("READPROB "+tmpLp+"\n")
        if self.maxSeconds:
            xpress.stdin.write("MAXTIME=%d\n" % self.maxSeconds)
        if self.targetGap:
            xpress.stdin.write("MIPRELSTOP=%f\n" % self.targetGap)
        if self.heurFreq:
            xpress.stdin.write("HEURFREQ=%d\n" % self.heurFreq)
        if self.heurStra:
            xpress.stdin.write("HEURSTRATEGY=%d\n" % self.heurStra)
        if self.coverCuts:
            xpress.stdin.write("COVERCUTS=%d\n" % self.coverCuts)
        if self.preSolve:
            xpress.stdin.write("PRESOLVE=%d\n" % self.preSolve)
        for option in self.options:
            xpress.stdin.write(option+"\n")
        if lp.sense == constants.LpMaximize:
            xpress.stdin.write("MAXIM\n")
        else:
            xpress.stdin.write("MINIM\n")
        if lp.isMIP() and self.mip:
            xpress.stdin.write("GLOBAL\n")
        xpress.stdin.write("WRITEPRTSOL "+tmpSol+"\n")
        xpress.stdin.write("QUIT\n")
        if xpress.wait() != 0:
            raise PulpSolverError("PuLP: Error while executing "+self.path)
        status, values = self.readsol(tmpSol)
        if not self.keepFiles:
            for f in [tmpLp, tmpSol]:
                try:
                    os.remove(f)
                except:
                    pass
        lp.assignVarsVals(values)
        if abs(lp.infeasibilityGap(self.mip)) > 1e-5:  # Arbitrary
            status = constants.LpStatusInfeasible
        lp.assignStatus(status)
        return status

    @staticmethod
    def readsol(filename):
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
            # TODO: check status for Integer Feasible
            xpressStatus = {
                "Optimal": constants.LpStatusOptimal,
                }
            if statusString not in xpressStatus:
                raise PulpSolverError("Unknown status returned by XPRESS: "+statusString)
            status = xpressStatus[statusString]
            values = {}
            while 1:
                _line = f.readline()
                if _line == "":
                    break
                line = _line.split()
                if len(line) and line[0] == 'C':
                    name = line[2]
                    value = float(line[4])
                    values[name] = value
        return status, values
