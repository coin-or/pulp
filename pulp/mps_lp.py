"""

@author: Franco Peschiera

"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any

from . import _rustcore
from . import constants as const

if TYPE_CHECKING:
    from pulp.pulp import LpProblem, LpVariable

_DC = Any  # type alias for a dataclass type


def _from_compatible_object(cls: type[_DC], obj: object) -> _DC:
    """Initialize a dataclass from any object sharing the same field names."""
    return cls(**{f.name: getattr(obj, f.name) for f in fields(cls)})


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

    @classmethod
    def from_rust(cls, obj: Any) -> MPS:
        """Build MPS dataclass from Rust MpsResult object returned by read_mps."""
        parameters = _from_compatible_object(MPSParameters, obj.parameters)
        obj_obj = obj.objective
        objective = MPSObjective(
            obj_obj.name,
            [_from_compatible_object(MPSCoefficient, c) for c in obj_obj.coefficients],
        )
        variables = [_from_compatible_object(MPSVariable, v) for v in obj.variables]
        constraints = [
            MPSConstraint(
                c.name,
                c.sense,
                [_from_compatible_object(MPSCoefficient, cc) for cc in c.coefficients],
                c.pi,
                c.constant,
            )
            for c in obj.constraints
        ]
        return cls(
            parameters,
            objective,
            variables,
            constraints,
            list(obj.sos1),
            list(obj.sos2),
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
    mps_result = _rustcore.read_mps(path, sense, dropConsNames)
    if isinstance(mps_result, dict):
        return MPS.fromDict(mps_result)
    return MPS.from_rust(mps_result)


def writeMPS(
    lp: LpProblem,
    filename: str,
    mpsSense: int = 0,
    rename: int | bool = False,
    mip: int | bool = True,
    with_objsense: bool = False,
) -> tuple[list[str], list[str], str]:
    """Write MPS file via Rust core. Returns (variable_names, constraint_names, objective_name) in list form."""
    wasNone, dummyVar = lp.fixObjective()
    try:
        if mpsSense == 0:
            mpsSense = lp.sense
        if lp.objective is None:
            raise ValueError("objective is None")
        model_name = "MODEL" if rename else lp.name
        obj_name = (lp.objective.name or "OBJ") if not rename else "OBJ"
        result = _rustcore.write_mps(
            lp._model,
            filename,
            mpsSense,
            bool(mip),
            with_objsense,
            bool(rename),
            model_name,
            obj_name,
        )
        return result
    finally:
        lp.restoreObjective(wasNone, dummyVar)


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
