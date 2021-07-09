pulp
**************************
.. image:: https://travis-ci.org/coin-or/pulp.svg?branch=master
    :target: https://travis-ci.org/coin-or/pulp

PuLP is an LP modeler written in Python. PuLP can generate MPS or LP files
and call GLPK_, COIN-OR CLP/`CBC`_, CPLEX_, GUROBI_, MOSEK_, XPRESS_, CHOCO_, MIPCL_, SCIP_ to solve linear
problems.

Installation
================

The easiest way to install pulp is via `PyPi <https://pypi.python.org/pypi/PuLP>`_

If pip is available on your system::

     python -m pip install pulp

Otherwise follow the download instructions on the PyPi page.


If you want to install the latest version from github you can run the following::

    python -m pip install -U git+https://github.com/coin-or/pulp


On Linux and OSX systems the tests must be run to make the default
solver executable.

::

     sudo pulptest

Examples
================

See the examples directory for examples.

PuLP requires Python 2.7 or Python >= 3.4.

The examples use the default solver (CBC). To use other solvers they must be available (installed and accessible). For more information on how to do that, see the `guide on configuring solvers <https://coin-or.github.io/pulp/guides/how_to_configure_solvers.html>`_.

Documentation
================

Documentation is found on https://coin-or.github.io/pulp/.


Use LpVariable() to create new variables. To create a variable 0 <= x <= 3::

     x = LpVariable("x", 0, 3)

To create a variable 0 <= y <= 1::

     y = LpVariable("y", 0, 1)

Use LpProblem() to create new problems. Create "myProblem"::

     prob = LpProblem("myProblem", LpMinimize)

Combine variables to create expressions and constraints, then add them to the
problem::

     prob += x + y <= 2

If you add an expression (not a constraint), it will
become the objective::

     prob += -4*x + y

To solve with the default included solver::

     status = prob.solve()

To use another sovler to solve the problem::

     status = prob.solve(GLPK(msg = 0))

Display the status of the solution::

     LpStatus[status]
     > 'Optimal'

You can get the value of the variables using value(). ex::

     value(x)
     > 2.0

Exported Classes:

* ``LpProblem`` -- Container class for a Linear programming problem
* ``LpVariable`` -- Variables that are added to constraints in the LP
* ``LpConstraint`` -- A constraint of the general form

      a1x1+a2x2 ...anxn (<=, =, >=) b

*  ``LpConstraintVar`` -- Used to construct a column of the model in column-wise modelling

Exported Functions:

* ``value()`` -- Finds the value of a variable or expression
* ``lpSum()`` -- given a list of the form [a1*x1, a2x2, ..., anxn] will construct a linear expression to be used as a constraint or variable
* ``lpDot()`` --given two lists of the form [a1, a2, ..., an] and [ x1, x2, ..., xn] will construct a linear expression to be used as a constraint or variable


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

	 




**Comments, bug reports, patches and suggestions are welcome.**

* Comments and suggestions: https://github.com/coin-or/pulp/discussions
* Bug reports: https://github.com/coin-or/pulp/issues
* Patches: https://github.com/coin-or/pulp/pulls

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
