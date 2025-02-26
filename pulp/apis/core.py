# PuLP : Python LP Modeler
# Version 1.4.2
from __future__ import annotations

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
import platform
import shutil
import sys
import ctypes
from typing import Any, TYPE_CHECKING, Sequence

import configparser

Parser = configparser.ConfigParser

from .. import sparse
from .. import constants as const

import logging

try:
    import ujson as json
except ImportError:
    import json

log = logging.getLogger(__name__)

import subprocess

devnull = subprocess.DEVNULL

from uuid import uuid4

if TYPE_CHECKING:
    from pulp.pulp import LpProblem
    from _typeshed import StrOrBytesPath


class PulpSolverError(const.PulpError):
    """
    Pulp Solver-related exceptions
    """

    pass


# import configuration information
def initialize(filename: str, operating_system: str = "linux", arch: str = "64"):
    """reads the configuration file to initialise the module"""
    here = os.path.dirname(filename)
    config = Parser({"here": here, "os": operating_system, "arch": arch})
    config.read(filename)

    try:
        cplex_dll_path = config.get("locations", "CplexPath")
    except configparser.Error:
        cplex_dll_path = "libcplex110.so"
    try:
        ilm_cplex_license = config.get("licenses", "ilm_cplex_license").replace('"', "")
    except configparser.Error:
        ilm_cplex_license = ""
    try:
        ilm_cplex_license_signature = config.getint(
            "licenses", "ilm_cplex_license_signature"
        )
    except configparser.Error:
        ilm_cplex_license_signature = 0
    try:
        coinMP_path = config.get("locations", "CoinMPPath").split(", ")
    except configparser.Error:
        coinMP_path = ["libCoinMP.so"]
    try:
        gurobi_path = config.get("locations", "GurobiPath")
    except configparser.Error:
        gurobi_path = "/opt/gurobi201/linux32/lib/python2.5"
    try:
        cbc_path = config.get("locations", "CbcPath")
    except configparser.Error:
        cbc_path = "cbc"
    try:
        glpk_path = config.get("locations", "GlpkPath")
    except configparser.Error:
        glpk_path = "glpsol"
    try:
        pulp_cbc_path = config.get("locations", "PulpCbcPath")
    except configparser.Error:
        pulp_cbc_path = "cbc"
    try:
        scip_path = config.get("locations", "ScipPath")
    except configparser.Error:
        scip_path = "scip"
    try:
        fscip_path = config.get("locations", "FscipPath")
    except configparser.Error:
        fscip_path = "fscip"
    for i, path in enumerate(coinMP_path):
        if not os.path.dirname(path):
            # if no pathname is supplied assume the file is in the same directory
            coinMP_path[i] = os.path.join(os.path.dirname(config_filename), path)
    return (
        cplex_dll_path,
        ilm_cplex_license,
        ilm_cplex_license_signature,
        coinMP_path,
        gurobi_path,
        cbc_path,
        glpk_path,
        pulp_cbc_path,
        scip_path,
        fscip_path,
    )


# pick up the correct config file depending on operating system
is_64bits = sys.maxsize > 2**32
if is_64bits:
    arch = "64"
    if platform.machine().lower() in ["aarch64", "arm64"]:
        arch = "arm64"
else:
    arch = "32"
if sys.platform in ["win32", "cli"]:
    operating_system = "win"
    PULPCFGFILE = "pulp.cfg.win"
elif sys.platform in ["darwin"]:
    operating_system = "osx"
    PULPCFGFILE = "pulp.cfg.osx"
else:
    operating_system = "linux"
    PULPCFGFILE = "pulp.cfg.linux"

DIRNAME = os.path.dirname(__file__)
config_filename = os.path.normpath(os.path.join(DIRNAME, "..", PULPCFGFILE))
(
    cplex_dll_path,
    ilm_cplex_license,
    ilm_cplex_license_signature,
    coinMP_path,
    gurobi_path,
    cbc_path,
    glpk_path,
    pulp_cbc_path,
    scip_path,
    fscip_path,
) = initialize(config_filename, operating_system, arch)


class LpSolver:
    """A generic LP Solver"""

    name = "LpSolver"

    def __init__(
        self,
        mip: bool = True,
        msg: bool = True,
        options: list[str] | None = None,
        timeLimit: float | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param list options:
        :param float timeLimit: maximum time for solver (in seconds)
        :param args:
        :param kwargs: optional named options to pass to each solver,
                        e.g. gapRel=0.1, gapAbs=10, logPath="",
        """
        if options is None:
            options = []
        self.mip = mip
        self.msg = msg
        self.options = options
        self.timeLimit = timeLimit

        # here we will store all other relevant information including:
        # gapRel, gapAbs, maxMemory, maxNodes, threads, logPath, timeMode
        self.optionsDict = {k: v for k, v in kwargs.items() if v is not None}

    def available(self) -> bool:
        """True if the solver is available"""
        raise NotImplementedError()

    def actualSolve(self, lp: LpProblem) -> int:
        """Solve a well formulated lp problem"""
        raise NotImplementedError()

    def actualResolve(self, lp: LpProblem, **kwargs: Any):
        """
        uses existing problem information and solves the problem
        If it is not implemented in the solver
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

    def solve(self, lp: LpProblem):
        """Solve the problem lp"""
        # Always go through the solve method of LpProblem
        return lp.solve(self)

    # TODO: Not sure if this code should be here or in a child class
    def getCplexStyleArrays(
        self,
        lp: LpProblem,
        senseDict: dict[int, str] | None = None,
        LpVarCategories: dict[str, str] | None = None,
        LpObjSenses: dict[int, int] | None = None,
        infBound: float = 1e20,
    ):
        """returns the arrays suitable to pass to a cdll Cplex
        or other solvers that are similar

        Copyright (c) Stuart Mitchell 2007
        """
        if senseDict is None:
            senseDict = {
                const.LpConstraintEQ: "E",
                const.LpConstraintLE: "L",
                const.LpConstraintGE: "G",
            }
        if LpVarCategories is None:
            LpVarCategories = {const.LpContinuous: "C", const.LpInteger: "I"}
        if LpObjSenses is None:
            LpObjSenses = {const.LpMaximize: -1, const.LpMinimize: 1}
        if lp.objective is None:
            raise const.PulpError("Objective has not been set")

        import ctypes

        rangeCount = 0
        variables = list(lp.variables())
        numVars = len(variables)
        # associate each variable with a ordinal
        self.v2n = {variables[i]: i for i in range(numVars)}
        self.vname2n = {variables[i].name: i for i in range(numVars)}
        self.n2v = {i: variables[i] for i in range(numVars)}
        # objective values
        objSense = LpObjSenses[lp.sense]
        NumVarDoubleArray = ctypes.c_double * numVars
        objectCoeffs = NumVarDoubleArray()
        # print "Get objective Values"
        for v, val in lp.objective.items():
            objectCoeffs[self.v2n[v]] = val
        # values for variables
        objectConst = ctypes.c_double(0.0)
        NumVarStrArray = ctypes.c_char_p * numVars
        colNames = NumVarStrArray()
        lowerBounds = NumVarDoubleArray()
        upperBounds = NumVarDoubleArray()
        initValues = NumVarDoubleArray()
        for v in lp.variables():
            colNames[self.v2n[v]] = v.name.encode("utf-8")
            initValues[self.v2n[v]] = 0.0
            if v.lowBound != None:
                lowerBounds[self.v2n[v]] = v.lowBound
            else:
                lowerBounds[self.v2n[v]] = -infBound
            if v.upBound != None:
                upperBounds[self.v2n[v]] = v.upBound
            else:
                upperBounds[self.v2n[v]] = infBound
        # values for constraints
        numRows = len(lp.constraints)
        NumRowDoubleArray = ctypes.c_double * numRows
        NumRowStrArray = ctypes.c_char_p * numRows
        NumRowCharArray = ctypes.c_char * numRows
        rhsValues = NumRowDoubleArray()
        rangeValues = NumRowDoubleArray()
        rowNames = NumRowStrArray()
        rowType = NumRowCharArray()
        self.c2n: dict[str, int] = {}
        self.n2c: dict[int, str] = {}
        i = 0
        for c in lp.constraints:
            rhsValues[i] = -lp.constraints[c].constant
            # for ranged constraints a<= constraint >=b
            rangeValues[i] = 0.0
            rowNames[i] = c.encode("utf-8")
            rowType[i] = senseDict[lp.constraints[c].sense].encode("utf-8")
            self.c2n[c] = i
            self.n2c[i] = c
            i = i + 1
        # return the coefficient matrix as a series of vectors
        coeffs = lp.coefficients()
        sparseMatrix = sparse.Matrix(list(range(numRows)), list(range(numVars)))
        for var, row, coeff in coeffs:
            sparseMatrix.add(self.c2n[row], self.vname2n[var], coeff)
        (
            numels,
            mystartsBase,
            mylenBase,
            myindBase,
            myelemBase,
        ) = sparseMatrix.col_based_arrays()
        elemBase = ctypesArrayFill(myelemBase, ctypes.c_double)
        indBase = ctypesArrayFill(myindBase, ctypes.c_int)
        startsBase = ctypesArrayFill(mystartsBase, ctypes.c_int)
        lenBase = ctypesArrayFill(mylenBase, ctypes.c_int)
        # MIP Variables
        NumVarCharArray = ctypes.c_char * numVars
        columnType = NumVarCharArray()
        if lp.isMIP():
            for v in lp.variables():
                columnType[self.v2n[v]] = LpVarCategories[v.cat].encode("utf-8")
        self.addedVars = numVars
        self.addedRows = numRows
        return (
            numVars,
            numRows,
            numels,
            rangeCount,
            objSense,
            objectCoeffs,
            objectConst,
            rhsValues,
            rangeValues,
            rowType,
            startsBase,
            lenBase,
            indBase,
            elemBase,
            lowerBounds,
            upperBounds,
            initValues,
            colNames,
            rowNames,
            columnType,
            self.n2v,
            self.n2c,
        )

    def toDict(self):
        data = dict(solver=self.name)
        for k in ["mip", "msg", "keepFiles"]:
            try:
                data[k] = getattr(self, k)
            except AttributeError:
                pass
        for k in ["timeLimit", "options"]:
            # with these ones, we only export if it has some content:
            try:
                value = getattr(self, k)
                if value:
                    data[k] = value
            except AttributeError:
                pass
        data.update(self.optionsDict)
        return data

    to_dict = toDict

    def toJson(self, filename: str, *args: Any, **kwargs: Any):
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    to_json = toJson


class LpSolver_CMD(LpSolver):
    """A generic command line LP Solver"""

    name = "LpSolver_CMD"

    def __init__(
        self,
        path: str | None = None,
        keepFiles: bool = False,
        *args: Any,
        **kwargs: Any,
    ):
        """

        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param list options: list of additional options to pass to solver (format depends on the solver)
        :param float timeLimit: maximum time for solver (in seconds)
        :param str path: a path to the solver binary
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param args: parameters to pass to :py:class:`LpSolver`
        :param kwargs: parameters to pass to :py:class:`LpSolver`
        """
        super().__init__(*args, **kwargs)
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
        if os.name != "nt":
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

    def create_tmp_files(self, name: str, *args: Any):
        if self.keepFiles:
            prefix = name
        else:
            prefix = os.path.join(self.tmpDir, uuid4().hex)
        return (f"{prefix}-pulp.{n}" for n in args)

    def silent_remove(self, file: StrOrBytesPath):
        try:
            os.remove(file)
        except FileNotFoundError:
            pass

    def delete_tmp_files(self, *args: Any):
        if self.keepFiles:
            return
        for file in args:
            self.silent_remove(file)

    def defaultPath(self) -> str:
        raise NotImplementedError()

    @staticmethod
    def executableExtension(name: str):
        if os.name != "nt":
            return name
        else:
            return name + ".exe"

    @staticmethod
    def executable(command: str) -> str | None:
        """Checks that the solver command is executable,
        And returns the actual path to it."""
        return shutil.which(command)


def ctypesArrayFill(myList: Sequence, type=ctypes.c_double) -> ctypes.Array:
    """
    Creates a c array with ctypes from a python list
    type is the type of the c array
    """
    ctype = type * len(myList)
    cList = ctype()
    for i, elem in enumerate(myList):
        cList[i] = elem
    return cList
