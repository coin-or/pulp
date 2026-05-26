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
    return loader.discover("pulp/tests", pattern="test_*.py", top_level_dir=".")


if __name__ == "__main__":
    pulpTestAll()
