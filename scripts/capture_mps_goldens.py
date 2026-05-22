"""One-shot helper to (re)generate MPS golden fixtures under pulp/tests/fixtures/mps/."""

from pathlib import Path

from pulp import LpBinary, LpInteger, LpMaximize, LpMinimize, LpProblem

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "pulp" / "tests" / "fixtures" / "mps"


def _write_continuous(path: Path) -> None:
    prob = LpProblem("continuous", LpMinimize)
    x = prob.add_variable("x", 0, 4)
    y = prob.add_variable("y", -1, 1)
    z = prob.add_variable("z", 0)
    prob += x + 4 * y + 9 * z, "obj"
    prob += x + y <= 5, "c1"
    prob += x + z >= 10, "c2"
    prob += -y + z == 7, "c3"
    prob.writeMPS(str(path), mip=False)


def _write_integer(path: Path) -> None:
    prob = LpProblem("integer", LpMinimize)
    x = prob.add_variable("x", 0, 4)
    y = prob.add_variable("y", -1, 1)
    z = prob.add_variable("z", 0, None, LpInteger)
    prob += 1.1 * x + 4.1 * y + 9.1 * z, "obj"
    prob += x + y <= 5, "c1"
    prob += x + z >= 10, "c2"
    prob += -y + z == 7.5, "c3"
    prob.writeMPS(str(path), mip=True)


def _write_binary(path: Path) -> None:
    prob = LpProblem("binary", LpMaximize)
    dummy = prob.add_variable("dummy")
    c1 = prob.add_variable("c1", 0, 1, LpBinary)
    c2 = prob.add_variable("c2", 0, 1, LpBinary)
    prob += dummy
    prob += c1 + c2 == 2
    prob += c1 <= 0
    prob.writeMPS(str(path), mip=True)


def _write_rename(path: Path) -> None:
    prob = LpProblem("rename", LpMinimize)
    x = prob.add_variable("x", 0, 1, LpInteger)
    y = prob.add_variable("y", 0, 1, LpInteger)
    prob += x + 2 * y, "obj"
    prob += x + y <= 1, "c1"
    prob += x - y >= 0, "c2"
    prob.writeMPS(str(path), rename=True, mip=True)


def _write_objsense_max(path: Path) -> None:
    prob = LpProblem("objsense_max", LpMaximize)
    x = prob.add_variable("x", 0, 4)
    y = prob.add_variable("y", -1, 1)
    prob += x + 4 * y, "obj"
    prob += x + y <= 5, "c1"
    prob += x >= 0, "c2"
    prob.writeMPS(str(path), with_objsense=True, mip=False)


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = {
        "continuous.mps": _write_continuous,
        "integer.mps": _write_integer,
        "binary.mps": _write_binary,
        "rename.mps": _write_rename,
        "objsense_max.mps": _write_objsense_max,
    }
    for name, writer in scenarios.items():
        out = FIXTURE_DIR / name
        writer(out)
        print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
