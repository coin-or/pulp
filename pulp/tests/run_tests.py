import os
import unittest

import pulp


def pulpTestAll():
    all_solvers = pulp.listSolvers(onlyAvailable=False)
    available = pulp.listSolvers(onlyAvailable=True)
    print(f"Available solvers: {available}")
    print(f"Unavailable solvers: {set(all_solvers) - set(available)}")
    runner = unittest.TextTestRunner()
    suite_all = get_test_suite()
    ret = runner.run(suite_all)
    if not ret.wasSuccessful():
        raise pulp.PulpError("Tests Failed")


def get_test_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    # discover relative to this file so that the ``pulptest`` entry point
    # works from an installed package, not only from the repository root
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    top_level_dir = os.path.dirname(os.path.dirname(tests_dir))
    return loader.discover(tests_dir, pattern="test_*.py", top_level_dir=top_level_dir)


if __name__ == "__main__":
    pulpTestAll()
