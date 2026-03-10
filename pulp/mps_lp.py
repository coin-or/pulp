"""

@author: Franco Peschiera

"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from . import _rustcore
from . import constants as const

if TYPE_CHECKING:
    from pulp.pulp import LpAffineExpression, LpProblem, LpVariable

CORE_FILE_ROW_MODE = "ROWS"
CORE_FILE_COL_MODE = "COLUMNS"
CORE_FILE_RHS_MODE = "RHS"
CORE_FILE_BOUNDS_MODE = "BOUNDS"

CORE_FILE_BOUNDS_MODE_NAME_GIVEN = "BOUNDS_NAME"
CORE_FILE_BOUNDS_MODE_NO_NAME = "BOUNDS_NO_NAME"
CORE_FILE_RHS_MODE_NAME_GIVEN = "RHS_NAME"
CORE_FILE_RHS_MODE_NO_NAME = "RHS_NO_NAME"

ROW_MODE_OBJ = "N"

ROW_EQUIV = {v: k for k, v in const.LpConstraintTypeToMps.items()}
COL_EQUIV = {1: "Integer", 0: "Continuous"}


def _safe_var_cat(variable: LpVariable) -> str:
    """Variable category; defaults to continuous if variable is from another model (e.g. after extend)."""
    try:
        return variable.cat
    except BaseException:
        return const.LpContinuous


def _safe_var_bounds(variable: LpVariable) -> tuple[float | None, float | None]:
    """(lowBound, upBound) with defaults if variable is from another model.
    Converts inf/-inf back to None for MPS/LP format compatibility."""
    try:
        lb = variable.lowBound
        ub = variable.upBound
        if lb is not None and not math.isfinite(lb):
            lb = None
        if ub is not None and not math.isfinite(ub):
            ub = None
        return (lb, ub)
    except BaseException:
        return (0, None)


@dataclass
class MPSParameters:
    name: str
    sense: int
    status: int
    sol_status: int

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPSParameters:
        return cls(
            str(data["name"]),
            int(data["sense"]),
            int(data["status"]),
            int(data["sol_status"]),
        )


@dataclass
class MPSCoefficient:
    name: str
    value: float

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPSCoefficient:
        return cls(data["name"], float(data["value"]))


@dataclass
class MPSObjective:
    name: str | None
    coefficients: list[MPSCoefficient]

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPSObjective:
        return cls(
            data["name"], [MPSCoefficient.fromDict(d) for d in data["coefficients"]]
        )


@dataclass
class MPSVariable:
    name: str
    cat: str
    lowBound: float | None = 0
    upBound: float | None = None
    varValue: float | None = None
    dj: float | None = None

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPSVariable:
        return cls(
            data["name"],
            data["cat"],
            data.get("lowBound", 0),
            data.get("upBound", None),
            data.get("varValue", None),
            data.get("dj", None),
        )


@dataclass
class MPSConstraint:
    name: str | None
    sense: int
    coefficients: list[MPSCoefficient]
    pi: float | None = None
    constant: float = 0

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPSConstraint:
        return cls(
            data.get("name", None),
            data["sense"],
            [MPSCoefficient.fromDict(d) for d in data["coefficients"]],
            data.get("pi", None),
            data.get("constant", 0),
        )


@dataclass
class MPS:
    parameters: MPSParameters
    objective: MPSObjective
    variables: list[MPSVariable]
    constraints: list[MPSConstraint]
    sos1: list[Any]
    sos2: list[Any]

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> MPS:
        return cls(
            MPSParameters.fromDict(data["parameters"]),
            MPSObjective.fromDict(data["objective"]),
            [MPSVariable.fromDict(d) for d in data["variables"]],
            [MPSConstraint.fromDict(d) for d in data["constraints"]],
            data["sos1"],
            data["sos2"],
        )


def readMPS(path: str, sense: int, dropConsNames: bool = False) -> MPS:
    """
    Reads an MPS file and returns an MPS dataclass.

    Uses Rust parser for performance, converts result to Python dataclasses.

    :param path: path of mps file
    :param sense: 1 for minimize, -1 for maximize
    :param dropConsNames: if True, do not store the names of constraints
    :return: a dataclass with all the problem data
    """
    data = _rustcore.read_mps(path, sense, dropConsNames)
    return MPS.fromDict(data)


def readMPSSetBounds(line: list[str], variable_dict: dict[str, MPSVariable]) -> None:
    bound = line[0]
    var_name = line[2]

    if bound == "FR":
        variable_dict[var_name].lowBound = None
        variable_dict[var_name].upBound = None
    elif bound == "BV":
        variable_dict[var_name].lowBound = 0
        variable_dict[var_name].upBound = 1
    elif bound == "PL":
        variable_dict[var_name].lowBound = 0
        variable_dict[var_name].upBound = None
    elif bound == "MI":
        variable_dict[var_name].lowBound = None
        variable_dict[var_name].upBound = 0
    else:
        value = float(line[3])
        if bound == "LO":
            variable_dict[var_name].lowBound = value
        elif bound == "UP":
            variable_dict[var_name].upBound = value
        elif bound == "FX":
            variable_dict[var_name].lowBound = value
            variable_dict[var_name].upBound = value
        else:
            raise const.PulpError(f"Unknown bound {bound}")


def readMPSSetRhs(line: list[str], constraintsDict: dict[str, MPSConstraint]) -> None:
    constraintsDict[line[1]].constant = -float(line[2])
    if len(line) == 5:  # read fields 5, 6
        constraintsDict[line[3]].constant = -float(line[4])


def writeMPS(
    lp: LpProblem,
    filename: str,
    mpsSense: int = 0,
    rename: int | bool = False,
    mip: int | bool = True,
    with_objsense: bool = False,
) -> (
    list[LpVariable]
    | tuple[list[LpVariable], dict[str, str], dict[str, str], str | None]
):
    wasNone, dummyVar = lp.fixObjective()
    if mpsSense == 0:
        mpsSense = lp.sense
    if lp.objective is None:
        raise ValueError("objective is None")
    cobj = lp.objective
    if mpsSense == const.LpMaximize:
        n = cobj.name
        cobj = -cobj
        cobj.name = n
        mpsSense = const.LpMinimize

    extra_col: dict[int, str] = {}
    if rename:
        constrNames, varNames, cobj.name = lp.normalisedNames()
        vs = list(lp._variables)
        for c in lp.constraints.values():
            for v, _ in c.items():
                if v.name not in varNames:
                    if v.name:
                        n = len(vs)
                        varNames[v.name] = "X%07d" % n
                        vs.append(v)
                    else:
                        vid = v._var.id()
                        if vid not in extra_col:
                            extra_col[vid] = "_var_%d" % vid
                            vs.append(v)

        def col_name(v) -> str:
            vid = v._var.id()
            return varNames.get(v.name) or extra_col.get(vid) or ("_var_%d" % vid)
    else:
        vs = list(lp.variables())
        varNames = {v.name: v.name for v in vs}
        constrNames = {c: c for c in lp.constraints}
        for c in lp.constraints.values():
            for v, _ in c.items():
                if v.name not in varNames:
                    if v.name:
                        varNames[v.name] = v.name
                        vs.append(v)
                    else:
                        vid = v._var.id()
                        if vid not in extra_col:
                            extra_col[vid] = "_var_%d" % vid
                            vs.append(v)

        def col_name(v) -> str:
            vid = v._var.id()
            return varNames.get(v.name) or extra_col.get(vid) or ("_var_%d" % vid)

    model_name = "MODEL" if rename else lp.name
    objName = cobj.name or "OBJ"

    # Use rename-aware column/row/bound writing (Python, since rename logic is complex)
    row_lines = [
        " " + const.LpConstraintTypeToMps[c.sense] + "  " + constrNames[k] + "\n"
        for k, c in lp.constraints.items()
    ]
    coefs: dict[str, dict[str, Union[int, float]]] = {col_name(v): {} for v in vs}
    for k, c in lp.constraints.items():
        k = constrNames[k]
        for v, value in c.items():
            coefs[col_name(v)][k] = value

    columns_lines: list[str] = []
    for v in vs:
        name = col_name(v)
        columns_lines.extend(
            writeMPSColumnLines(coefs[name], v, mip, name, cobj, objName)
        )

    rhs_lines = [
        "    RHS       %-8s  % .12e\n"
        % (constrNames[k], -c.constant if c.constant != 0 else 0)
        for k, c in lp.constraints.items()
    ]
    bound_lines: list[str] = []
    for v in vs:
        bound_lines.extend(writeMPSBoundLines(col_name(v), v, mip))

    with open(filename, "w") as f:
        if with_objsense:
            f.write("OBJSENSE\n")
            f.write(f" {const.LpSensesMPS[mpsSense]}\n")
        else:
            f.write(f"*SENSE:{const.LpSenses[mpsSense]}\n")
        f.write(f"NAME          {model_name}\n")
        f.write("ROWS\n")
        f.write(f" N  {objName}\n")
        f.write("".join(row_lines))
        f.write("COLUMNS\n")
        f.write("".join(columns_lines))
        f.write("RHS\n")
        f.write("".join(rhs_lines))
        f.write("BOUNDS\n")
        f.write("".join(bound_lines))
        f.write("ENDATA\n")
    lp.restoreObjective(wasNone, dummyVar)
    if not rename:
        return vs
    else:
        return vs, varNames, constrNames, cobj.name


def writeMPSColumnLines(
    cv: dict[str, Union[int, float]],
    variable: LpVariable,
    mip: int | bool,
    name: str,
    cobj: LpAffineExpression,
    objName: str,
) -> list[str]:
    columns_lines: list[str] = []
    cat = _safe_var_cat(variable)
    if mip and cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTORG'\n")
    # Most of the work is done here
    _tmp = ["    %-8s  %-8s  % .12e\n" % (name, k, v) for k, v in cv.items()]
    columns_lines.extend(_tmp)

    # objective function
    if variable in cobj:
        columns_lines.append(
            "    %-8s  %-8s  % .12e\n" % (name, objName, cobj[variable])
        )
    if mip and cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTEND'\n")
    return columns_lines


def writeMPSBoundLines(name: str, variable: LpVariable, mip: int | bool) -> list[str]:
    low, up = _safe_var_bounds(variable)
    cat = _safe_var_cat(variable)
    if low is not None and low == up:
        return [" FX BND       %-8s  % .12e\n" % (name, low)]
    elif low == 0 and up == 1 and mip and cat == const.LpInteger:
        return [" BV BND       %-8s\n" % name]
    bound_lines: list[str] = []
    if low is not None:
        if low != 0 or (mip and cat == const.LpInteger and up is None):
            bound_lines.append(" LO BND       %-8s  % .12e\n" % (name, low))
    else:
        if up is not None:
            bound_lines.append(" MI BND       %-8s\n" % name)
        else:
            bound_lines.append(" FR BND       %-8s\n" % name)
    if up is not None:
        bound_lines.append(" UP BND       %-8s  % .12e\n" % (name, up))
    return bound_lines


def writeLP(
    lp: LpProblem,
    filename: str,
    writeSOS: int | bool = True,
    mip: int | bool = True,
    max_length: int = 100,
) -> list[LpVariable]:
    wasNone, objectiveDummyVar = lp.fixObjective()
    assert lp.objective is not None
    objName = lp.objective.name or "OBJ"

    # Ensure dummy variable exists if any constraint is empty
    has_empty = any(len(c) == 0 for c in lp.constraints.values())
    if has_empty:
        lp.get_dummyVar()
    dummy_var_name = ""
    if lp.dummyVar is not None:
        dummy_var_name = lp.dummyVar.name

    # Build SOS lines
    sos_lines = ""
    if writeSOS and (lp.sos1 or lp.sos2):
        parts = ["SOS\n"]
        if lp.sos1:
            for sos in lp.sos1.values():
                parts.append("S1:: \n")
                for v, val in sos.items():
                    parts.append(f" {v.name}: {val:.12g}\n")
        if lp.sos2:
            for sos in lp.sos2.values():
                parts.append("S2:: \n")
                for v, val in sos.items():
                    parts.append(f" {v.name}: {val:.12g}\n")
        sos_lines = "".join(parts)

    try:
        rust_vars = _rustcore.write_lp(
            lp._model,
            filename,
            bool(mip),
            max_length,
            objName,
            dummy_var_name,
            sos_lines,
        )
    except RuntimeError as e:
        raise const.PulpError(str(e)) from None
    finally:
        lp.restoreObjective(wasNone, objectiveDummyVar)

    from .pulp import LpVariable  # deferred: circular import with pulp.py

    return [LpVariable(v) for v in rust_vars]
