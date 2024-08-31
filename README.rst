pulp
**************************

.. image:: https://travis-ci.org/coin-or/pulp.svg?branch=master
    :target: https://travis-ci.org/coin-or/pulp
.. image:: https://img.shields.io/pypi/v/pulp
    :target: https://pypi.org/project/PuLP/
    :alt: PyPI
.. image:: https://img.shields.io/pypi/dm/pulp
    :target: https://pypi.org/project/PuLP/
    :alt: PyPI - Downloads

PuLP is an linear and mixed integer programming modeler written in Python. With PuLP, it is simple to create MILP optimisation problems and solve them with the latest open-source (or proprietary) solvers.  PuLP can generate MPS or LP files and call solvers such as GLPK_, COIN-OR CLP/`CBC`_, CPLEX_, GUROBI_, MOSEK_, XPRESS_, CHOCO_, MIPCL_, HiGHS_, SCIP_/FSCIP_.

The documentation for PuLP can be `found here <https://coin-or.github.io/pulp/>`_.

PuLP is part of the `COIN-OR project <https://www.coin-or.org/>`_. 

Installation
================

PuLP requires Python 3.7 or newer.

The easiest way to install PuLP is with ``pip``. If ``pip`` is available on your system, type::

     python -m pip install pulp

Otherwise follow the download instructions on the `PyPi page <https://pypi.python.org/pypi/PuLP>`_.


Quickstart 
===============

Use ``LpVariable`` to create new variables. To create a variable x with 0  ≤  x  ≤  3::

     from pulp import *
     x = LpVariable("x", 0, 3)

To create a binary variable, y, with values either 0 or 1::

     y = LpVariable("y", cat="Binary")

Use ``LpProblem`` to create new problems. Create a problem called "myProblem" like so::

     prob = LpProblem("myProblem", LpMinimize)

Combine variables in order to create expressions and constraints, and then add them to the problem.::

     prob += x + y <= 2

An expression is a constraint without a right-hand side (RHS) sense (one of ``=``, ``<=`` or ``>=``). If you add an expression to a problem, it will become the objective::

     prob += -4*x + y

To solve the problem  with the default included solver::

     status = prob.solve()

If you want to try another solver to solve the problem::

     status = prob.solve(GLPK(msg = 0))

Display the status of the solution::

     LpStatus[status]
     > 'Optimal'

You can get the value of the variables using ``value``. ex::

     value(x)
     > 2.0


Essential Classes
------------------


* ``LpProblem`` -- Container class for a Linear or Integer programming problem
* ``LpVariable`` -- Variables that are added into constraints in the LP problem
* ``LpConstraint`` -- Constraints of the general form

      a1x1 + a2x2 + ... + anxn (<=, =, >=) b

* ``LpConstraintVar`` -- A special type of constraint for constructing column of the model in column-wise modelling

Useful Functions
------------------

* ``value()`` -- Finds the value of a variable or expression
* ``lpSum()`` -- Given a list of the form [a1*x1, a2*x2, ..., an*xn] will construct a linear expression to be used as a constraint or variable
* ``lpDot()`` -- Given two lists of the form [a1, a2, ..., an] and [x1, x2, ..., xn] will construct a linear expression to be used as a constraint or variable

More Examples
================

Several tutorial are given in `documentation <https://coin-or.github.io/pulp/CaseStudies/index.html>`_ and pure code examples are available in `examples/ directory <https://github.com/coin-or/pulp/tree/master/examples>`_ .

The examples use the default solver (CBC). To use other solvers they must be available (installed and accessible). For more information on how to do that, see the `guide on configuring solvers <https://coin-or.github.io/pulp/guides/how_to_configure_solvers.html>`_.


For Developers 
================


If you want to install the latest version from GitHub you can run::

    python -m pip install -U git+https://github.com/coin-or/pulp


On Linux and MacOS systems, you must run the tests to make the default solver executable::

     sudo pulptest




Building the documentation
--------------------------

The PuLP documentation is built with `Sphinx <https://www.sphinx-doc.org>`_.  We recommended using a
`virtual environment <https://docs.python.org/3/library/venv.html>`_ to build the documentation locally.

To build, run the following in a terminal window, in the PuLP root directory

::

    cd pulp
    python -m pip install -r requirements-dev.txt
    cd doc
    make html

A folder named html will be created inside the ``build/`` directory.
The home page for the documentation is ``doc/build/html/index.html`` which can be opened in a browser.

Contributing to PuLP
-----------------------
Instructions for making your first contribution to PuLP are given `here <https://coin-or.github.io/pulp/develop/contribute.html>`_.

**Comments, bug reports, patches and suggestions are very welcome!**

* Comments and suggestions: https://github.com/coin-or/pulp/discussions
* Bug reports: https://github.com/coin-or/pulp/issues
* Patches: https://github.com/coin-or/pulp/pulls

Copyright and License 
=======================
PuLP is distributed under an MIT license. 

     Copyright J.S. Roy, 2003-2005
     Copyright Stuart A. Mitchell
     See the LICENSE file for copyright information.

.. _Python: http://www.python.org/

.. _GLPK: http://www.gnu.org/software/glpk/glpk.html
.. _CBC: https://github.com/coin-or/Cbc
.. _CPLEX: http://www.cplex.com/
.. _GUROBI: http://www.gurobi.com/
.. _MOSEK: https://www.mosek.com/
.. _XPRESS: https://www.fico.com/es/products/fico-xpress-solver
.. _CHOCO: https://choco-solver.org/
.. _MIPCL: http://mipcl-cpp.appspot.com/
.. _SCIP: https://www.scipopt.org/
.. _HiGHS: https://highs.dev
.. _FSCIP: https://ug.zib.de
