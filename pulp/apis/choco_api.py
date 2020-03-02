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
from .core import pulp_choco_path
import os
from uuid import uuid4
from .. import constants
import warnings

class CHOCO_CMD(LpSolver_CMD):
    """The CHOCO_CMD solver"""

    def defaultPath(self):
        raise PulpSolverError("PuLP: default path does not exist por CHOCO_CMD")
        # return self.executableExtension("choco-parsers-4.0.5-SNAPSHOT-with-dependencies.jar")

    def available(self):
        """True if the solver is available"""
        java_path = self.executableExtension('java')
        return self.executable(self.path) and self.executable(java_path)

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        java_path = self.executableExtension('java')
        if not self.executable(java_path):
            raise PulpSolverError("PuLP: java needs to be installed and accesible in order to use CHOCO_CMD")
        if not os.path.exists(self.path):
            raise PulpSolverError("PuLP: cannot execute "+self.path)
        if not self.keepFiles:
            uuid = uuid4().hex
            tmpLp = os.path.join(self.tmpDir, "%s-pulp.lp" % uuid)
            tmpMps = os.path.join(self.tmpDir, "%s-pulp.mps" % uuid)
            tmpSol = os.path.join(self.tmpDir, "%s-pulp.sol" % uuid)
        else:
            tmpLp = lp.name + "-pulp.lp"
            tmpMps = lp.name+"-pulp.mps"
            tmpSol = lp.name+"-pulp.sol"
        # just to report duplicated variables:
        lp.checkDuplicateVars()

        lp.writeMPS(tmpMps, mpsSense=lp.sense)
        try:
            os.remove(tmpSol)
        except:
            pass
        cmd = java_path + ' -cp ' + self.path + ' org.chocosolver.parser.mps.ChocoMPS'
        cmd += ' ' + ' '.join(['%s %s' % (key, value)
                               for key, value in self.options])
        cmd += ' %s' % tmpMps
        if lp.sense == constants.LpMaximize:
            cmd += ' -max'
        if lp.isMIP():
            if not self.mip:
                warnings.warn("CHOCO_CMD cannot solve the relaxation of a problem")
        # we always get the output to a file.
        # if not, we cannot read it afterwards
        # (we thus ignore the self.msg parameter)
        pipe = open(tmpSol, 'w')

        return_code = subprocess.call(cmd.split(), stdout=pipe, stderr=pipe)

        if return_code != 0:
            raise PulpSolverError("PuLP: Error while trying to execute "+self.path)
        if not self.keepFiles:
            try:
                os.remove(tmpMps)
                os.remove(tmpLp)
            except:
                pass
        if not os.path.exists(tmpSol):
            status = constants.LpStatusNotSolved
            status_sol = constants.LpSolutionNoSolutionFound
            values = None
        else:
            status, values, status_sol = self.readsol(tmpSol)
        if not self.keepFiles:
            try:
                os.remove(tmpSol)
            except:
                pass

        lp.assignStatus(status, status_sol)
        if status not in [constants.LpStatusInfeasible, constants.LpStatusNotSolved]:
            lp.assignVarsVals(values)

        return status

    @staticmethod
    def readsol(filename):
        """Read a Choco solution file"""
        # TODO: figure out the unbounded status in choco solver
        chocoStatus = {'OPTIMUM FOUND': constants.LpStatusOptimal,
                       'SATISFIABLE': constants.LpStatusOptimal,
                       'UNSATISFIABLE': constants.LpStatusInfeasible,
                       'UNKNOWN': constants.LpStatusNotSolved}

        chocoSolStatus = {'OPTIMUM FOUND': constants.LpSolutionOptimal,
                          'SATISFIABLE': constants.LpSolutionIntegerFeasible,
                          'UNSATISFIABLE': constants.LpSolutionInfeasible,
                          'UNKNOWN': constants.LpSolutionNoSolutionFound}

        status = constants.LpStatusNotSolved
        sol_status = constants.LpSolutionNoSolutionFound
        values = {}
        with open(filename) as f:
            content = f.readlines()
        content = [l.strip() for l in content if l[:2] not in ['o ', 'c ']]
        if not len(content):
            return status, values, sol_status
        if content[0][:2] == 's ':
            status_str = content[0][2:]
            status = chocoStatus[status_str]
            sol_status = chocoSolStatus[status_str]
        for line in content[1:]:
            name, value = line.split()
            values[name] = float(value)

        return status, values, sol_status


class PULP_CHOCO_CMD(CHOCO_CMD):
    """
    This solver uses a packaged version of choco provided with the package
    """
    pulp_choco_path = pulp_choco_path
    try:
        if os.name != 'nt':
            if not os.access(pulp_choco_path, os.X_OK):
                import stat
                os.chmod(pulp_choco_path, stat.S_IXUSR + stat.S_IXOTH)
    except:  # probably due to incorrect permissions

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp, callback=None):
            """Solve a well formulated lp problem"""
            raise PulpSolverError("PULP_CHOCO_CMD: Not Available (check permissions on %s)" % self.pulp_choco_path)
    else:
        def __init__(self, path=None, *args, **kwargs):
            """
            just loads up CHOCO_CMD with the path set
            """
            if path is not None:
                raise PulpSolverError('Use CHOCO_CMD if you want to set a path')
            # check that the file is executable
            CHOCO_CMD.__init__(self, path=self.pulp_choco_path, *args, **kwargs)
