"""Unit tests for coin_cmd solver."""

import os
import re
from typing import ClassVar

import pulp.apis as solvers
from pulp import LpProblem, lpSum
from pulp import constants as const
from pulp.constants import PulpError
from pulp.tests.solver_common import (
    FAKE_SOLVER_ARGV_PREAMBLE,
    BaseSolverTest,
    PulpTestConfig,
    SolverCmdPathsWithSpacesTestCase,
    _status,
    pulpTestCheck,
    write_fake_executable,
)


class COIN_CMD_CBCOptionsTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COIN_CMD

    @staticmethod
    def read_command_line_from_log_file(logPath):
        """
        Read from log file the command line executed.
        """
        with open(logPath) as fp:
            for row in fp.readlines():
                if row.startswith("command line "):
                    return row
        raise ValueError(f"Unable to find the command line in {logPath}")

    @staticmethod
    def extract_option_from_command_line(
        command_line, option, prefix="-", grp_pattern="[a-zA-Z]+"
    ):
        """
        Extract option value from command line string.

        :param command_line: str that we extract the option value from
        :param option: str representing the option name (e.g., presolve, sec, etc)
        :param prefix: str (default: '-')
        :param grp_pattern: str (default: '[a-zA-Z]+') - regex to capture option value

        :return: option value captured (str); otherwise, None

        example:

        >>> cmd = "cbc model.mps -presolve off -timeMode elapsed -branch"
        >>> COIN_CMD_CBCOptionsTest.extract_option_from_command_line(cmd, "presolve")
        'off'

        >>> cmd = "cbc model.mps -strong 101 -timeMode elapsed -branch"
        >>> COIN_CMD_CBCOptionsTest.extract_option_from_command_line(cmd, "strong", grp_pattern="\\d+")
        '101'
        """
        pattern = re.compile(rf"{prefix}{option}\s+({grp_pattern})\s*")
        m = pattern.search(command_line)
        if not m:
            print(f"{option} not found in {command_line}")
            return None
        option_value = m.groups()[0]
        return option_value

    def test_presolve_off(self):
        """
        Test if setting presolve=False in COIN_CMD adds presolve off to the
        command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["presolve"] = False
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {x: 4, y: -1, z: 6, w: 0},
        )
        if not os.path.exists(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        if not os.path.getsize(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        # Extract option_value from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="presolve"
        )
        self.assertEqual("off", option_value)

    def test_cuts_on(self):
        """
        Test if setting cuts=True in COIN_CMD adds "gomory on knapsack on
        probing on" to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["cuts"] = True
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {x: 4, y: -1, z: 6, w: 0},
        )
        if not os.path.exists(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        if not os.path.getsize(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        # Extract option values from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        gomory_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="gomory"
        )
        knapsack_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="knapsack", prefix=""
        )
        probing_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="probing", prefix=""
        )
        self.assertListEqual(
            ["on", "on", "on"], [gomory_value, knapsack_value, probing_value]
        )

    def test_cuts_off(self):
        """
        Test if setting cuts=False adds cuts off to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["cuts"] = False
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {x: 4, y: -1, z: 6, w: 0},
        )
        if not os.path.exists(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        if not os.path.getsize(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        # Extract option value from the command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="cuts"
        )
        self.assertEqual("off", option_value)

    def test_strong(self):
        """
        Test if setting strong=10 adds strong 10 to the command line.
        """
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["strong"] = 10
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {x: 4, y: -1, z: 6, w: 0},
        )
        if not os.path.exists(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        if not os.path.getsize(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        # Extract option value from command line
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="strong", grp_pattern="\\d+"
        )
        self.assertEqual("10", option_value)

    def test_random_seed(self):
        """
        Test if setting randomSeed=20 adds randomSeed 20 to the command line.
        """
        # randomSeed is a public constructor argument that flows into optionsDict.
        self.assertEqual(20, solvers.COIN_CMD(randomSeed=20).optionsDict["randomSeed"])
        name = self._testMethodName
        prob = LpProblem(name, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        logFilename = name + ".log"
        self.solver.optionsDict["logPath"] = logFilename
        self.solver.optionsDict["randomSeed"] = 20
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {x: 4, y: -1, z: 6, w: 0},
        )
        if not os.path.exists(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        if not os.path.getsize(logFilename):
            raise PulpError(f"Test failed for solver: {self.solver}")
        command_line = COIN_CMD_CBCOptionsTest.read_command_line_from_log_file(
            logFilename
        )
        option_value = COIN_CMD_CBCOptionsTest.extract_option_from_command_line(
            command_line, option="randomSeed", grp_pattern="\\d+"
        )
        self.assertEqual("20", option_value)


class COIN_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.COIN_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_infeasible": PulpTestConfig(
            okstatus=_status("Infeasible"),
            solve_kwargs={"use_mps": False},
        ),
        "test_longname_lp": PulpTestConfig(skip=False, solve_kwargs={"use_mps": False}),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_integer_infeasible": PulpTestConfig(
            okstatus=_status("Infeasible", "Undefined")
        ),
    }

    def test_infeasible(self):
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        w = prob.add_variable("w", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += (lpSum([v for v in [x] if False]) >= 5, "c1")
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"
        prob += w >= 0, "c4"
        self._apply_pulp_check(prob, sol={x: 4, y: -1, z: 6, w: 0})

    def test_add_variable_dicts_tuple_indices_mps_path(self):
        """Tuple keys from a list of indices build names with punctuation/spaces; CBC MPS path must run."""
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        keys = [(0, 0), (0, 1), (1, 0)]
        x = prob.add_variable_dicts("flow", keys, lowBound=0, cat=const.LpContinuous)
        prob += lpSum(x[k] for k in keys)
        prob += lpSum(x[k] for k in keys) >= 1, "cover"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {
                x[(0, 0)]: 1.0,
                x[(0, 1)]: 0.0,
                x[(1, 0)]: 0.0,
            },
            objective=1.0,
        )

    def test_add_variable_dicts_tuple_indices_mip_mps_path(self):
        """Integer variables with tuple-index dicts use MPS integer markers; COIN_CMD must accept."""
        prob = LpProblem(self._testMethodName, const.LpMinimize)
        keys = [(1, "east"), (2, "west")]
        y = prob.add_variable_dicts("open", keys, cat=const.LpBinary)
        prob += y[(1, "east")] + 2 * y[(2, "west")]
        prob += y[(1, "east")] + y[(2, "west")] >= 1, "pick_one"
        pulpTestCheck(
            prob,
            self.solver,
            [const.LpSolveStatus.Optimal],
            {y[(1, "east")]: 1.0, y[(2, "west")]: 0.0},
            objective=1.0,
        )


FAKE_CBC = FAKE_SOLVER_ARGV_PREAMBLE + """\

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


class COIN_CMDPathsWithSpacesTest(SolverCmdPathsWithSpacesTestCase):
    def test_paths_with_spaces(self):
        fake = write_fake_executable(self.spaced, "cbc", FAKE_CBC)
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
