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

from .core import LpSolver_CMD, subprocess, PulpSolverError, clock
from .core import scip_path
import os
from uuid import uuid4
from .. import constants
import sys


class SCIP_CMD(LpSolver_CMD):
    """The SCIP optimization solver"""

    SCIP_STATUSES = {
        'unknown': constants.LpStatusUndefined,
        'user interrupt': constants.LpStatusNotSolved,
        'node limit reached': constants.LpStatusNotSolved,
        'total node limit reached': constants.LpStatusNotSolved,
        'stall node limit reached': constants.LpStatusNotSolved,
        'time limit reached': constants.LpStatusNotSolved,
        'memory limit reached': constants.LpStatusNotSolved,
        'gap limit reached': constants.LpStatusNotSolved,
        'solution limit reached': constants.LpStatusNotSolved,
        'solution improvement limit reached': constants.LpStatusNotSolved,
        'restart limit reached': constants.LpStatusNotSolved,
        'optimal solution found': constants.LpStatusOptimal,
        'infeasible':   constants.LpStatusInfeasible,
        'unbounded': constants.LpStatusUnbounded,
        'infeasible or unbounded': constants.LpStatusNotSolved,
    }

    def defaultPath(self):
        return self.executableExtension(scip_path)

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute "+self.path)

        # TODO: should we use tempfile instead?
        if not self.keepFiles:
            uuid = uuid4().hex
            tmpLp = os.path.join(self.tmpDir, "%s-pulp.lp" % uuid)
            tmpSol = os.path.join(self.tmpDir, "%s-pulp.sol" % uuid)
        else:
            tmpLp = lp.name + "-pulp.lp"
            tmpSol = lp.name + "-pulp.sol"

        lp.writeLP(tmpLp)
        proc = [
            'scip', '-c', 'read "%s"' % tmpLp, '-c', 'optimize',
            '-c', 'write solution "%s"' % tmpSol, '-c', 'quit'
        ]
        proc.extend(self.options)
        if not self.msg:
            proc.append('-q')

        self.solution_time = clock()
        subprocess.check_call(proc, stdout=sys.stdout, stderr=sys.stderr)
        self.solution_time += clock()

        if not os.path.exists(tmpSol):
            raise PulpSolverError("PuLP: Error while executing "+self.path)

        status, values = self.readsol(tmpSol)

        # Make sure to add back in any 0-valued variables SCIP leaves out.
        finalVals = {}
        for v in lp.variables():
            finalVals[v.name] = values.get(v.name, 0.0)

        lp.assignVarsVals(finalVals)
        lp.assignStatus(status)

        if not self.keepFiles:
            for f in (tmpLp, tmpSol):
                try:
                    os.remove(f)
                except:
                    pass

        return status

    @staticmethod
    def readsol(filename):
        """Read a SCIP solution file"""
        with open(filename) as f:
            # First line must containt 'solution status: <something>'
            try:
                line = f.readline()
                comps = line.split(': ')
                assert comps[0] == 'solution status'
                assert len(comps) == 2
            except:
                raise PulpSolverError("Can't read SCIP solver output: %r" % line)

            status = SCIP_CMD.SCIP_STATUSES.get(comps[1].strip(), constants.LpStatusUndefined)

            # Look for an objective value. If we can't find one, stop.
            try:
                line = f.readline()
                comps = line.split(': ')
                assert comps[0] == 'objective value'
                assert len(comps) == 2
                float(comps[1].strip())
            except:
                raise PulpSolverError("Can't read SCIP solver output: %r" % line)

            # Parse the variable values.
            values = {}
            for line in f:
                try:
                    comps = line.split()
                    values[comps[0]] = float(comps[1])
                except:
                    raise PulpSolverError("Can't read SCIP solver output: %r" % line)

        return status, values


SCIP = SCIP_CMD
