#!/usr/bin/env/python
"""
Setup script for PuLP added by Stuart Mitchell 2007
Copyright 2007 Stuart Mitchell
"""
from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup

Description = open('README').read()

License = open('LICENSE').read()

Version = open('VERSION').read().strip()

setup(name="PuLP",
      version=Version,
      description="""
PuLP is an LP modeler written in python. PuLP can generate MPS or LP files
and call GLPK, COIN CLP/CBC, CPLEX, and GUROBI to solve linear
problems.
""",
      long_description = Description,
      license = License,
      keywords = ["Optimization", "Linear Programming", "Operations Research"],
      author="J.S. Roy and S.A. Mitchell",
      author_email="s.mitchell@auckland.ac.nz",
      url="http://pulp-or.googlecode.com/",
      classifiers = ['Development Status :: 5 - Production/Stable',
                     'Environment :: Console',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Natural Language :: English',
                     'Programming Language :: Python',
                     'Topic :: Scientific/Engineering :: Mathematics',
      ],
      #ext_modules = [pulpCOIN],
      package_dir={'':'src'},
      packages = ['pulp', 'pulp.solverdir'],
      package_data = {'pulp' : ["AUTHORS","LICENSE",
                                "pulp.cfg.linux",
                                "pulp.cfg.win",
                                "LICENSE.CoinMP.txt",
                                "AUTHORS.CoinMP.txt",
                                "README.CoinMP.txt",
                                ],
                      'pulp.solverdir' : ['*','*.*']},
      install_requires = ['pyparsing>=1.5.2'],
      entry_points = ("""
      [console_scripts]
      pulptest = pulp:pulpTestAll
      pulpdoctest = pulp:pulpDoctest
      """
      ),
)
