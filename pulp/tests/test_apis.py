import unittest

from pulp import SCIP_CMD


class ScipTest(unittest.TestCase):
    def testBuildSolveCommand(self):
        scip = SCIP_CMD(options=["-c", "set presolving emphasis aggressive"])

        command, file_options = scip._build_solve_command(
            "tmpLp", "tmpSol", "tmpOptions"
        )

        assert command == [
            scip.path,
            "-s",
            "tmpOptions",
            "-c",
            "set presolving emphasis aggressive",
            "-c",
            'read "tmpLp"',
            "-c",
            "optimize",
            "-c",
            'write solution "tmpSol"',
            "-c",
            "quit",
        ]

        assert file_options == []


class FscipTest(unittest.TestCase):
    def testBuildSolveCommand(self):
        scip = SCIP_CMD(options=["-c", "set presolving emphasis aggressive"])

        command, file_options = scip._build_solve_command(
            "tmpLp", "tmpSol", "tmpOptions"
        )

        assert command == [
            scip.path,
            "-s",
            "tmpOptions",
            "-c",
            "set presolving emphasis aggressive",
            "-c",
            'read "tmpLp"',
            "-c",
            "optimize",
            "-c",
            'write solution "tmpSol"',
            "-c",
            "quit",
        ]

        assert file_options == []


if __name__ == "__main__":
    unittest.main()
