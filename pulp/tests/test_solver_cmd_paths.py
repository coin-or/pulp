"""Regression tests for solver command lines when paths contain spaces.

Issue #811: ``GUROBI_CMD``, ``MIPCL_CMD``, ``CHOCO_CMD`` and ``COIN_CMD``
built their command line as one string and split it on whitespace before
calling the solver, so a ``TMPDIR`` (or solver path) containing a space
broke every file path into fragments and the solve failed.

These tests run each solver against a fake executable that records the
``argv`` it receives and writes a minimal valid solution file, with the
temporary directory (and the fake executables themselves) placed under a
directory whose name contains spaces. No real solver is needed.
"""

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import pulp.apis as solvers
from pulp import LpProblem
from pulp import constants as const

FAKE_PREAMBLE = """\
import json
import os
import sys

with open(os.environ["FAKE_ARGV_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
"""

FAKE_GUROBI = FAKE_PREAMBLE + """\

sol = next(a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("ResultFile="))
with open(sol, "w") as f:
    f.write("# Objective value = -4\\n")
    f.write("x 0\\n")
    f.write("y -1\\n")
"""

FAKE_MIPCL = FAKE_PREAMBLE + """\

sol = sys.argv[sys.argv.index("-solfile") + 1]
with open(sol, "w") as f:
    f.write("objective -4\\n")
    f.write("x 0\\n")
    f.write("y -1\\n")
"""

FAKE_CBC = FAKE_PREAMBLE + """\

model = sys.argv[1]
names = []
in_columns = False
with open(model) as f:
    for line in f:
        if line.startswith("COLUMNS"):
            in_columns = True
            continue
        if in_columns:
            if not line.startswith(" "):
                break
            tokens = line.split()
            if tokens and tokens[0] != "MARKER" and tokens[0] not in names:
                names.append(tokens[0])
sol = sys.argv[sys.argv.index("-solution") + 1]
with open(sol, "w") as f:
    f.write("Optimal - objective value    -4.00000000\\n")
    for i, name in enumerate(names):
        f.write(f"{i:>7} {name} {0:>15} {0:>23}\\n")
"""

FAKE_JAVA = FAKE_PREAMBLE + """\

print("s OPTIMUM FOUND")
print("x 0")
print("y -1")
"""


def _write_executable(directory, name, source):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write("#!" + sys.executable + "\n")
        f.write(textwrap.dedent(source))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


@unittest.skipUnless(os.name == "posix", "fake executables need a POSIX shell")
class SolverCmdPathsWithSpacesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # the whole point: every path below lives under a spaced directory
        self.spaced = os.path.join(self._tmp.name, "dir with spaces")
        os.makedirs(self.spaced)
        self.argv_log = os.path.join(self.spaced, "argv.log")
        env = mock.patch.dict(
            os.environ,
            {"TMPDIR": self.spaced, "FAKE_ARGV_LOG": self.argv_log},
        )
        env.start()
        self.addCleanup(env.stop)

    def build_problem(self):
        prob = LpProblem("test_spaces", const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        prob += x + 4 * y
        prob += x + y <= 5
        return prob

    def recorded_argv(self):
        with open(self.argv_log) as f:
            return [json.loads(line) for line in f]

    def assert_paths_not_split(self, argv):
        # every temporary-file argument must be one whole spaced path;
        # a fragmented path shows up as an element that is only part of it
        # "LogFile=" is excluded here: that path is minted by
        # tempfile.mkstemp in LpSolver_CMD.capture_log, not from the solver
        # tmpDir these tests exercise, so it is not asserted to live under
        # the spaced dir (test_gurobi_cmd checks it arrives whole instead)
        tmp_args = [a for a in argv if "-pulp." in a and not a.startswith("LogFile=")]
        self.assertTrue(tmp_args, f"no temporary paths in argv: {argv}")
        for arg in tmp_args:
            path = arg.split("=", 1)[-1]  # strip a leading "ResultFile=" etc.
            self.assertTrue(
                path.startswith(self.spaced),
                f"path argument was split: {arg!r} not under {self.spaced!r}",
            )

    def test_gurobi_cmd(self):
        fake = _write_executable(self.spaced, "gurobi_cl", FAKE_GUROBI)
        prob = self.build_problem()
        stats = prob.solve(solvers.GUROBI_CMD(path=fake, msg=False))
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertTrue(argv[-1].endswith("-pulp.lp"))
        self.assertIn(f"ResultFile={argv[-1].replace('.lp', '.sol')}", argv)
        # the capture log path (from LpSolver_CMD.capture_log) is not under
        # the spaced dir, but it must still arrive as one whole element
        log_args = [a for a in argv if a.startswith("LogFile=")]
        self.assertEqual(len(log_args), 1)
        self.assertTrue(log_args[0].endswith("-pulp.log"))
        # with a time limit and a warm start, TimeLimit is a single
        # "key=value" token and InputFile= carries the whole spaced path
        prob = self.build_problem()
        prob.variables()[0].setInitialValue(1)
        stats = prob.solve(
            solvers.GUROBI_CMD(path=fake, msg=False, timeLimit=99, warmStart=True)
        )
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        argv = self.recorded_argv()[1]
        self.assert_paths_not_split(argv)
        self.assertIn("TimeLimit=99", argv)
        input_args = [a for a in argv if a.startswith("InputFile=")]
        self.assertEqual(len(input_args), 1)
        self.assertTrue(input_args[0].split("=", 1)[1].startswith(self.spaced))
        self.assertTrue(input_args[0].endswith("-pulp.mst"))

    def test_mipcl_cmd(self):
        fake = _write_executable(self.spaced, "mipcl", FAKE_MIPCL)
        prob = self.build_problem()
        stats = prob.solve(
            solvers.MIPCL_CMD(
                path=fake, msg=False, timeLimit=30, options=["-threads 4"]
            )
        )
        # MIPCL solution files do not state optimality, so a completed
        # solve with a solution reads back as Stopped (see MIPCL_CMD.readsol)
        self.assertEqual(stats.status, const.LpSolveStatus.Stopped)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertTrue(argv[0].endswith("-pulp.mps"))
        sol = argv[argv.index("-solfile") + 1]
        self.assertTrue(sol.endswith("-pulp.sol"))
        self.assertEqual(argv[argv.index("-time") + 1], "30")
        # a multi-word option fragment keeps its historical tokenisation:
        # "-threads" and "4" are separate tokens, not one "-threads 4"
        self.assertNotIn("-threads 4", argv)
        self.assertEqual(argv[argv.index("-threads") + 1], "4")

    def test_coin_cmd(self):
        fake = _write_executable(self.spaced, "cbc", FAKE_CBC)
        prob = self.build_problem()
        stats = prob.solve(solvers.COIN_CMD(path=fake, msg=False))
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertTrue(argv[0].endswith("-pulp.mps"))
        sol = argv[argv.index("-solution") + 1]
        self.assertTrue(sol.endswith("-pulp.sol"))
        # warm start, presolve and cuts: the -mips path is one whole spaced
        # argument and the switches arrive as separate tokens
        prob = self.build_problem()
        for var in prob.variables():
            var.setInitialValue(0)
        stats = prob.solve(
            solvers.COIN_CMD(
                path=fake, msg=False, warmStart=True, presolve=True, cuts=False
            )
        )
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        argv = self.recorded_argv()[1]
        self.assert_paths_not_split(argv)
        mips = argv[argv.index("-mips") + 1]
        self.assertTrue(mips.startswith(self.spaced))
        self.assertTrue(mips.endswith("-pulp.mst"))
        self.assertEqual(argv[argv.index("-presolve") + 1], "on")
        self.assertEqual(argv[argv.index("-cuts") + 1], "off")

    def test_choco_cmd(self):
        _write_executable(self.spaced, "java", FAKE_JAVA)
        jar = os.path.join(self.spaced, "choco parser.jar")
        with open(jar, "w") as f:
            f.write("")
        prob = self.build_problem()
        with mock.patch.dict(
            os.environ, {"PATH": self.spaced + os.pathsep + os.environ["PATH"]}
        ):
            stats = prob.solve(
                solvers.CHOCO_CMD(
                    path=jar, msg=False, timeLimit=60, options=[("-fs", "1")]
                )
            )
        self.assertEqual(stats.status, const.LpSolveStatus.Optimal)
        (argv,) = self.recorded_argv()
        self.assert_paths_not_split(argv)
        self.assertEqual(argv[argv.index("-cp") + 1], jar)
        self.assertTrue(argv[-1].endswith("-pulp.mps"))
        # the time limit is the token after -limit, and each option
        # key/value pair arrives as two separate tokens
        self.assertEqual(argv[argv.index("-limit") + 1], "[-60s]")
        self.assertEqual(argv[argv.index("-fs") + 1], "1")


if __name__ == "__main__":
    unittest.main()
