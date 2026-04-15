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

from __future__ import annotations

import ctypes
import math
import os
import platform
import shutil
import sys
from time import time


def clock() -> float:
    """Wall-clock seconds (for solver timing)."""
    return time()


def get_operating_system() -> str:
    if sys.platform in ["win32", "cli"]:
        return "win"
    if sys.platform in ["darwin"]:
        return "osx"
    return "linux"


def get_arch() -> str:
    is_64bits = sys.maxsize > 2**32
    if is_64bits:
        if platform.machine().lower() in ["aarch64", "arm64"]:
            return "arm64"
        return "i64"
    return "i32"


operating_system = get_operating_system()
arch = get_arch()

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Union

from .. import constants as const
from .. import sparse

if TYPE_CHECKING:
    from ..pulp import LpProblem

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

log = logging.getLogger(__name__)

import subprocess

devnull = subprocess.DEVNULL


def to_string(_obj: Any) -> bytes:
    """Return UTF-8 bytes for ``str(_obj)`` (used for C API string arguments)."""
    return str(_obj).encode()


from uuid import uuid4


class PulpSolverError(const.PulpError):
    """
    Pulp Solver-related exceptions
    """

    pass


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
    ) -> None:
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
        raise NotImplementedError

    def actualSolve(self, lp: LpProblem, **kwargs: Any) -> int:
        """Solve a well formulated lp problem"""
        raise NotImplementedError

    def copy(self) -> LpSolver:
        """Make a copy of self"""

        aCopy = self.__class__()
        aCopy.mip = self.mip
        aCopy.msg = self.msg
        aCopy.options = self.options
        return aCopy

    def solve(self, lp: LpProblem) -> int:
        """Solve the problem lp"""
        return lp.solve(self)

    # TODO: Not sure if this code should be here or in a child class
    def getCplexStyleArrays(
        self,
        lp: LpProblem,
        senseDict: dict[int, str] | None = None,
        LpVarCategories: dict[str, str] | None = None,
        LpObjSenses: dict[int, int] | None = None,
        infBound: float = 1e20,
    ) -> tuple[Any, ...]:
        """Return arrays suitable for a CDLL CPLEX-style API or similar solvers.

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

        import ctypes

        rangeCount = 0

        variables = list(lp.exported_variables())
        numVars = len(variables)
        # associate each variable with an ordinal (key by name; variables are not hashable)
        self.vname2n = {variables[i].name: i for i in range(numVars)}
        self.v2n = self.vname2n  # alias for code that uses v2n[v.name]
        self.n2v = {i: variables[i] for i in range(numVars)}
        # objective values
        objSense = LpObjSenses[lp.sense]
        NumVarDoubleArray = ctypes.c_double * numVars
        objectCoeffs = NumVarDoubleArray()
        if lp.objective is not None:
            for v, val in lp.objective.items():
                objectCoeffs[self.vname2n[v.name]] = val
        # values for variables
        objectConst = ctypes.c_double(0.0)
        NumVarStrArray = ctypes.c_char_p * numVars
        colNames = NumVarStrArray()
        lowerBounds = NumVarDoubleArray()
        upperBounds = NumVarDoubleArray()
        initValues = NumVarDoubleArray()
        for v in variables:
            i = self.vname2n[v.name]
            colNames[i] = to_string(v.name)
            initValues[i] = 0.0
            if math.isfinite(v.lowBound):
                lowerBounds[i] = v.lowBound
            else:
                lowerBounds[i] = -infBound
            if math.isfinite(v.upBound):
                upperBounds[i] = v.upBound
            else:
                upperBounds[i] = infBound
        # values for constraints
        numRows = len(lp.constraints())
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
        for c in lp.constraints():
            rhsValues[i] = -c.constant
            # for ranged constraints a<= constraint >=b
            rangeValues[i] = 0.0
            rowNames[i] = to_string(c.name)
            rowType[i] = to_string(senseDict[c.sense])
            self.c2n[c.name] = i
            self.n2c[i] = c.name
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
            for v in variables:
                columnType[self.vname2n[v.name]] = to_string(LpVarCategories[v.cat])
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

    def toDict(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(solver=self.name)
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

    def toJson(self, filename: str, *args: Any, **kwargs: Any) -> None:
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
    ) -> None:
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
        LpSolver.__init__(self, *args, **kwargs)
        if path is None:
            self.path = self.defaultPath()
        else:
            self.path = path
        self.keepFiles = keepFiles
        self.setTmpDir()

    def copy(self) -> LpSolver_CMD:
        """Make a copy of self"""

        aCopy: LpSolver_CMD = self.__class__()
        aCopy.mip = self.mip
        aCopy.msg = self.msg
        aCopy.options = self.options
        aCopy.path = self.path
        aCopy.keepFiles = self.keepFiles
        aCopy.tmpDir = self.tmpDir
        return aCopy

    def setTmpDir(self) -> None:
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

    def create_tmp_files(self, name: str, *args: str) -> Iterator[str]:
        if self.keepFiles:
            prefix = name
        else:
            prefix = os.path.join(self.tmpDir, uuid4().hex)
        return (f"{prefix}-pulp.{n}" for n in args)

    def silent_remove(self, file: Union[str, bytes, os.PathLike]) -> None:
        try:
            os.remove(file)
        except FileNotFoundError:
            pass

    def delete_tmp_files(self, *args: str) -> None:
        if self.keepFiles:
            return
        for file in args:
            self.silent_remove(file)

    def defaultPath(self) -> str:
        raise NotImplementedError

    @staticmethod
    def executableExtension(name: str) -> str:
        if os.name != "nt":
            return name
        else:
            return name + ".exe"

    @staticmethod
    def executable(command: str) -> str | None:
        """Checks that the solver command is executable,
        And returns the actual path to it."""
        return shutil.which(command)

    def get_pipe(self) -> Any:
        if self.msg:
            return None
        return open(os.devnull, "w")


def ctypesArrayFill(myList: list[Any], type: Any = ctypes.c_double) -> Any:
    """
    Creates a c array with ctypes from a python list
    type is the type of the c array
    """
    ctype = type * len(myList)
    cList = ctype()
    for i, elem in enumerate(myList):
        cList[i] = elem
    return cList
