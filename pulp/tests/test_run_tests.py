import os
import tempfile
import unittest

from pulp.tests.run_tests import get_test_suite


class GetTestSuiteTest(unittest.TestCase):
    def test_discovers_tests_from_any_working_directory(self) -> None:
        # pulptest is usually run from outside the repository
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                suite = get_test_suite()
            finally:
                os.chdir(cwd)
        self.assertGreater(suite.countTestCases(), 0)


if __name__ == "__main__":
    unittest.main()
