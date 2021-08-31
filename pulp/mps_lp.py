# -*- coding: utf-8 -*-
"""

@author: Franco Peschiera

"""

from . import constants as const
import pysmps.mps_loader as mps
import math

ROW_EQUIV = {v: k for k, v in const.LpConstraintTypeToMps.items()}


def readMPS(path, sense, dropConsNames=False):
    """
    returns a dictionary with the contents of the model.
    This dictionary can be used to generate an LpProblem

    :param path: path of mps file
    :param sense: 1 for minimize, -1 for maximize
    :param dropConsNames: if True, do not store the names of constraints
    :return: a dictionary with all the problem data
    """
    pysmps_data = mps.load_mps(path)
    return pysmpsToPuLP(pysmps_data, sense, dropConsNames=dropConsNames)


def writeMPS(LpProblem, filename, mpsSense=0, rename=0, mip=1):
    wasNone, dummyVar = LpProblem.fixObjective()
    if mpsSense == 0:
        mpsSense = LpProblem.sense
    cobj = LpProblem.objective
    if mpsSense != LpProblem.sense:
        n = cobj.name
        cobj = -cobj
        cobj.name = n
    if rename:
        constrNames, varNames, cobj.name = LpProblem.normalisedNames()
        # No need to call self.variables() again, we have just filled self._variables:
        vs = LpProblem._variables
    else:
        vs = LpProblem.variables()
        varNames = dict((v.name, v.name) for v in vs)
        constrNames = dict((c, c) for c in LpProblem.constraints)
    model_name = LpProblem.name
    if rename:
        model_name = "MODEL"
    objName = cobj.name
    if not objName:
        objName = "OBJ"

    # constraints
    row_lines = [
        " " + const.LpConstraintTypeToMps[c.sense] + "  " + constrNames[k] + "\n"
        for k, c in LpProblem.constraints.items()
    ]
    # Creation of a dict of dict:
    # coefs[variable_name][constraint_name] = coefficient
    coefs = {varNames[v.name]: {} for v in vs}
    for k, c in LpProblem.constraints.items():
        k = constrNames[k]
        for v, value in c.items():
            coefs[varNames[v.name]][k] = value

    # matrix
    columns_lines = []
    for v in vs:
        name = varNames[v.name]
        columns_lines.extend(
            writeMPSColumnLines(coefs[name], v, mip, name, cobj, objName)
        )

    # right hand side
    rhs_lines = [
        "    RHS       %-8s  % .12e\n"
        % (constrNames[k], -c.constant if c.constant != 0 else 0)
        for k, c in LpProblem.constraints.items()
    ]
    # bounds
    bound_lines = []
    for v in vs:
        bound_lines.extend(writeMPSBoundLines(varNames[v.name], v, mip))

    with open(filename, "w") as f:
        f.write("*SENSE:" + const.LpSenses[mpsSense] + "\n")
        f.write("NAME          " + model_name + "\n")
        f.write("ROWS\n")
        f.write(" N  %s\n" % objName)
        f.write("".join(row_lines))
        f.write("COLUMNS\n")
        f.write("".join(columns_lines))
        f.write("RHS\n")
        f.write("".join(rhs_lines))
        f.write("BOUNDS\n")
        f.write("".join(bound_lines))
        f.write("ENDATA\n")
    LpProblem.restoreObjective(wasNone, dummyVar)
    # returns the variables, in writing order
    if rename == 0:
        return vs
    else:
        return vs, varNames, constrNames, cobj.name


def writeMPSColumnLines(cv, variable, mip, name, cobj, objName):
    columns_lines = []
    if mip and variable.cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTORG'\n")
    # Most of the work is done here
    _tmp = ["    %-8s  %-8s  % .12e\n" % (name, k, v) for k, v in cv.items()]
    columns_lines.extend(_tmp)

    # objective function
    if variable in cobj:
        columns_lines.append(
            "    %-8s  %-8s  % .12e\n" % (name, objName, cobj[variable])
        )
    if mip and variable.cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTEND'\n")
    return columns_lines


def writeMPSBoundLines(name, variable, mip):
    if variable.lowBound is not None and variable.lowBound == variable.upBound:
        return [" FX BND       %-8s  % .12e\n" % (name, variable.lowBound)]
    elif (
        variable.lowBound == 0
        and variable.upBound == 1
        and mip
        and variable.cat == const.LpInteger
    ):
        return [" BV BND       %-8s\n" % name]
    bound_lines = []
    if variable.lowBound is not None:
        # In MPS files, variables with no bounds (i.e. >= 0)
        # are assumed BV by COIN and CPLEX.
        # So we explicitly write a 0 lower bound in this case.
        if variable.lowBound != 0 or (
            mip and variable.cat == const.LpInteger and variable.upBound is None
        ):
            bound_lines.append(
                " LO BND       %-8s  % .12e\n" % (name, variable.lowBound)
            )
    else:
        if variable.upBound is not None:
            bound_lines.append(" MI BND       %-8s\n" % name)
        else:
            bound_lines.append(" FR BND       %-8s\n" % name)
    if variable.upBound is not None:
        bound_lines.append(" UP BND       %-8s  % .12e\n" % (name, variable.upBound))
    return bound_lines


def writeLP(LpProblem, filename, writeSOS=1, mip=1, max_length=100):
    f = open(filename, "w")
    f.write("\\* " + LpProblem.name + " *\\\n")
    if LpProblem.sense == 1:
        f.write("Minimize\n")
    else:
        f.write("Maximize\n")
    wasNone, objectiveDummyVar = LpProblem.fixObjective()
    objName = LpProblem.objective.name
    if not objName:
        objName = "OBJ"
    f.write(LpProblem.objective.asCplexLpAffineExpression(objName, constant=0))
    f.write("Subject To\n")
    ks = list(LpProblem.constraints.keys())
    ks.sort()
    dummyWritten = False
    for k in ks:
        constraint = LpProblem.constraints[k]
        if not list(constraint.keys()):
            # empty constraint add the dummyVar
            dummyVar = LpProblem.get_dummyVar()
            constraint += dummyVar
            # set this dummyvar to zero so infeasible problems are not made feasible
            if not dummyWritten:
                f.write((dummyVar == 0.0).asCplexLpConstraint("_dummy"))
                dummyWritten = True
        f.write(constraint.asCplexLpConstraint(k))
    # check if any names are longer than 100 characters
    LpProblem.checkLengthVars(max_length)
    vs = LpProblem.variables()
    # check for repeated names
    LpProblem.checkDuplicateVars()
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
            f.write(" %s\n" % v.asCplexLpVariable())
    # Integer non-binary variables
    if mip:
        vg = [v for v in vs if v.cat == const.LpInteger and not v.isBinary()]
        if vg:
            f.write("Generals\n")
            for v in vg:
                f.write("%s\n" % v.name)
        # Binary variables
        vg = [v for v in vs if v.isBinary()]
        if vg:
            f.write("Binaries\n")
            for v in vg:
                f.write("%s\n" % v.name)
    # Special Ordered Sets
    if writeSOS and (LpProblem.sos1 or LpProblem.sos2):
        f.write("SOS\n")
        if LpProblem.sos1:
            for sos in LpProblem.sos1.values():
                f.write("S1:: \n")
                for v, val in sos.items():
                    f.write(" %s: %.12g\n" % (v.name, val))
        if LpProblem.sos2:
            for sos in LpProblem.sos2.values():
                f.write("S2:: \n")
                for v, val in sos.items():
                    f.write(" %s: %.12g\n" % (v.name, val))
    f.write("End\n")
    f.close()
    LpProblem.restoreObjective(wasNone, objectiveDummyVar)
    return vs


def pysmpsToPuLP(pysmps_data, sense, dropConsNames=False):
    variables = [
        dict(
            cat=value["type"],
            name=value["name"],
            upBound=value["bnd_upper"] if value["bnd_upper"] != math.inf else None,
            lowBound=value["bnd_lower"] if value["bnd_lower"] != -math.inf else None,
            dj=None,
            varValue=None,
        )
        for name, value in pysmps_data["variable"].items()
    ]

    constraints = [
        dict(
            name=value["name"],
            coefficients=list(value["coefficients"]),
            sense=ROW_EQUIV[value["type"]],
            constant=-value["bounds"],
            pi=None,
        )
        for name, value in pysmps_data["constraints"].items()
    ]
    # we make a copy of all contents
    objective = dict(
        name=pysmps_data["objective"]["name"],
        coefficients=[dict(el) for el in pysmps_data["objective"]["coefficients"]],
    )

    # TODO: can we have the name?
    parameters = dict(name="", sense=sense, status=0, sol_status=0)
    if dropConsNames:
        for c in constraints:
            c["name"] = None
        objective["name"] = None
    return dict(
        constraints=constraints,
        variables=variables,
        objective=objective,
        parameters=parameters,
        sos1=[],
        sos2=[],
    )
