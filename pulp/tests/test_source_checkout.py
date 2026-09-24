"""
Tests that only make sense in a source checkout: they read the docs and
``pyproject.toml`` next to the package, and skip when those are not there.
"""

from __future__ import annotations

import os
import tomllib
import unittest

import pulp

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC_SOURCE = os.path.join(REPO_ROOT, "doc", "source")
PYPROJECT = os.path.join(REPO_ROOT, "pyproject.toml")


def toctree_entries(path: str) -> list[str]:
    """The documents listed in the ``toctree`` directives of an rst file."""
    entries = []
    in_toctree = False
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith(".. toctree::"):
                in_toctree = True
                continue
            if not in_toctree or not stripped:
                continue
            if not line[0].isspace():
                in_toctree = False
                continue
            if stripped.startswith(":"):
                continue
            # "Title <path>" entries
            if stripped.endswith(">") and "<" in stripped:
                stripped = stripped[stripped.rindex("<") + 1 : -1]
            entries.append(stripped)
    return entries


class DocsTest(unittest.TestCase):
    def setUp(self):
        if not os.path.isdir(DOC_SOURCE):
            self.skipTest("docs not available")

    def test_toctree_entries_exist(self):
        missing = []
        for folder, _, files in os.walk(DOC_SOURCE):
            for name in files:
                if not name.endswith(".rst"):
                    continue
                path = os.path.join(folder, name)
                for entry in toctree_entries(path):
                    if "*" in entry:
                        continue
                    if entry.startswith("/"):
                        target = os.path.join(DOC_SOURCE, entry.lstrip("/"))
                    else:
                        target = os.path.join(folder, entry)
                    if not os.path.isfile(target + ".rst"):
                        missing.append(f"{os.path.relpath(path, DOC_SOURCE)}: {entry}")
        self.assertEqual(missing, [])


class VersionTest(unittest.TestCase):
    def test_version_matches_pyproject(self):
        # a stale *.egg-info or dist-info left in the checkout would shadow the
        # installed metadata and report an old version
        if not os.path.isfile(PYPROJECT):
            self.skipTest("pyproject.toml not available")
        with open(PYPROJECT, "rb") as f:
            expected = tomllib.load(f)["project"]["version"]
        self.assertEqual(pulp.__version__, expected)


if __name__ == "__main__":
    unittest.main()
