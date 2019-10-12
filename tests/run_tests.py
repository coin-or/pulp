import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
import unittest
from tests.test_amply import AmplyTest
from tests.test_pulp import suite, TestLoaderWithKwargs

if __name__ == '__main__':
    # Tests
    runner = unittest.TextTestRunner(verbosity=0)
    loader = TestLoaderWithKwargs()
    # we get suite with all PuLP tests
    suite_all = suite()
    # we add Amply tests to the suite
    tests = loader.loadTestsFromTestCase(AmplyTest)
    suite_all.addTests(tests)
    # we run all tests at the same time
    runner.run(suite_all)