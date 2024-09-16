import unittest
import pulp
from pulp.tests import test_pulp, test_examples, test_gurobipy_env


def pulpTestAll(test_docs=False):
    all_solvers = pulp.listSolvers(onlyAvailable=False)
    available = pulp.listSolvers(onlyAvailable=True)
    print(f"Available solvers: {available}")
    print(f"Unavailable solvers: {set(all_solvers) - set(available)}")
    runner = unittest.TextTestRunner()
    suite_all = get_test_suite(test_docs)
    # we run all tests at the same time
    ret = runner.run(suite_all)
    if not ret.wasSuccessful():
        raise pulp.PulpError("Tests Failed")


def get_test_suite(test_docs=False):
    # Tests
    loader = unittest.TestLoader()
    suite_all = unittest.TestSuite()
    # we get suite with all PuLP tests
    pulp_solver_tests = loader.loadTestsFromModule(test_pulp)
    suite_all.addTests(pulp_solver_tests)
    # Add tests for gurobipy env
    gurobipy_env = loader.loadTestsFromModule(test_gurobipy_env)
    suite_all.addTests(gurobipy_env)
    # We add examples and docs tests
    if test_docs:
        docs_examples = loader.loadTestsFromTestCase(test_examples.Examples_DocsTests)
        suite_all.addTests(docs_examples)
    return suite_all


if __name__ == "__main__":
    pulpTestAll(test_docs=False)
