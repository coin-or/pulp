import unittest

from pulp import SCIP_CMD, FSCIP_CMD


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
        ], f"Command is not equal: {command}"

        assert file_options == [], f"File options are not equal: {file_options}"


class FscipTest(unittest.TestCase):
    def testBuildSolveCommand(self):
        fscip = FSCIP_CMD(options=["-sl", "foo"])

        command, file_options, file_parameters = fscip._build_solve_command(
            "tmpLp", "tmpSol", "tmpOptions", "tmpParams"
        )

        assert command == [
            fscip.path,
            "tmpParams",
            "tmpLp",
            "-s",
            "tmpOptions",
            "-fsol",
            "tmpSol",
            "-sl",
            "foo",
        ], f"Command is not equal: {command}"

        assert file_options == [], f"File options are not equal: {file_options}"
        assert file_parameters == [
            "NoPreprocessingInLC = TRUE"
        ], f"File parameters are not equal: {file_parameters}"


if __name__ == "__main__":
    unittest.main()
