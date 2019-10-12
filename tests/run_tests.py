import os, sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
import unittest
from tests import test_amply, test_pulp, test_examples

if __name__ == '__main__':
    # Tests
    runner = unittest.TextTestRunner()
    loader = unittest.TestLoader()
    # we get suite with all PuLP tests
    suite_all = test_pulp.suite()
    # we add Amply tests to the suite
    amply = loader.loadTestsFromTestCase(test_amply.AmplyTest)
    suite_all.addTests(amply)
    # We add examples and docs tests
    docs_examples = loader.loadTestsFromTestCase(test_examples.Examples_DocsTests)
    suite_all.addTests(docs_examples)
    # we run all tests at the same time
    ret = runner.run(suite_all)
    sys.exit(not ret.wasSuccessful())
