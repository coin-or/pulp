import unittest

import pulp
from pulp.tests import test_examples, test_gurobipy_env, test_pulp, test_sparse


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


def get_test_suite(test_docs: bool = False) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite_all = unittest.TestSuite()

    suite_all.addTests(loader.loadTestsFromModule(test_pulp))
    suite_all.addTests(loader.loadTestsFromModule(test_sparse))
    suite_all.addTests(loader.loadTestsFromModule(test_gurobipy_env))

    # We add examples and docs tests
    if test_docs:
        suite_all.addTests(
            loader.loadTestsFromTestCase(test_examples.Examples_DocsTests)
        )

    return suite_all


if __name__ == "__main__":
    pulpTestAll(test_docs=False)
