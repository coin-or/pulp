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

"""
This file contains the solver classes for PuLP
Note that the solvers that require a compiled extension may not work in
the current version
"""

import os
import sys
try:
    from time import process_time as clock
except ImportError:
    from time import clock

try:
    import configparser
except ImportError:
    import ConfigParser as configparser
try:
    Parser = configparser.ConfigParser
except AttributeError:
    Parser = configparser.SafeConfigParser    
from .. import sparse
from .. import constants as const

import logging
log = logging.getLogger(__name__)

if os.name == "posix" and sys.version_info[0] < 3:
    try:
        import subprocess32 as subprocess
    except ImportError:
        log.debug("Thread-safe subprocess32 module not found! "
                  "Using unsafe built-in subprocess module instead.")
        import subprocess
else:
    import subprocess

if sys.version_info[0] < 3:
    devnull = open(os.devnull, 'wb')
else:
    devnull = subprocess.DEVNULL


class PulpSolverError(const.PulpError):
    """
    Pulp Solver-related exceptions
    """
    pass

#import configuration information
def initialize(filename, operating_system='linux', arch='64'):
    """ reads the configuration file to initialise the module"""
    here = os.path.dirname(filename)
    config = Parser({'here':here,
        'os':operating_system, 'arch':arch})
    config.read(filename)

    try:
        cplex_dll_path = config.get("locations", "CplexPath")
    except configparser.Error:
        cplex_dll_path = 'libcplex110.so'
    try:
        try:
            ilm_cplex_license = config.get("licenses",
                "ilm_cplex_license").decode("string-escape").replace('"','')
        except AttributeError:
            ilm_cplex_license = config.get("licenses",
                "ilm_cplex_license").replace('"','')
    except configparser.Error:
        ilm_cplex_license = ''
    try:
        ilm_cplex_license_signature = config.getint("licenses",
                "ilm_cplex_license_signature")
    except configparser.Error:
        ilm_cplex_license_signature = 0
    try:
        coinMP_path = config.get("locations", "CoinMPPath").split(', ')
    except configparser.Error:
        coinMP_path = ['libCoinMP.so']
    try:
        gurobi_path = config.get("locations", "GurobiPath")
    except configparser.Error:
        gurobi_path = '/opt/gurobi201/linux32/lib/python2.5'
    try:
        cbc_path = config.get("locations", "CbcPath")
    except configparser.Error:
        cbc_path = 'cbc'
    try:
        glpk_path = config.get("locations", "GlpkPath")
    except configparser.Error:
        glpk_path = 'glpsol'
    try:
        pulp_cbc_path = config.get("locations", "PulpCbcPath")
    except configparser.Error:
        pulp_cbc_path = 'cbc'
    try:
        scip_path = config.get("locations", "ScipPath")
    except configparser.Error:
        scip_path = 'scip'
    try:
        pulp_choco_path = config.get("locations", "PulpChocoPath")
    except configparser.Error:
        pulp_choco_path = 'choco'
    for i,path in enumerate(coinMP_path):
        if not os.path.dirname(path):
            #if no pathname is supplied assume the file is in the same directory
            coinMP_path[i] = os.path.join(os.path.dirname(config_filename),path)
    return cplex_dll_path, ilm_cplex_license, ilm_cplex_license_signature,\
        coinMP_path, gurobi_path, cbc_path, glpk_path, pulp_cbc_path, scip_path, pulp_choco_path

#pick up the correct config file depending on operating system
PULPCFGFILE = "pulp.cfg"
is_64bits = sys.maxsize > 2**32
if is_64bits:
    arch = '64'
else:
    arch = '32'
operating_system = None
if sys.platform in ['win32', 'cli']:
    operating_system = 'win'
    PULPCFGFILE += ".win"
elif sys.platform in ['darwin']:
    operating_system = "osx"
    arch = '64'
    PULPCFGFILE += ".osx"
else:
    operating_system = "linux"
    PULPCFGFILE += ".linux"

DIRNAME = os.path.dirname(__file__)
config_filename = os.path.join(DIRNAME, "..", PULPCFGFILE)
cplex_dll_path, ilm_cplex_license, ilm_cplex_license_signature, coinMP_path,\
        gurobi_path, cbc_path, glpk_path, pulp_cbc_path, scip_path, pulp_choco_path = \
        initialize(config_filename, operating_system, arch)


# See later for LpSolverDefault definition
class LpSolver:
    """A generic LP Solver"""

    def __init__(self, mip = True, msg = True, options = None, mip_start=False, *args, **kwargs):
        if options is None:
            options = []
        self.mip = mip
        self.msg = msg
        self.options = options
        self.mip_start = mip_start

    def available(self):
        """True if the solver is available"""
        raise NotImplementedError

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        raise NotImplementedError

    def actualResolve(self, lp, **kwargs):
        """
        uses existing problem information and solves the problem
        If it is not implelemented in the solver
        just solve again
        """
        self.actualSolve(lp, **kwargs)

    def copy(self):
        """Make a copy of self"""

        aCopy = self.__class__()
        aCopy.mip = self.mip
        aCopy.msg = self.msg
        aCopy.options = self.options
        return aCopy

    def solve(self, lp):
        """Solve the problem lp"""
        # Always go through the solve method of LpProblem
        return lp.solve(self)

    #TODO: Not sure if this code should be here or in a child class
    def getCplexStyleArrays(self,lp, senseDict=None, LpVarCategories=None, LpObjSenses=None, infBound=1e20):
        """returns the arrays suitable to pass to a cdll Cplex
        or other solvers that are similar

        Copyright (c) Stuart Mitchell 2007
        """
        if senseDict is None:
            senseDict = {const.LpConstraintEQ: "E", const.LpConstraintLE: "L", const.LpConstraintGE: "G"}
        if LpVarCategories is None:
            LpVarCategories = {const.LpContinuous: "C", const.LpInteger: "I"}
        if LpObjSenses is None:
            LpObjSenses = {const.LpMaximize: -1, const.LpMinimize: 1}

        import ctypes
        rangeCount = 0
        variables=list(lp.variables())
        numVars = len(variables)
        #associate each variable with a ordinal
        self.v2n=dict(((variables[i],i) for i in range(numVars)))
        self.vname2n=dict(((variables[i].name,i) for i in range(numVars)))
        self.n2v=dict((i,variables[i]) for i in range(numVars))
        #objective values
        objSense = LpObjSenses[lp.sense]
        NumVarDoubleArray = ctypes.c_double * numVars
        objectCoeffs=NumVarDoubleArray()
        #print "Get objective Values"
        for v,val in lp.objective.items():
            objectCoeffs[self.v2n[v]]=val
        #values for variables
        objectConst = ctypes.c_double(0.0)
        NumVarStrArray = ctypes.c_char_p * numVars
        colNames = NumVarStrArray()
        lowerBounds = NumVarDoubleArray()
        upperBounds = NumVarDoubleArray()
        initValues = NumVarDoubleArray()
        for v in lp.variables():
            colNames[self.v2n[v]] = str(v.name)
            initValues[self.v2n[v]] = 0.0
            if v.lowBound != None:
                lowerBounds[self.v2n[v]] = v.lowBound
            else:
                lowerBounds[self.v2n[v]] = -infBound
            if v.upBound != None:
                upperBounds[self.v2n[v]] = v.upBound
            else:
                upperBounds[self.v2n[v]] = infBound
        #values for constraints
        numRows =len(lp.constraints)
        NumRowDoubleArray = ctypes.c_double * numRows
        NumRowStrArray = ctypes.c_char_p * numRows
        NumRowCharArray = ctypes.c_char * numRows
        rhsValues = NumRowDoubleArray()
        rangeValues = NumRowDoubleArray()
        rowNames = NumRowStrArray()
        rowType = NumRowCharArray()
        self.c2n = {}
        self.n2c = {}
        i = 0
        for c in lp.constraints:
            rhsValues[i] = -lp.constraints[c].constant
            #for ranged constraints a<= constraint >=b
            rangeValues[i] = 0.0
            rowNames[i] = str(c)
            rowType[i] = senseDict[lp.constraints[c].sense]
            self.c2n[c] = i
            self.n2c[i] = c
            i = i+1
        #return the coefficient matrix as a series of vectors
        coeffs = lp.coefficients()
        sparseMatrix = sparse.Matrix(list(range(numRows)), list(range(numVars)))
        for var,row,coeff in coeffs:
            sparseMatrix.add(self.c2n[row], self.vname2n[var], coeff)
        (numels, mystartsBase, mylenBase, myindBase,
         myelemBase) = sparseMatrix.col_based_arrays()
        elemBase = ctypesArrayFill(myelemBase, ctypes.c_double)
        indBase = ctypesArrayFill(myindBase, ctypes.c_int)
        startsBase = ctypesArrayFill(mystartsBase, ctypes.c_int)
        lenBase = ctypesArrayFill(mylenBase, ctypes.c_int)
        #MIP Variables
        NumVarCharArray = ctypes.c_char * numVars
        columnType = NumVarCharArray()
        if lp.isMIP():
            for v in lp.variables():
                columnType[self.v2n[v]] = LpVarCategories[v.cat]
        self.addedVars = numVars
        self.addedRows = numRows
        return  (numVars, numRows, numels, rangeCount,
            objSense, objectCoeffs, objectConst,
            rhsValues, rangeValues, rowType, startsBase, lenBase, indBase,
            elemBase, lowerBounds, upperBounds, initValues, colNames,
            rowNames, columnType, self.n2v, self.n2c)


class LpSolver_CMD(LpSolver):
    """A generic command line LP Solver"""
    # TODO: make a general naming function for file names dictionary.
        # .lp, .mip, .sol, .mst, etc.
    # TODO: also handle the deletion of files afterwards

    def __init__(self, path=None, keepFiles=0, mip=1, msg=1, options=None, mip_start=False):
        LpSolver.__init__(self, mip=mip, msg=msg, options=options, mip_start=mip_start)
        if path is None:
            self.path = self.defaultPath()
        else:
            self.path = path
        self.keepFiles = keepFiles
        self.setTmpDir()

    def copy(self):
        """Make a copy of self"""

        aCopy = LpSolver.copy(self)
        aCopy.path = self.path
        aCopy.keepFiles = self.keepFiles
        aCopy.tmpDir = self.tmpDir
        return aCopy

    def setTmpDir(self):
        """Set the tmpDir attribute to a reasonnable location for a temporary
        directory"""
        if os.name != 'nt':
            # On unix use /tmp by default
            self.tmpDir = os.environ.get("TMPDIR", "/tmp")
            self.tmpDir = os.environ.get("TMP", self.tmpDir)
        else:
            # On Windows use the current directory
            self.tmpDir = os.environ.get("TMPDIR", "")
            self.tmpDir = os.environ.get("TMP", self.tmpDir)
            self.tmpDir = os.environ.get("TEMP", self.tmpDir)
        if not os.path.isdir(self.tmpDir):
            self.tmpDir = ""
        elif not os.access(self.tmpDir, os.F_OK + os.W_OK):
            self.tmpDir = ""

    def defaultPath(self):
        raise NotImplementedError

    def executableExtension(name):
        if os.name != 'nt':
            return name
        else:
            return name+".exe"
    executableExtension = staticmethod(executableExtension)

    def executable(command):
        """Checks that the solver command is executable,
        And returns the actual path to it."""

        if os.path.isabs(command):
            if os.path.exists(command) and os.access(command, os.X_OK):
                return command
        for path in os.environ.get("PATH", []).split(os.pathsep):
            new_path = os.path.join(path, command)
            if os.path.exists(new_path) and os.access(new_path, os.X_OK):
                return os.path.join(path, command)
        return False
    executable = staticmethod(executable)

try:
    import ctypes
    def ctypesArrayFill(myList, type=ctypes.c_double):
        """
        Creates a c array with ctypes from a python list
        type is the type of the c array
        """
        ctype= type * len(myList)
        cList = ctype()
        for i,elem in enumerate(myList):
            cList[i] = elem
        return cList
except(ImportError):
    def ctypesArrayFill(myList, type = None):
        return None