"""

@author: Franco Peschiera

"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Union

from . import constants as const

if TYPE_CHECKING:
    from pulp.pulp import LpProblem, LpVariable, LpAffineExpression, _ObjectiveView

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


def _safe_var_cat(variable: "LpVariable"):
    """Variable category; defaults to continuous if variable is from another model (e.g. after extend)."""
    try:
        return variable.cat
    except BaseException:
        return const.LpContinuous


def _safe_var_bounds(variable: "LpVariable"):
    """(lowBound, upBound) with defaults if variable is from another model.
    Converts inf/-inf back to None for MPS/LP format compatibility."""
    import math
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

from dataclasses import dataclass


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
    adapted from Julian Märte (https://github.com/pchtsp/pysmps)
    returns a dictionary with the contents of the model.
    This dictionary can be used to generate an LpProblem

    :param path: path of mps file
    :param sense: 1 for minimize, -1 for maximize
    :param dropConsNames: if True, do not store the names of constraints
    :return: a dictionary with all the problem data
    """

    mode = ""
    parameters = MPSParameters(name="", sense=sense, status=0, sol_status=0)
    variable_info: dict[str, MPSVariable] = {}
    constraints: dict[str, MPSConstraint] = {}
    objective = MPSObjective(name="", coefficients=[])
    sos1: list[Any] = []
    sos2: list[Any] = []
    # TODO: maybe take out rhs_names and bnd_names? not sure if they're useful
    rhs_names: list[str] = []
    bnd_names: list[str] = []
    integral_marker: bool = False

    with open(path) as reader:
        for line in reader:
            line = re.split(" |\t", line)
            line = [x.strip() for x in line]
            line = list(filter(None, line))

            if line[0] == "ENDATA":
                break
            if line[0] == "*":
                continue
            if line[0] == "NAME":
                if len(line) > 1:
                    parameters.name = line[1]
                else:
                    parameters.name = ""
                continue

            # here we get the mode
            if line[0] in [CORE_FILE_ROW_MODE, CORE_FILE_COL_MODE]:
                mode = line[0]
            elif line[0] == CORE_FILE_RHS_MODE and len(line) <= 2:
                if len(line) > 1:
                    rhs_names.append(line[1])
                    mode = CORE_FILE_RHS_MODE_NAME_GIVEN
                else:
                    mode = CORE_FILE_RHS_MODE_NO_NAME
            elif line[0] == CORE_FILE_BOUNDS_MODE and len(line) <= 2:
                if len(line) > 1:
                    bnd_names.append(line[1])
                    mode = CORE_FILE_BOUNDS_MODE_NAME_GIVEN
                else:
                    mode = CORE_FILE_BOUNDS_MODE_NO_NAME

            # here we query the mode variable
            elif mode == CORE_FILE_ROW_MODE:
                row_type = line[0]
                row_name = line[1]
                if row_type == ROW_MODE_OBJ:
                    objective.name = row_name
                else:
                    constraints[row_name] = MPSConstraint(
                        name=row_name, sense=ROW_EQUIV[row_type], coefficients=[]
                    )
            elif mode == CORE_FILE_COL_MODE:
                var_name = line[0]
                if len(line) > 1 and line[1] == "'MARKER'":
                    if line[2] == "'INTORG'":
                        integral_marker = True
                    elif line[2] == "'INTEND'":
                        integral_marker = False
                    continue
                if var_name not in variable_info:
                    variable_info[var_name] = MPSVariable(
                        cat=COL_EQUIV[integral_marker], name=var_name
                    )
                j = 1
                while j < len(line) - 1:
                    if line[j] == objective.name:
                        # we store the variable objective coefficient
                        objective.coefficients.append(
                            MPSCoefficient(name=var_name, value=float(line[j + 1]))
                        )
                    else:
                        # we store the variable coefficient
                        constraints[line[j]].coefficients.append(
                            MPSCoefficient(name=var_name, value=float(line[j + 1]))
                        )
                    j = j + 2
            elif mode == CORE_FILE_RHS_MODE_NAME_GIVEN:
                if line[0] != rhs_names[-1]:
                    raise const.PulpError(
                        "Other RHS name was given even though name was set after RHS tag."
                    )
                readMPSSetRhs(line, constraints)
            elif mode == CORE_FILE_RHS_MODE_NO_NAME:
                readMPSSetRhs(line, constraints)
                if line[0] not in rhs_names:
                    rhs_names.append(line[0])
            elif mode == CORE_FILE_BOUNDS_MODE_NAME_GIVEN:
                if line[1] != bnd_names[-1]:
                    raise const.PulpError(
                        "Other BOUNDS name was given even though name was set after BOUNDS tag."
                    )
                readMPSSetBounds(line, variable_info)
            elif mode == CORE_FILE_BOUNDS_MODE_NO_NAME:
                readMPSSetBounds(line, variable_info)
                if line[1] not in bnd_names:
                    bnd_names.append(line[1])
    constraints_list = list(constraints.values())
    if dropConsNames:
        for c in constraints_list:
            c.name = None
        objective.name = None
    variable_info_list = list(variable_info.values())
    return MPS(
        parameters=parameters,
        objective=objective,
        variables=variable_info_list,
        constraints=constraints_list,
        sos1=sos1,
        sos2=sos2,
    )


def readMPSSetBounds(line: list[str], variable_dict: dict[str, MPSVariable]):
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


def readMPSSetRhs(line: list[str], constraintsDict: dict[str, MPSConstraint]):
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
) -> list[LpVariable] | tuple[list[LpVariable], dict[str, str], dict[str, str], str | None]:
    wasNone, dummyVar = lp.fixObjective()
    if mpsSense == 0:
        mpsSense = lp.sense
    if lp.objective is None:
        raise ValueError("objective is None")
    cobj = lp.objective
    # Normalize to minimization: max f <=> min -f, so CBC always sees MIN (avoids -max flag)
    if mpsSense == const.LpMaximize:
        n = cobj.name
        cobj = -cobj
        cobj.name = n
        mpsSense = const.LpMinimize
    # For variables in constraints but not in vs (e.g. extend/elastic); key by Rust var id so wrappers match
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

        def col_name(v: LpVariable) -> str:
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

        def col_name(v: LpVariable) -> str:
            vid = v._var.id()
            return varNames.get(v.name) or extra_col.get(vid) or ("_var_%d" % vid)
    model_name = lp.name
    if rename:
        model_name = "MODEL"
    objName = cobj.name
    if not objName:
        objName = "OBJ"

    # constraints
    row_lines = [
        " " + const.LpConstraintTypeToMps[c.sense] + "  " + constrNames[k] + "\n"
        for k, c in lp.constraints.items()
    ]
    # Creation of a dict of dict:
    # coefs[variable_name][constraint_name] = coefficient
    coefs: dict[str, dict[str, Union[int, float]]] = {col_name(v): {} for v in vs}
    for k, c in lp.constraints.items():
        k = constrNames[k]
        for v, value in c.items():
            coefs[col_name(v)][k] = value

    # matrix
    columns_lines: list[str] = []
    for v in vs:
        name = col_name(v)
        columns_lines.extend(
            writeMPSColumnLines(coefs[name], v, mip, name, cobj, objName)
        )

    # right hand side
    rhs_lines = [
        "    RHS       %-8s  % .12e\n"
        % (constrNames[k], -c.constant if c.constant != 0 else 0)
        for k, c in lp.constraints.items()
    ]
    # bounds
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
    # returns the variables, in writing order
    if not rename:
        return vs
    else:
        return vs, varNames, constrNames, cobj.name


def writeMPSColumnLines(
    cv: dict[str, Union[int, float]],
    variable: LpVariable,
    mip: int | bool,
    name: str,
    cobj: LpAffineExpression | _ObjectiveView,
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
    f = open(filename, "w")
    f.write("\\* " + lp.name + " *\\\n")
    if lp.sense == 1:
        f.write("Minimize\n")
    else:
        f.write("Maximize\n")
    wasNone, objectiveDummyVar = lp.fixObjective()
    assert lp.objective is not None
    objName = lp.objective.name
    if not objName:
        objName = "OBJ"
    f.write(lp.objective.asCplexLpAffineExpression(objName, include_constant=False))
    f.write("Subject To\n")
    ks = list(lp.constraints.keys())
    ks.sort()
    dummyWritten = False
    for k in ks:
        constraint = lp.constraints[k]
        if not list(constraint.keys()):
            # empty constraint: use dummyVar so infeasible problems stay infeasible
            # (do not modify Rust-backed constraint in place; write synthetic line)
            dummyVar = lp.get_dummyVar()
            if not dummyWritten:
                f.write((dummyVar == 0.0).asCplexLpConstraint("_dummy"))
                dummyWritten = True
            c = -constraint.constant
            if c == 0:
                c = 0
            f.write(
                f"{k}: 1 {dummyVar.name} {const.LpConstraintSenses[constraint.sense]} {c:.12g}\n"
            )
            continue
        f.write(constraint.asCplexLpConstraint(k))
    # check if any names are longer than 100 characters
    lp.checkLengthVars(max_length)
    vs = lp.variables()
    # check for repeated names
    lp.checkDuplicateVars()
    # Bounds on non-"positive" variables
    # Note: XPRESS and CPLEX do not interpret integer variables without
    # explicit bounds
    if mip:
        vg = [
            v
            for v in vs
            if not (v.isPositive() and v.cat == const.LpContinuous) and not v.isBinary()
        ]
    else:
        vg = [v for v in vs if not v.isPositive()]
    if vg:
        f.write("Bounds\n")
        for v in vg:
            f.write(f" {v.asCplexLpVariable()}\n")
    # Integer non-binary variables
    if mip:
        vg = [v for v in vs if v.cat == const.LpInteger and not v.isBinary()]
        if vg:
            f.write("Generals\n")
            for v in vg:
                f.write(f"{v.name}\n")
        # Binary variables
        vg = [v for v in vs if v.isBinary()]
        if vg:
            f.write("Binaries\n")
            for v in vg:
                f.write(f"{v.name}\n")
    # Special Ordered Sets
    if writeSOS and (lp.sos1 or lp.sos2):
        f.write("SOS\n")
        if lp.sos1:
            for sos in lp.sos1.values():
                f.write("S1:: \n")
                for v, val in sos.items():
                    f.write(f" {v.name}: {val:.12g}\n")
        if lp.sos2:
            for sos in lp.sos2.values():
                f.write("S2:: \n")
                for v, val in sos.items():
                    f.write(f" {v.name}: {val:.12g}\n")
    f.write("End\n")
    f.close()
    lp.restoreObjective(wasNone, objectiveDummyVar)
    return vs
