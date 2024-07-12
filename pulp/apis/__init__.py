from .coin_api import *
from .cplex_api import *
from .gurobi_api import *
from .glpk_api import *
from .choco_api import *
from .mipcl_api import *
from .mosek_api import *
from .scip_api import *
from .xpress_api import *
from .highs_api import *
from .copt_api import *
from .core import *

_all_solvers = [
    GLPK_CMD,
    PYGLPK,
    CPLEX_CMD,
    CPLEX_PY,
    GUROBI,
    GUROBI_CMD,
    MOSEK,
    XPRESS,
    XPRESS_CMD,
    XPRESS_PY,
    PULP_CBC_CMD,
    COIN_CMD,
    COINMP_DLL,
    CHOCO_CMD,
    MIPCL_CMD,
    SCIP_CMD,
    FSCIP_CMD,
    SCIP_PY,
    HiGHS,
    HiGHS_CMD,
    COPT,
    COPT_DLL,
    COPT_CMD,
]

import json

# Default solver selection
if PULP_CBC_CMD().available():
    LpSolverDefault = PULP_CBC_CMD()
elif GLPK_CMD().available():
    LpSolverDefault = GLPK_CMD()
elif COIN_CMD().available():
    LpSolverDefault = COIN_CMD()
else:
    LpSolverDefault = None


def setConfigInformation(**keywords):
    """
    set the data in the configuration file
    at the moment will only edit things in [locations]
    the keyword value pairs come from the keywords dictionary
    """
    # TODO: extend if we ever add another section in the config file
    # read the old configuration
    config = Parser()
    config.read(config_filename)
    # set the new keys
    for key, val in keywords.items():
        config.set("locations", key, val)
    # write the new configuration
    fp = open(config_filename, "w")
    config.write(fp)
    fp.close()


def configSolvers():
    """
    Configure the path the the solvers on the command line

    Designed to configure the file locations of the solvers from the
    command line after installation
    """
    configlist = [
        (cplex_dll_path, "cplexpath", "CPLEX: "),
        (coinMP_path, "coinmppath", "CoinMP dll (windows only): "),
    ]
    print(
        "Please type the full path including filename and extension \n"
        + "for each solver available"
    )
    configdict = {}
    for default, key, msg in configlist:
        value = input(msg + "[" + str(default) + "]")
        if value:
            configdict[key] = value
    setConfigInformation(**configdict)


def getSolver(solver, *args, **kwargs):
    """
    Instantiates a solver from its name

    :param str solver: solver name to create
    :param args: additional arguments to the solver
    :param kwargs: additional keyword arguments to the solver
    :return: solver of type :py:class:`LpSolver`
    """
    mapping = {k.name: k for k in _all_solvers}
    try:
        return mapping[solver](*args, **kwargs)
    except KeyError:
        raise PulpSolverError(
            "The solver {} does not exist in PuLP.\nPossible options are: \n{}".format(
                solver, mapping.keys()
            )
        )


def getSolverFromDict(data):
    """
    Instantiates a solver from a dictionary with its data

    :param dict data: a dictionary with, at least an "solver" key with the name
        of the solver to create
    :return: a solver of type :py:class:`LpSolver`
    :raises PulpSolverError: if the dictionary does not have the "solver" key
    :rtype: LpSolver
    """
    solver = data.pop("solver", None)
    if solver is None:
        raise PulpSolverError("The json file has no solver attribute.")
    return getSolver(solver, **data)


def getSolverFromJson(filename):
    """
    Instantiates a solver from a json file with its data

    :param str filename: name of the json file to read
    :return: a solver of type :py:class:`LpSolver`
    :rtype: LpSolver
    """
    with open(filename) as f:
        data = json.load(f)
    return getSolverFromDict(data)


def listSolvers(onlyAvailable=False):
    """
    List the names of all the existing solvers in PuLP

    :param bool onlyAvailable: if True, only show the available solvers
    :return: list of solver names
    :rtype: list
    """
    result = []
    for s in _all_solvers:
        solver = s(msg=False)
        if (not onlyAvailable) or solver.available():
            result.append(solver.name)
        del solver
    return result
