from __future__ import annotations

import dataclasses
import math
import warnings
from collections.abc import Iterable
from time import time
from typing import Any, Optional, cast

try:
    import ujson as json  # type: ignore[import-untyped]
except ImportError:
    import json

from .. import _rustcore
from .. import constants as const
from .. import mps_lp as mpslp
from ..apis import LpSolverDefault
from ..apis.core import LpSolver, clock
from ..utilities import value
from ._internal import _const_to_rust_cat, _const_to_rust_sense, _is_numpy_bool
from .lp_affine_expression import LpAffineExpression
from .lp_constraint import LpConstraint
from .lp_variable import LpVariable


class LpProblem:
    """An LP Problem"""

    def __init__(self, name: str = "NoName", sense: int = const.LpMinimize) -> None:
        """
        Creates an LP Problem

        This function creates a new LP Problem  with the specified associated parameters

        :param name: name of the problem used in the output .lp file
        :param sense: of the LP problem objective.  \
                Either :data:`~pulp.const.LpMinimize` (default) \
                or :data:`~pulp.const.LpMaximize`.
        :return: An LP Problem
        """
        if " " in name:
            warnings.warn("Spaces are not permitted in the name. Converted to '_'")
            name = name.replace(" ", "_")
        self.name = name
        self._sense = sense
        self.status = const.LpStatusNotSolved
        self.sol_status = const.LpSolutionNoSolutionFound
        self.solver = None
        self.solverModel = None
        self.dummyVar = None
        self.solutionTime = 0
        self.solutionCpuTime = 0
        # Set by some MIP solvers (e.g. COINMP_DLL) after solve when applicable.
        self.bestBound: float | None = None

        self._model: _rustcore.Model = _rustcore.Model(self.name)
        self._model.set_sense(
            _rustcore.ObjSense.Minimize
            if sense == const.LpMinimize
            else _rustcore.ObjSense.Maximize
        )

    def has_sos(self) -> bool:
        """True if the model has any SOS1/SOS2 groups (stored in the Rust core)."""
        return bool(self._model.sos_export())

    def clear_sos(self) -> None:
        """Remove all SOS groups from the model."""
        self._model.clear_sos()

    def add_sos_group(
        self,
        kind: _rustcore.SosKind,
        key: str | None,
        members: dict[LpVariable, float],
    ) -> None:
        """Add one SOS group. ``members`` maps each variable to its SOS weight."""
        self._model.add_sos_group(
            kind, key, [(v._var, float(w)) for v, w in members.items()]
        )

    def exported_variables(self) -> list[LpVariable]:
        """Variables that appear in the objective, a constraint, or an SOS group (solver column order)."""
        ids = self._model.used_variable_ids()
        rvs = self._model.list_variables_by_ids(ids)
        return [LpVariable(v) for v in rvs]

    def _sos_lists_for_mps_dataclass(self) -> tuple[list[Any], list[Any]]:
        vs = self.variables()
        s1: list[Any] = []
        s2: list[Any] = []
        for t, _key, pairs in self._model.sos_export():
            d = {vs[vid].name: float(w) for vid, w in pairs}
            if t == 1:
                s1.append(d)
            else:
                s2.append(d)
        return s1, s2

    def _sos_dicts_for_xpress(
        self,
    ) -> tuple[dict[str, dict[LpVariable, float]], dict[str, dict[LpVariable, float]]]:
        """XPRESS ``addSOS`` expects ``{group_name: {LpVariable: weight}}`` per SOS type."""
        vs = self.variables()
        d1: dict[str, dict[LpVariable, float]] = {}
        d2: dict[str, dict[LpVariable, float]] = {}
        for t, key, pairs in self._model.sos_export():
            name = key if key is not None else str(len(d1) + len(d2))
            m = {vs[vid]: float(w) for vid, w in pairs}
            if t == 1:
                d1[name] = m
            else:
                d2[name] = m
        return d1, d2

    def add_variable(
        self,
        name: str,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
    ) -> LpVariable:
        """Add a variable to the problem. Returns LpVariable wrapping the Rust variable."""
        if lowBound is not None and not math.isfinite(lowBound):
            raise const.PulpError(
                "The lower bound of a variable must be finite, got {}".format(lowBound)
            )
        if upBound is not None and not math.isfinite(upBound):
            raise const.PulpError(
                "The upper bound of a variable must be finite, got {}".format(upBound)
            )
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        if lowBound is not None and math.isfinite(lowBound):
            lb = lowBound
        if upBound is not None and math.isfinite(upBound):
            ub = upBound
        rcat = _const_to_rust_cat(cat)
        rvar = self._model.add_variable(name, lb, ub, rcat)
        return LpVariable(rvar)

    def add_variable_dicts(
        self,
        name: str,
        indices: tuple[Iterable[Any], ...] | Iterable[Any] | None = None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart: list[Any] | None = None,
    ) -> dict[Any, Any]:
        """Create a dictionary of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = list(indices[0])  # type: ignore[arg-type]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = _const_to_rust_cat(cat)
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [str(i)]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
            return {i: LpVariable(v) for i, v in zip(index, vars_)}
        return {
            i: self.add_variable_dicts(
                name, indices_rest, lowBound, upBound, cat, indexStart + [i]
            )
            for i in index
        }

    def add_variable_dict(
        self,
        name: str,
        indices: tuple[Iterable[Any], ...] | Iterable[Any] | None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
    ) -> dict[Any, LpVariable]:
        """Create a dictionary of variables with Cartesian product of indices."""
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        lists = list(indices)
        if len(indices) > 1:
            res = []
            while lists:
                first = lists[-1]
                nres = []
                if res:
                    if first:
                        for f in first:
                            nres.extend([[f] + r for r in res])
                    else:
                        nres = res
                    res = nres
                else:
                    res = [[f] for f in first]
                lists = lists[:-1]
            index = [tuple(r) for r in res]
        elif len(indices) == 1:
            index = list(cast(Iterable[Any], indices[0]))
        else:
            return {}
        names = [name % (i if isinstance(i, tuple) else (i,)) for i in index]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = _const_to_rust_cat(cat)
        vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
        return {i: LpVariable(v) for i, v in zip(index, vars_)}

    def add_variable_matrix(
        self,
        name: str,
        indices: tuple[Iterable[Any], ...] | Iterable[Any] | None = None,
        lowBound: Optional[float] = None,
        upBound: Optional[float] = None,
        cat: str = const.LpContinuous,
        indexStart: list[Any] | None = None,
    ) -> list[Any]:
        """Create a list or nested list of variables; names built from name + indices."""
        if indexStart is None:
            indexStart = []
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)
        index = list(indices[0])  # type: ignore[arg-type]
        indices_rest = indices[1:]
        lb = float("-inf") if lowBound is None else lowBound
        ub = float("inf") if upBound is None else upBound
        if cat == const.LpBinary:
            lb, ub = 0.0, 1.0
            cat = const.LpInteger
        rcat = _const_to_rust_cat(cat)
        if len(indices_rest) == 0:
            names = [name % tuple(indexStart + [i]) for i in index]
            vars_ = self._model.add_variables_batch(names, lb, ub, rcat)
            return [LpVariable(v) for v in vars_]
        return [
            self.add_variable_matrix(
                name, indices_rest, lowBound, upBound, cat, indexStart + [i]
            )
            for i in index
        ]

    def constraints(self) -> list[LpConstraint]:
        """Constraints from the Rust model, in insertion / id order."""
        return [LpConstraint(v) for v in self._model.list_constraints()]

    @property
    def objective(self) -> LpAffineExpression | None:
        """Objective expression from Rust, wrapped as LpAffineExpression."""
        expr = self._model.get_objective()
        if expr is None:
            return None
        return LpAffineExpression(expr)

    @objective.setter
    def objective(self, value: LpAffineExpression | LpVariable | None) -> None:
        """Set objective from LpAffineExpression or similar; stored in Rust."""
        if value is None:
            self._model.clear_objective()
            return
        if isinstance(value, LpVariable):
            value = LpAffineExpression.from_variable(value)
        self._model.set_objective(value._expr)

    @property
    def sense(self) -> int:
        return self._sense

    @sense.setter
    def sense(self, value: int) -> None:
        self._sense = value
        self._model.set_sense(
            _rustcore.ObjSense.Minimize
            if value == const.LpMinimize
            else _rustcore.ObjSense.Maximize
        )

    def __repr__(self) -> str:
        s = self.name + ":\n"
        if self.sense == 1:
            s += "MINIMIZE\n"
        else:
            s += "MAXIMIZE\n"
        s += repr(self.objective) + "\n"

        if self.constraints():
            s += "SUBJECT TO\n"
            for c in self.constraints():
                n = c.name or ""
                s += c.asCplexLpConstraint(n) + "\n"
        s += "VARIABLES\n"
        for v in self.variables():
            s += v.asCplexLpVariable() + " " + const.LpCategories[v.cat] + "\n"
        return s

    def __getstate__(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)

    @classmethod
    def _from_rust_model_copy(cls, source: LpProblem) -> LpProblem:
        """Build a new problem sharing Python metadata but a deep-copied Rust model."""
        p = object.__new__(cls)
        p.name = source.name
        p._sense = source._sense
        p._model = source._model.copy_model()
        p.status = source.status
        p.sol_status = source.sol_status
        p.solver = source.solver
        p.solverModel = source.solverModel
        p.dummyVar = source.dummyVar
        p.solutionTime = source.solutionTime
        p.solutionCpuTime = source.solutionCpuTime
        return p

    def copy(self) -> LpProblem:
        """Make a copy of self (deep copy of the Rust model)."""
        return LpProblem._from_rust_model_copy(self)

    def deepcopy(self) -> LpProblem:
        """Make a copy of self (deep copy of the Rust model)."""
        return LpProblem._from_rust_model_copy(self)

    def toDataclass(self) -> mpslp.MPS:
        """
        Creates a :py:class:`mpslp.MPS` from the model with as much data as possible.
        It replaces variables by variable names.
        So it requires to have unique names for variables.

        :return: :py:class:`mpslp.MPS` with model data
        :rtype: mpslp.MPS
        """
        try:
            self.checkDuplicateVars()
        except const.PulpError:
            raise const.PulpError(
                "Duplicated names found in variables:\nto export the model, variable names need to be unique"
            )
        try:
            self.checkDuplicateConstraints()
        except const.PulpError:
            raise const.PulpError(
                "Duplicated names found in constraints:\n"
                "to export the model, constraint names need to be unique"
            )
        self.fixObjective()
        assert self.objective is not None
        variables = self.variables()
        s1, s2 = self._sos_lists_for_mps_dataclass()
        return mpslp.MPS(
            objective=mpslp.MPSObjective(
                name=self.objective.name, coefficients=self.objective.toDataclass()
            ),
            constraints=[v.toDataclass() for v in self.constraints()],
            variables=[v.toDataclass() for v in variables],
            parameters=mpslp.MPSParameters(
                name=self.name,
                sense=self.sense,
                status=self.status,
                sol_status=self.sol_status,
            ),
            sos1=s1,
            sos2=s2,
        )

    def toRustModel(self) -> _rustcore.Model:
        """
        Return the Rust-backed model for this problem, if available.

        When the compiled extension ``pulp._rustcore`` is present, each
        :class:`LpProblem` maintains an internal Rust ``Model`` that mirrors
        variables, objective, and constraints as they are created.

        :raises RuntimeError: if the Rust extension is not available.
        """
        return self._model

    @classmethod
    def fromDataclass(
        cls,
        mps: mpslp.MPS,
        *,
        objective_negate_for_max: bool = True,
    ) -> tuple[dict[str, LpVariable], LpProblem]:
        """
        Takes a :py:class:`mpslp.MPS` with all necessary information to build a model.
        And returns a dictionary of variables and a problem object.

        :param mps: :py:class:`mpslp.MPS` with the model stored
        :param objective_negate_for_max: when True (default), negate objective coefficients
            when sense is Maximize (for MPS files written as minimization). Set False when
            loading from :meth:`toDict` / JSON, where coefficients are stored as-is.
        :return: a tuple with a dictionary of variables and a :py:class:`LpProblem`
        """

        # we instantiate the problem
        pb = cls(name=mps.parameters.name, sense=mps.parameters.sense)
        pb.status = mps.parameters.status
        pb.sol_status = mps.parameters.sol_status

        # recreate the variables.
        var: dict[str, LpVariable] = {
            v.name: LpVariable.fromDataclass(pb, v) for v in mps.variables
        }

        # objective function.
        obj_e = {var[v.name]: v.value for v in mps.objective.coefficients}
        # MPS files are written as minimization; when sense is Maximize we negated on write, so negate back on read. toDict stores coefficients as-is, so do not negate when loading from dict.
        if objective_negate_for_max and mps.parameters.sense == const.LpMaximize:
            obj_e = {v: -c for v, c in obj_e.items()}
        pb += LpAffineExpression.from_dict(obj_e, name=mps.objective.name)

        # constraints
        for c in mps.constraints:
            pb._addConstraintFromDataclass(c, var)

        pb._model.clear_sos()
        for i, group in enumerate(mps.sos1):
            members: dict[LpVariable, float] = {}
            for k, w in group.items():
                vk = var[k] if isinstance(k, str) else k
                members[vk] = float(w)
            pb.add_sos_group(_rustcore.SosKind.Sos1, str(i), members)
        for i, group in enumerate(mps.sos2):
            members = {}
            for k, w in group.items():
                vk = var[k] if isinstance(k, str) else k
                members[vk] = float(w)
            pb.add_sos_group(_rustcore.SosKind.Sos2, str(i), members)

        return var, pb

    def toDict(self) -> dict[str, Any]:
        return dataclasses.asdict(self.toDataclass())

    def to_dict(self) -> dict[str, Any]:
        warnings.warn(
            "LpProblem.to_dict is deprecated, use LpProblem.toDict instead",
            category=DeprecationWarning,
        )
        return self.toDict()

    @classmethod
    def fromDict(cls, data: dict[Any, Any]) -> tuple[dict[str, LpVariable], LpProblem]:
        return cls.fromDataclass(
            mpslp.MPS.fromDict(data), objective_negate_for_max=False
        )

    @classmethod
    def from_dict(cls, data: dict[Any, Any]) -> tuple[dict[str, LpVariable], LpProblem]:
        warnings.warn(
            "LpProblem.from_dict is deprecated, use LpProblem.fromDict instead",
            category=DeprecationWarning,
        )
        return cls.fromDict(data)

    def toJson(self, filename: str, *args: Any, **kwargs: Any) -> None:
        """
        Creates a json file from the LpProblem information

        :param str filename: filename to write json
        :param args: additional arguments for json function
        :param kwargs: additional keyword arguments for json function
        :return: None
        """
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    def to_json(self, filename: str, *args: Any, **kwargs: Any) -> None:
        warnings.warn(
            "LpProblem.to_json is deprecated, use LpProblem.toJson instead",
            category=DeprecationWarning,
        )
        return self.toJson(filename, *args, **kwargs)

    @classmethod
    def fromJson(cls, filename: str) -> tuple[dict[str, LpVariable], LpProblem]:
        """
        Creates a new LpProblem from a json file with information

        :param str filename: json file name
        :return: a tuple with a dictionary of variables and an LpProblem
        :rtype: (dict, :py:class:`LpProblem`)
        """
        with open(filename) as f:
            data = json.load(f)
        return cls.fromDict(data)

    @classmethod
    def from_json(cls, filename: str) -> tuple[dict[str, LpVariable], LpProblem]:
        warnings.warn(
            "LpProblem.from_json is deprecated, use LpProblem.fromJson instead",
            category=DeprecationWarning,
        )
        return cls.fromJson(filename)

    @classmethod
    def fromMPS(
        cls, filename: str, sense: int = const.LpMinimize, dropConsNames: bool = False
    ) -> tuple[dict[str, LpVariable], LpProblem]:
        data = mpslp.readMPS(filename, sense=sense, dropConsNames=dropConsNames)
        return cls.fromDataclass(data)

    def isMIP(self) -> int:
        return 1 if self._model.is_mip() else 0

    def roundSolution(self, epsInt: float = 1e-5, eps: float = 1e-7) -> None:
        """
        Rounds the lp variables

        Inputs:
            - none

        Side Effects:
            - The lp variables are rounded
        """
        self._model.round_solution(epsInt, eps)

    def valid(self, eps: float = 0) -> bool:
        for v in self.variables():
            if not v.valid(eps):
                return False
        for c in self.constraints():
            if not c.valid(eps):
                return False
        else:
            return True

    def infeasibilityGap(self, mip: bool = True) -> float:
        gap: float = 0
        for v in self.variables():
            gap = max(abs(v.infeasibilityGap(mip)), gap)
        for c in self.constraints():
            if not c.valid(0):
                cv = c.value()
                if cv is not None:
                    gap = max(abs(cv), gap)
        return gap

    def variables(self) -> list[LpVariable]:
        """Problem variables from the Rust model, in id order (same order as :meth:`constraints`)."""
        return [LpVariable(v) for v in self._model.list_variables()]

    def variablesDict(self) -> dict[str, LpVariable]:
        """Dict of variable name -> LpVariable, using same order as :meth:`variables`."""
        return {v.name: v for v in self.variables()}

    def add(self, constraint: LpAffineExpression, name: str | None = None) -> None:
        self.addConstraint(constraint, name)

    def _addConstraintFromDataclass(
        self, mps: mpslp.MPSConstraint, variables: dict[str, LpVariable]
    ) -> None:
        """Build a constraint directly from an MPSConstraint dataclass, preserving pi."""
        rust_expr = _rustcore.AffineExpr()
        for coefficient in mps.coefficients:
            rust_expr.add_term(variables[coefficient.name]._var, coefficient.value)
        rust_expr.set_constant(float(mps.constant))
        rust_expr.set_sense(_const_to_rust_sense(mps.sense))
        cname = str(mps.name).translate(LpAffineExpression.trans) if mps.name else ""
        # MPS row names may start with '_'; Rust rejects user names with a leading '_' (reserved for _C{n}).
        if cname and cname[0] == "_":
            cname = f"imp_{cname}"
        if cname:
            rust_expr.set_name(cname)
        rust_constr = self._model.add_constraint(rust_expr)
        if mps.pi is not None:
            rust_constr.set_pi(mps.pi)

    def addConstraint(
        self, constraint: LpAffineExpression, name: str | None = None
    ) -> None:
        if name:
            constraint.name = name
        rhs = -constraint.constant
        if not math.isfinite(rhs):
            raise const.PulpError(
                f"Invalid constraint RHS value: {rhs}. Coefficients and bounds must be finite."
            )
        for var, coeff in constraint._expr.items():
            if not math.isfinite(coeff):
                raise const.PulpError(
                    f"Invalid coefficient value: {coeff} for variable {var.name}. Coefficients must be finite."
                )
        if constraint.sense is None:
            raise const.PulpError("Cannot add constraint without a sense (<=, >=, ==)")
        try:
            self._model.add_constraint(constraint._expr)
        except ValueError as err:
            msg = str(err)
            if "different model" in msg or "no longer exists" in msg:
                raise const.PulpError(msg) from err
            raise

    def setObjective(self, obj: LpAffineExpression | LpVariable | int | float) -> None:
        """
        Sets the objective function.

        :param obj: the objective function (LpAffineExpression, LpVariable, or numeric)

        Side Effects:
            - The objective function is set
        """
        if isinstance(obj, LpVariable):
            self.objective = LpAffineExpression.from_variable(obj)
        elif isinstance(obj, (int, float)):
            self.objective = LpAffineExpression.from_constant(float(obj))
        else:
            self.objective = obj

    def __iadd__(
        self,
        other: LpAffineExpression
        | LpVariable
        | int
        | float
        | bool
        | tuple[Any, str | None],
    ) -> LpProblem:
        name: str | None = None
        if isinstance(other, tuple):
            other_val = other[0]
            name = str(other[1]) if other[1] is not None else None
            other = other_val  # type: ignore[assignment]
        if other is True:
            return self
        elif other is False:
            raise TypeError("A False object cannot be passed as a constraint")
        elif _is_numpy_bool(other):
            raise TypeError(
                "Comparison with a numpy scalar returned a numpy boolean. "
                "Put the variable on the left, e.g. model += var <= np.float64(34.5)"
            )
        elif isinstance(other, LpAffineExpression):
            if other.sense is not None:
                self.addConstraint(other, name)
            else:
                if self.objective is not None:
                    warnings.warn("Overwriting previously set objective.")
                if name is not None:
                    other.name = name
                self.objective = other
        elif isinstance(other, LpVariable):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression.from_variable(other, name=name)
        elif isinstance(other, (int, float)):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression.from_constant(float(other), name=name)
        else:
            raise TypeError(
                "Can only add LpAffineExpression, LpVariable, numeric, or True objects"
            )
        return self

    def coefficients(
        self, translation: dict[str, str] | None = None
    ) -> list[tuple[str, str, float]]:
        coefs: list[tuple[str, str, float]] = []
        for cst in self.constraints():
            row = cst.name
            if translation is None:
                coefs.extend([(v.name, row, cst[v]) for v in cst])
            else:
                ctr = translation[row]
                coefs.extend([(translation[v.name], ctr, cst[v]) for v in cst])
        return coefs

    def writeMPS(
        self,
        filename: str,
        mpsSense: int = 0,
        rename: bool = False,
        mip: bool = True,
        with_objsense: bool = False,
    ) -> tuple[list[str], list[str], str, list[str]]:
        """
        Writes an mps file from the problem information.

        :param filename: name of the file to write
        :param mpsSense: 0 (use problem sense), 1 minimize, -1 maximize
        :param rename: if True, normalized names (X0000000, C0000000) are used in the file
        :param mip: include integer/binary markers
        :param with_objsense: write OBJSENSE section
        :return: ``(variable_names, constraint_names, objective_name, pulp_names_in_column_order)``
        """
        return mpslp.writeMPS(
            self,
            filename,
            mpsSense=mpsSense,
            rename=rename,
            mip=mip,
            with_objsense=with_objsense,
        )

    def writeLP(
        self,
        filename: str,
        writeSOS: int | bool = 1,
        mip: bool = True,
        max_length: int = 100,
    ) -> list[LpVariable]:
        """
        Write the given Lp problem to a .lp file.

        This function writes the specifications (objective function,
        constraints, variables) of the defined Lp problem to a file.

        :param str filename: the name of the file to be created.
        :return: variables

        Side Effects:
            - The file is created
        """
        return mpslp.writeLP(
            self, filename=filename, writeSOS=writeSOS, mip=mip, max_length=max_length
        )

    def checkDuplicateVars(self) -> None:
        """
        Checks if there are at least two variables with the same name
        :return: 1
        :raises `const.PulpError`: if there ar duplicates
        """
        try:
            self._model.check_duplicate_vars()
        except RuntimeError as e:
            raise const.PulpError(str(e)) from None

    def checkDuplicateConstraints(self) -> None:
        """
        Checks if there are at least two constraints with the same name.
        :raises const.PulpError: if there are duplicates
        """
        try:
            self._model.check_duplicate_constraints()
        except RuntimeError as e:
            raise const.PulpError(str(e)) from None

    def checkLengthVars(self, max_length: int) -> None:
        """
        Checks if variables have names smaller than `max_length`
        :param int max_length: max size for variable name
        :return:
        :raises const.PulpError: if there is at least one variable that has a long name
        """
        try:
            self._model.check_length_vars(max_length)
        except RuntimeError as e:
            raise const.PulpError(str(e)) from None

    def assignVarsVals(self, values: dict[str, float]) -> None:
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_values_by_name(filtered)

    def assignVarsDj(self, values: dict[str, float]) -> None:
        filtered = {k: v for k, v in values.items() if k != "__dummy"}
        self._model.set_variable_djs_by_name(filtered)

    def assignConsPi(self, values: dict[str, float]) -> None:
        self._model.set_constraint_pis_by_name(dict(values))

    def assignConsSlack(self, values: dict[str, float], activity: bool = False) -> None:
        if activity:
            slack_vals: dict[str, float] = {}
            for name, val in values.items():
                rust_c = self._model.get_constraint_by_name(name)
                if rust_c is not None:
                    c = LpConstraint(rust_c)
                    slack_vals[name] = -1 * (c.constant + float(val))
            self._model.set_constraint_slacks_by_name(slack_vals)
        else:
            self._model.set_constraint_slacks_by_name(
                {k: float(v) for k, v in values.items()}
            )

    def get_dummyVar(self) -> LpVariable:
        if self.dummyVar is None:
            self.dummyVar = self.add_variable("__dummy", 0, 0)
        return self.dummyVar

    def fixObjective(self) -> tuple[bool, LpVariable | None]:
        obj = self.objective
        if obj is None:
            self.objective = LpAffineExpression.from_constant(0.0)
            obj = self.objective
            wasNone = True
        else:
            wasNone = False

        if obj is not None and obj.isNumericalConstant():
            dummyVar = self.get_dummyVar()
            expr = obj.copy()
            expr.addInPlace(dummyVar)
            self.objective = expr
        else:
            dummyVar = None

        return wasNone, dummyVar

    def restoreObjective(self, wasNone: bool, dummyVar: LpVariable | None) -> None:
        if wasNone:
            self.objective = None
        elif dummyVar is not None:
            obj = self.objective
            if obj is not None:
                expr = obj.copy()
                expr.subInPlace(dummyVar)
                self.objective = expr

    def solve(self, solver: LpSolver | None = None, **kwargs: Any) -> int:
        """
        Solve the given Lp problem.

        This function changes the problem to make it suitable for solving
        then calls the solver.actualSolve() method to find the solution

        :param solver:  Optional: the specific solver to be used, defaults to the
              default solver.

        Side Effects:
            - The attributes of the problem object are changed in
              :meth:`~pulp.solver.LpSolver.actualSolve()` to reflect the Lp solution
        """

        if not (solver):
            solver = self.solver
        if not (solver):
            solver = LpSolverDefault
        if solver is None:
            raise const.PulpError("No solver available")
        wasNone, dummyVar = self.fixObjective()
        # time it
        self.startClock()
        status = solver.actualSolve(self, **kwargs)
        self.stopClock()
        self.restoreObjective(wasNone, dummyVar)
        self.solver = solver
        return status

    def startClock(self) -> None:
        "initializes properties with the current time"
        self.solutionCpuTime = -clock()
        self.solutionTime = -time()

    def stopClock(self) -> None:
        "updates time wall time and cpu time"
        self.solutionTime += time()
        self.solutionCpuTime += clock()

    def sequentialSolve(
        self,
        objectives: list[LpAffineExpression],
        absoluteTols: list[int] | list[float] | None = None,
        relativeTols: list[int] | list[float] | None = None,
        solver: LpSolver | None = None,
        debug: bool = False,
    ) -> list[int]:
        """
        Solve the given Lp problem with several objective functions.

        This function sequentially changes the objective of the problem
        and then adds the objective function as a constraint

        :param objectives: the list of objectives to be used to solve the problem
        :param absoluteTols: the list of absolute tolerances to be applied to
           the constraints should be +ve for a minimise objective
        :param relativeTols: the list of relative tolerances applied to the constraints
        :param solver: the specific solver to be used, defaults to the default solver.

        """
        # TODO Add a penalty variable to make problems elastic
        # TODO add the ability to accept different status values i.e. infeasible etc

        if not (solver):
            solver = self.solver
        if not (solver):
            solver = LpSolverDefault
        if solver is None:
            raise const.PulpError("No solver available")
        if not (absoluteTols):
            absoluteTols = [0] * len(objectives)
        if not (relativeTols):
            relativeTols = [1] * len(objectives)
        # time it
        self.startClock()
        statuses = []
        for i, (obj, absol, rel) in enumerate(
            zip(objectives, absoluteTols, relativeTols)
        ):
            self.setObjective(obj)
            status = solver.actualSolve(self)
            statuses.append(status)
            if debug:
                self.writeLP(f"{i}Sequence.lp")
            obj_val = value(obj)
            if obj_val is None:
                raise const.PulpError(
                    "Objective has no value after solve; cannot add sequential tolerance constraint"
                )
            if self.sense == const.LpMinimize:
                self += obj <= obj_val * rel + absol, f"Sequence_Objective_{i}"
            elif self.sense == const.LpMaximize:
                self += obj >= obj_val * rel + absol, f"Sequence_Objective_{i}"
        self.stopClock()
        self.solver = solver
        return statuses

    def resolve(self, solver: LpSolver | None = None, **kwargs: Any) -> int:
        """
        Re-solves the problem using the same solver as previously.
        """
        return self.solve(solver=solver, **kwargs)

    def setSolver(self, solver: LpSolver | None = LpSolverDefault) -> None:
        """Sets the Solver for this problem useful if you are using
        resolve
        """
        self.solver = solver

    def numVariables(self) -> int:
        """

        :return: number of variables in model
        """
        return len(self.variables())

    def numConstraints(self) -> int:
        """

        :return: number of constraints in model
        """
        return len(self.constraints())

    def getSense(self) -> int:
        return self.sense

    def assignStatus(self, status: int, sol_status: int | None = None) -> bool:
        """
        Sets the status of the model after solving.
        :param status: code for the status of the model
        :param sol_status: code for the status of the solution
        :return:
        """
        if status not in const.LpStatus:
            raise const.PulpError("Invalid status code: " + str(status))

        if sol_status is not None and sol_status not in const.LpSolution:
            raise const.PulpError("Invalid solution status code: " + str(sol_status))

        self.status = status
        if sol_status is None:
            sol_status = const.LpStatusToSolution.get(
                status, const.LpSolutionNoSolutionFound
            )
        self.sol_status = sol_status
        return True
