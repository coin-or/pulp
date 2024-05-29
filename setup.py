#!/usr/bin/env/python
"""
Setup script for PuLP added by Stuart Mitchell 2007
Copyright 2007 Stuart Mitchell
"""
from typing import Any, Dict
from setuptools import setup

readme_name = "README.rst"
Description = open(readme_name).read()

# read the version number safely from the constants.py file
version_dict: Dict[str, Any] = {}
exec(open("pulp/constants.py").read(), version_dict)
VERSION = version_dict["VERSION"]

with open(readme_name) as fh:
    long_description = fh.read()

setup(
    name="PuLP",
    version=VERSION,
    description="PuLP is an LP modeler written in python. PuLP can generate MPS or LP files and call GLPK, COIN CLP/CBC, CPLEX, and GUROBI to solve linear problems.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    keywords=["Optimization", "Linear Programming", "Operations Research"],
    author="J.S. Roy and S.A. Mitchell and F. Peschiera",
    author_email="pulp@stuartmitchell.com",
    url="https://github.com/coin-or/pulp",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Topic :: Scientific/Engineering :: Mathematics",
    ],
    python_requires=">=3.7",
    # need the cbc directories here as the executable bit is set
    packages=[
        "pulp",
        "pulp.solverdir",
        "pulp.solverdir.cbc.linux.32",
        "pulp.solverdir.cbc.linux.64",
        "pulp.solverdir.cbc.linux.arm64",
        "pulp.solverdir.cbc.win.32",
        "pulp.solverdir.cbc.win.64",
        "pulp.solverdir.cbc.osx.64",
    ],
    package_data={
        "pulp.solverdir.cbc.linux.32": ["*", "*.*"],
        "pulp.solverdir.cbc.linux.64": ["*", "*.*"],
        "pulp.solverdir.cbc.linux.arm64": ["*", "*.*"],
        "pulp.solverdir.cbc.win.32": ["*", "*.*"],
        "pulp.solverdir.cbc.win.64": ["*", "*.*"],
        "pulp.solverdir.cbc.osx.64": ["*", "*.*"],
    },
    include_package_data=True,
    install_requires=[],
    entry_points=(
        """
      [console_scripts]
      pulptest = pulp.tests.run_tests:pulpTestAll
      """
    ),
    test_suite="pulp.tests.run_tests.get_test_suite",
)
