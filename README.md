# pulp ![Build Status](https://travis-ci.org/coin-or/pulp.svg?branch=master)](https://travis-ci.org/coin-or/pulp)

PuLP is an LP modeler written in python. PuLP can generate MPS or LP files
and call GLPK[1], COIN CLP/CBC[2], CPLEX[3], and GUROBI[4] to solve linear
problems.

## Installation

The easiest way to install pulp is via [PyPi](https://pypi.python.org/pypi/PuLP)

If pip is available on your system

     $pip install pulp

Otherwise follow the download instructions on the PyPi page
On Linux and OSX systems the tests must be run to make the default
solver executable.

     $sudo pulptest

## Examples

See the examples directory for examples.

PuLP requires Python >= 2.6.

The examples use the default solver (cbc), to use other solvers they must be available.

# Documentation
Documentation is found on https://pythonhosted.org/PuLP/.


Use LpVariable() to create new variables. To create a variable 0 <= x <= 3

     >>> x = LpVariable("x", 0, 3)

To create a variable 0 <= y <= 1

     >>> y = LpVariable("y", 0, 1)

Use LpProblem() to create new problems. Create "myProblem"

     >>> prob = LpProblem("myProblem", LpMinimize)

Combine variables to create expressions and constraints and add them to the
problem.

     >>> prob += x + y <= 2

If you add an expression (not a constraint), it will
become the objective.

     >>> prob += -4*x + y

To solve with the default included solver

     >>> status = prob.solve()

To use another sovler to solve the problem.

     >>> status = prob.solve(GLPK(msg = 0))

Display the status of the solution

     >>> LpStatus[status]
     'Optimal'

You can get the value of the variables using value(). ex:

     >>> value(x)
     2.0

Exported Classes:

* LpProblem -- Container class for a Linear programming problem
* LpVariable -- Variables that are added to constraints in the LP
* LpConstraint -- A constraint of the general form

      a1x1+a2x2 ...anxn (<=, =, >=) b

*  LpConstraintVar -- Used to construct a column of the model in column-wise modelling

Exported Functions:

* value() -- Finds the value of a variable or expression
* lpSum() -- given a list of the form [a1*x1, a2x2, ..., anxn] will construct a linear expression to be used as a constraint or variable
* lpDot() --given two lists of the form [a1, a2, ..., an] and [ x1, x2, ..., xn] will construct a linear epression to be used as a constraint or variable

Comments, bug reports, patches and suggestions are welcome.
pulp-or-discuss@googlegroups.com

     Copyright J.S. Roy (js@jeannot.org), 2003-2005
     Copyright Stuart A. Mitchell (stu@stuartmitchell.com)
     See the LICENSE file for copyright information.

References:
[1] http://www.gnu.org/software/glpk/glpk.html
[2] http://www.coin-or.org/
[3] http://www.cplex.com/
[4] http://www.gurobi.com/
