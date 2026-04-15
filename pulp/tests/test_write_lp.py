"""
Tests for :meth:`~pulp.LpProblem.writeLP` (CPLEX LP format).

CPLEX LP treats ASCII space as a token separator in row bodies, so identifiers
(variable, constraint, and objective row labels) must not contain raw spaces.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pulp import LpProblem, _rustcore, const

# Section headers in the order produced by the Rust writer (subset used for checks).
_LP_MAJOR_HEADERS = frozenset(
    {
        "Minimize",
        "Maximize",
        "Subject To",
        "Bounds",
        "Generals",
        "Binaries",
        "SOS",
        "End",
    }
)


def _collect_row_labels_before_colon(text: str) -> list[str]:
    """
    Collect ``name`` from primary LP lines ``name: ...`` (objective, constraints,
    SOS entries). Continuation lines and section headers are skipped.
    """
    labels: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n\r")
        if not line.strip() or line.lstrip().startswith("\\*"):
            continue
        # Continuation lines from the writer start with whitespace.
        if line and line[0] in " \t":
            continue
        stripped = line.strip()
        if stripped in _LP_MAJOR_HEADERS:
            continue
        if ":" not in stripped:
            continue
        before, _after = stripped.split(":", 1)
        if not before:
            continue
        # SOS group header lines look like ``S1::`` / ``S2::``.
        if (
            before == "S1"
            or before == "S2"
            or before.startswith("S1")
            or before.startswith("S2")
        ):
            continue
        labels.append(before)
    return labels


def _assert_cplex_lp_shell(text: str, *, sense_minimize: bool) -> None:
    """Lightweight structural checks aligned with common CPLEX LP files."""
    lines = [ln.rstrip("\r\n") for ln in text.splitlines()]
    assert lines, "LP file must not be empty"
    assert lines[-1].strip() == "End", f"expected last line 'End', got {lines[-1]!r}"
    assert any(ln.strip() == "Subject To" for ln in lines), (
        "missing 'Subject To' section"
    )
    if sense_minimize:
        assert any(ln.strip() == "Minimize" for ln in lines), (
            "missing 'Minimize' header"
        )
    else:
        assert any(ln.strip() == "Maximize" for ln in lines), (
            "missing 'Maximize' header"
        )
    # Opening comment block produced by the writer.
    assert lines[0].lstrip().startswith("\\*"), (
        f"expected leading comment, got {lines[0]!r}"
    )


class WriteLpTest(unittest.TestCase):
    def test_escapes_spaces_in_variable_constraint_and_objective_rows(self) -> None:
        """Spaces in variable names must become underscores in the .lp body."""
        raw_var = "QX9 VAR PART"
        escaped = "QX9_VAR_PART"
        self.assertNotIn(" ", escaped)

        prob = LpProblem("lp_space_escape", const.LpMinimize)
        x = prob.add_variable(raw_var, 0, 3, const.LpInteger)
        self.assertEqual(x.name, escaped)
        prob += (x, "obj row name")
        prob += x >= 1, "row with spaces"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.lp"
            prob.writeLP(str(path))
            body = path.read_text(encoding="utf-8")

        self.assertIn(escaped, body)
        self.assertNotIn(raw_var, body)
        _assert_cplex_lp_shell(body, sense_minimize=True)

        for label in _collect_row_labels_before_colon(body):
            self.assertNotIn(
                " ",
                label,
                f"row label {label!r} must not contain a space (CPLEX LP tokenization)",
            )

    def test_escapes_spaces_in_bounds_generals_binaries(self) -> None:
        raw = "BOUND INT VAR"
        prob = LpProblem("bounds_escape", const.LpMinimize)
        xi = prob.add_variable(raw, 2, 5, const.LpInteger)
        xb = prob.add_variable("bin var z", cat=const.LpBinary)
        prob += xi + xb
        prob += xi + xb <= 1

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bounds.lp"
            prob.writeLP(str(path), mip=True)
            body = path.read_text(encoding="utf-8")

        self.assertEqual(xi.name, "BOUND_INT_VAR")
        self.assertEqual(xb.name, "bin_var_z")
        self.assertIn("BOUND_INT_VAR", body)
        self.assertIn("bin_var_z", body)
        self.assertNotIn(raw, body)
        self.assertNotIn("bin var z", body)
        self.assertRegex(body, r"(?m)^Bounds\s*$")
        self.assertRegex(body, r"(?m)^Generals\s*$")
        self.assertRegex(body, r"(?m)^Binaries\s*$")
        _assert_cplex_lp_shell(body, sense_minimize=True)

        for label in _collect_row_labels_before_colon(body):
            self.assertNotIn(" ", label)

    def test_exported_variables_only_used_columns(self) -> None:
        prob = LpProblem("export_used", const.LpMinimize)
        x = prob.add_variable("x", 0, 1)
        prob.add_variable("y_unused", 0, 1)
        prob += x
        exported = prob.exported_variables()
        self.assertEqual([v.name for v in exported], ["x"])

    def test_sos_section_escapes_variable_names(self) -> None:
        raw = "SOS V NAME"
        prob = LpProblem("sos_escape", const.LpMinimize)
        v1 = prob.add_variable(raw, 0, 1, const.LpBinary)
        v2 = prob.add_variable("t", 0, 1, const.LpBinary)
        prob += v1 + v2
        prob.add_sos_group(_rustcore.SosKind.Sos1, "0", {v1: 1.0, v2: 2.0})

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sos.lp"
            prob.writeLP(str(path), writeSOS=True, mip=True)
            body = path.read_text(encoding="utf-8")

        self.assertEqual(v1.name, "SOS_V_NAME")
        self.assertIn("SOS_V_NAME", body)
        self.assertNotIn(raw, body)
        self.assertRegex(body, r"(?m)^SOS\s*$")
        self.assertRegex(body, r"(?m)^S1::\s*$")
        _assert_cplex_lp_shell(body, sense_minimize=True)

    def test_maximize_and_constraint_sense_tokens(self) -> None:
        prob = LpProblem("max_lp", const.LpMaximize)
        x = prob.add_variable("x", 0, 1)
        prob += x
        prob += x <= 0.5, "c_le"
        prob += x >= 0.1, "c_ge"
        prob += x == 0.25, "c_eq"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "max.lp"
            prob.writeLP(str(path), mip=False)
            body = path.read_text(encoding="utf-8")

        _assert_cplex_lp_shell(body, sense_minimize=False)
        self.assertRegex(body, r"(?m)^c_le:.*<=\s*")
        self.assertRegex(body, r"(?m)^c_ge:.*>=\s*")
        self.assertRegex(body, r"(?m)^c_eq:.*=\s*")

    def test_empty_constraint_uses_escaped_dummy_name(self) -> None:
        prob = LpProblem("empty_row", const.LpMinimize)
        d = prob.get_dummyVar()
        d.name = "dummy var name"
        self.assertEqual(d.name, "dummy_var_name")
        z = prob.add_variable("z", 0, 1)
        prob += z
        prob += 0 * z == 0, "empty row label"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dummy.lp"
            prob.writeLP(str(path), mip=False)
            body = path.read_text(encoding="utf-8")

        self.assertIn("dummy_var_name", body)
        self.assertNotIn("dummy var name", body)
        self.assertRegex(body, r"(?m)^_dummy: 1 dummy_var_name = 0\s*$")

    def test_assign_vars_vals_accepts_lp_escaped_variable_names(self) -> None:
        """``assignVarsVals`` accepts keys matching stored names (normalized at create)."""
        prob = LpProblem("assign_esc", const.LpMinimize)
        x = prob.add_variable("my var", 0, 1)
        self.assertEqual(x.name, "my_var")
        prob += x
        prob.assignVarsVals({"my_var": 0.75})
        self.assertAlmostEqual(x.value(), 0.75)

    def test_assign_vars_dj_accepts_lp_escaped_variable_names(self) -> None:
        prob = LpProblem("assign_dj", const.LpMinimize)
        x = prob.add_variable("col name", 0, 1)
        self.assertEqual(x.name, "col_name")
        prob += x
        prob.assignVarsDj({"col_name": 0.25})
        self.assertAlmostEqual(x.dj, 0.25)

    def test_coin_readsol_mps_maps_lp_file_column_names_to_model_names(self) -> None:
        """CBC solution lines use names from the .lp file (escaped), not Python ``v.name``."""
        from pulp.apis.coin_api import COIN_CMD

        prob = LpProblem("cbc_map", const.LpMinimize)
        x = prob.add_variable("x y", 0, 1)
        self.assertEqual(x.name, "x_y")
        prob += x
        prob += x <= 1, "c1"

        with tempfile.TemporaryDirectory() as tmp:
            sol_path = Path(tmp) / "fake.sol"
            # Minimal CBC-style solution snippet (column section uses LP names).
            sol_path.write_text(
                "Optimal - objective value 0\n"
                "    0 x_y            0.5                     0\n",
                encoding="utf-8",
            )
            status, values, dj, pi, slacks, sol_status = COIN_CMD(
                msg=False
            ).readsol_MPS(
                str(sol_path),
                prob,
                variableNames=["x_y"],
                constraintNames=["c1"],
            )
        self.assertEqual(values["x_y"], 0.5)
        self.assertEqual(dj["x_y"], 0.0)

    def test_duplicate_vars_after_normalization_detected_on_write_lp(self) -> None:
        """``a b`` and ``a_b`` both store as ``a_b``; duplicate check runs on ``writeLP``."""
        prob = LpProblem("dup_norm", const.LpMinimize)
        x1 = prob.add_variable("a b", 0, 1)
        prob.add_variable("a_b", 0, 1)
        prob += x1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.lp"
            with self.assertRaises(const.PulpError):
                prob.writeLP(str(path))


if __name__ == "__main__":
    unittest.main()
