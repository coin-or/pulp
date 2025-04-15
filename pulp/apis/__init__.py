from typing import Dict, Optional, Type, Union

from .choco_api import *
from .coin_api import *
from .copt_api import *
from .core import *
from .cplex_api import *
from .glpk_api import *
from .gurobi_api import *
from .highs_api import *
from .mipcl_api import *
from .mosek_api import *
from .sas_api import *
from .scip_api import *
from .xpress_api import *
from .cuopt_api import *

_all_solvers: List[Type[LpSolver]] = [
    CYLP,
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
    SAS94,
    SASCAS,
    CUOPT,
]

import json

LpSolverDefault: Optional[Union[PULP_CBC_CMD, GLPK_CMD, COIN_CMD]] = None
# Default solver selection
if PULP_CBC_CMD().available():
    LpSolverDefault = PULP_CBC_CMD()
elif GLPK_CMD().available():
    LpSolverDefault = GLPK_CMD()
elif COIN_CMD().available():
    LpSolverDefault = COIN_CMD()


def getSolver(solver: str, *args, **kwargs) -> LpSolver:
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


def getSolverFromDict(data: Dict[str, Union[str, bool, float, int]]) -> LpSolver:
    """
    Instantiates a solver from a dictionary with its data

    :param dict data: a dictionary with, at least an "solver" key with the name
        of the solver to create
    :return: a solver of type :py:class:`LpSolver`
    :raises PulpSolverError: if the dictionary does not have the "solver" key
    :rtype: LpSolver
    """
    data = dict(data)
    solver = data.pop("solver", None)
    if solver is None:
        raise PulpSolverError("The json file has no solver attribute.")
    assert isinstance(solver, str)
    return getSolver(solver, **data)


def getSolverFromJson(filename: str) -> LpSolver:
    """
    Instantiates a solver from a json file with its data

    :param str filename: name of the json file to read
    :return: a solver of type :py:class:`LpSolver`
    :rtype: LpSolver
    """
    with open(filename) as f:
        data = json.load(f)
    return getSolverFromDict(data)


def listSolvers(onlyAvailable: bool = False) -> List[str]:
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
