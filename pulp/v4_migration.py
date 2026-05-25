"""PuLP 4.0 migration deprecation warnings."""

from __future__ import annotations

import warnings

V4_MIGRATION_WARNINGS = True


def set_v4_migration_warnings(enabled: bool) -> None:
    """Enable or disable PuLP 4.0 migration DeprecationWarnings (default: enabled)."""

    global V4_MIGRATION_WARNINGS
    V4_MIGRATION_WARNINGS = enabled


def v4_deprecation(message: str, stacklevel: int = 2) -> None:
    if V4_MIGRATION_WARNINGS:
        warnings.warn(message, category=DeprecationWarning, stacklevel=stacklevel)
