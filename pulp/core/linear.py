from __future__ import annotations

import array
import math
from collections.abc import Iterable
from typing import Any

from .. import constants as const
from .lp_affine_expression import LpAffineExpression
from .lp_variable import LpVariable


def lpSum(
    vector: (
        Iterable[LpAffineExpression | LpVariable | int | float]
        | Iterable[tuple[LpVariable, float]]
        | int
        | float
        | LpVariable
    ),
) -> LpAffineExpression:
    """
    Calculate the sum of a list of linear expressions

    :param vector: A list of linear expressions
    """
    return LpAffineExpression.empty().addInPlace(vector)


def lpSum_vars(variables: Iterable[LpVariable]) -> LpAffineExpression:
    """
    Sum of variables with coefficient 1 each, using a Rust batch path.

    All variables must belong to the same :class:`LpProblem` / model.
    """
    vs = list(variables)
    if not vs:
        return LpAffineExpression.empty()
    ptr = vs[0]._var.model_identity()
    for w in vs[1:]:
        if w._var.model_identity() != ptr:
            raise const.PulpError(
                "lpSum_vars: all variables must belong to the same model"
            )
    ids = array.array("Q")
    ids.extend(v.id for v in vs)
    ones = array.array("d", [1.0]) * len(ids)
    model = vs[0]._var.containing_model()
    e = LpAffineExpression.empty()
    e._expr.add_term_ids_coeffs(model, ids, ones)
    return e


def lpSum_vars_coefs(pairs: Iterable[tuple[LpVariable, float]]) -> LpAffineExpression:
    """
    Sum of ``coeff * var`` terms using a Rust batch path.

    All variables must belong to the same model. Coefficients must be finite.
    """
    plist = list(pairs)
    if not plist:
        return LpAffineExpression.empty()
    ptr = plist[0][0]._var.model_identity()
    ids = array.array("Q")
    coeffs = array.array("d")
    for v, c in plist:
        if v._var.model_identity() != ptr:
            raise const.PulpError(
                "lpSum_vars_coefs: all variables must belong to the same model"
            )
        if not math.isfinite(c):
            raise const.PulpError(
                f"lpSum_vars_coefs: coefficient must be finite, got {c!r}"
            )
        ids.append(v.id)
        coeffs.append(float(c))
    model = plist[0][0]._var.containing_model()
    e = LpAffineExpression.empty()
    e._expr.add_term_ids_coeffs(model, ids, coeffs)
    return e


def _vector_like(obj: object) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, LpAffineExpression)


def lpDot(v1: Any, v2: Any) -> LpAffineExpression:
    """Calculate the dot product of two lists of linear expressions"""
    if not _vector_like(v1) and not _vector_like(v2):
        return v1 * v2
    elif not _vector_like(v1):
        return lpDot([v1] * len(v2), v2)
    elif not _vector_like(v2):
        return lpDot(v1, [v2] * len(v1))
    else:
        return lpSum([lpDot(e1, e2) for e1, e2 in zip(v1, v2)])
