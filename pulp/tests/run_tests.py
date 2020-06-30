import unittest
import pulp
from pulp.tests import test_amply, test_pulp, test_examples

def pulpTestAll(test_docs=False):
    runner = unittest.TextTestRunner()
    suite_all = get_test_suit(test_docs)
    # we run all tests at the same time
    ret = runner.run(suite_all)
    if not ret.wasSuccessful():
        raise pulp.PulpError("Tests Failed")

def get_test_suit(test_docs=False):
     # Tests
    loader = unittest.TestLoader()
    # we get suite with all PuLP tests
    suite_all = test_pulp.suite()
    # we add Amply tests to the suite
    amply = loader.loadTestsFromTestCase(test_amply.AmplyTest)
    suite_all.addTests(amply)
    # We add examples and docs tests
    if test_docs:
        docs_examples = loader.loadTestsFromTestCase(test_examples.Examples_DocsTests)
        suite_all.addTests(docs_examples)
    return suite_all

if __name__ == '__main__':
    pulpTestAll(test_docs=False)
