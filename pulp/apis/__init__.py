import json
from typing import Dict, List, Optional, Type, Union

from .choco_api import CHOCO_CMD
from .coin_api import COIN_CMD, COINMP_DLL, CYLP, YAPOSIB
from .copt_api import COPT, COPT_CMD, COPT_DLL
from .core import LpSolver, LpSolver_CMD, PulpSolverError
from .cplex_api import CPLEX, CPLEX_CMD, CPLEX_PY
from .cuopt_api import CUOPT
from .glpk_api import GLPK, GLPK_CMD, PYGLPK
from .gurobi_api import GUROBI, GUROBI_CMD
from .highs_api import HiGHS, HiGHS_CMD
from .mipcl_api import MIPCL_CMD
from .mosek_api import MOSEK
from .sas_api import SAS94, SASCAS, SASsolver
from .scip_api import FSCIP, FSCIP_CMD, SCIP, SCIP_CMD, SCIP_PY
from .xpress_api import XPRESS, XPRESS_CMD, XPRESS_PY

__all__ = [
    "CHOCO_CMD",
    "COIN_CMD",
    "COINMP_DLL",
    "CYLP",
    "YAPOSIB",
    "COPT",
    "COPT_CMD",
    "COPT_DLL",
    "LpSolver",
    "LpSolver_CMD",
    "PulpSolverError",
    "CPLEX",
    "CPLEX_CMD",
    "CPLEX_PY",
    "CUOPT",
    "GLPK",
    "GLPK_CMD",
    "PYGLPK",
    "GUROBI",
    "GUROBI_CMD",
    "HiGHS",
    "HiGHS_CMD",
    "MIPCL_CMD",
    "MOSEK",
    "SAS94",
    "SASCAS",
    "SASsolver",
    "FSCIP",
    "FSCIP_CMD",
    "SCIP",
    "SCIP_CMD",
    "SCIP_PY",
    "XPRESS",
    "XPRESS_CMD",
    "XPRESS_PY",
    "LpSolverDefault",
    "getSolver",
    "getSolverFromDict",
    "getSolverFromJson",
    "listSolvers",
]

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

LpSolverDefault: Optional[Union[COIN_CMD, GLPK_CMD]] = None
# Default solver selection: CBC via COIN_CMD (cbcbox extra or ``cbc`` on PATH), else GLPK.
if COIN_CMD().available():
    LpSolverDefault = COIN_CMD()
elif GLPK_CMD().available():
    LpSolverDefault = GLPK_CMD()


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
