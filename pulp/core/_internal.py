"""Shared helpers for pulp.core (Rust/category/sense mapping)."""

from __future__ import annotations

import logging

from .. import _rustcore
from .. import constants as const

log = logging.getLogger("pulp.pulp")


def _is_numpy_bool(obj: object) -> bool:
    """Return True if obj is a numpy boolean scalar (e.g. from np.float64(3) >= var)."""
    t = type(obj)
    return getattr(t, "__name__", "") in ("bool_", "bool8", "bool") and (
        getattr(t, "__module__", "") or ""
    ).startswith("numpy")


def _rust_cat_to_const(rust_cat: _rustcore.Category) -> str:
    if rust_cat == _rustcore.Category.Continuous:
        return const.LpContinuous
    if rust_cat == _rustcore.Category.Integer:
        return const.LpInteger
    if rust_cat == _rustcore.Category.Binary:
        return const.LpInteger  # Binary as Integer 0-1
    return const.LpContinuous


def _const_to_rust_cat(const_str: str) -> _rustcore.Category:
    if const_str == const.LpBinary:
        return _rustcore.Category.Binary
    if const_str == const.LpInteger:
        return _rustcore.Category.Integer
    return _rustcore.Category.Continuous


def _rust_sense_to_const(rsense: _rustcore.Sense) -> int:
    if rsense == _rustcore.Sense.LessEqual:
        return const.LpConstraintLE
    if rsense == _rustcore.Sense.GreaterEqual:
        return const.LpConstraintGE
    return const.LpConstraintEQ


def _const_to_rust_sense(sense_int: int) -> _rustcore.Sense:
    if sense_int == const.LpConstraintLE:
        return _rustcore.Sense.LessEqual
    if sense_int == const.LpConstraintGE:
        return _rustcore.Sense.GreaterEqual
    return _rustcore.Sense.Equal
