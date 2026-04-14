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

.. important::

   **CBC is not shipped inside the PuLP package.** Older releases bundled a CBC
   binary and exposed it as ``PULP_CBC_CMD``; that API and the bundled solver are
   **removed**. To solve models with CBC through PuLP you should:

   * install PuLP with the optional CBC extra: ``python -m pip install pulp[cbc]``
     (this installs the `cbcbox <https://pypi.org/project/cbcbox/>`_ wheel, which
     provides a CBC executable PuLP can find automatically), **or**
   * install a CBC build yourself and ensure the ``cbc`` (or ``cbc.exe`` on
     Windows) executable is on your ``PATH``,

   then use the ``COIN_CMD`` solver (or call ``prob.solve()`` with no arguments
   when CBC is available; otherwise install another solver such as GLPK or pass
   an explicit solver). Without CBC or another available solver, the default
   solve path will raise ``PulpError: No solver available``.

Installation
================

PuLP requires Python 3.9 or newer.

**Recommended:** install with CBC support::

     python -m pip install pulp[cbc]

Plain ``python -m pip install pulp`` installs only the modeler; you must then
supply your own CBC on ``PATH`` or another solver.

Otherwise follow the download instructions on the `PyPi page <https://pypi.python.org/pypi/PuLP>`_.

Installing solvers
----------------------

PuLP can use a variety of solvers. When CBC is available (via ``pulp[cbc]`` or
``cbc`` on ``PATH``), ``COIN_CMD`` is the usual open-source MIP/LP choice and is
selected as the default ahead of GLPK. PuLP can also install other solvers via
optional PyPI extras (some require a commercial license for running or for large models)::

    python -m pip install pulp[gurobi]
    python -m pip install pulp[cplex]
    python -m pip install pulp[xpress]
    python -m pip install pulp[scip]
    python -m pip install pulp[highs]
    python -m pip install pulp[copt]
    python -m pip install pulp[mosek]
    python -m pip install pulp[cylp]
    python -m pip install pulp[cbc]

If you want to install all open source solvers (scip, highs, cbc), you can use the shortcut::
    python -m pip install pulp[open_py]

For more information on how to install solvers, see the `guide on configuring solvers <https://coin-or.github.io/pulp/guides/how_to_configure_solvers.html>`_.

Quickstart 
===============

Use ``LpProblem`` to create a problem, then add variables with ``add_variable``. Create a problem called "myProblem" and a variable x with 0 ≤ x ≤ 3::

     from pulp import *
     prob = LpProblem("myProblem", LpMinimize)
     x = prob.add_variable("x", 0, 3)

To create a binary variable y (values 0 or 1)::

     y = prob.add_variable("y", cat="Binary")

Combine variables to create expressions and constraints and add them to the problem::

     prob += x + y <= 2

An expression is a constraint without a right-hand side (RHS) sense (one of ``=``, ``<=`` or ``>=``). If you add an expression to a problem, it will become the objective::

     prob += -4*x + y

To solve the problem with the default solver (CBC when installed via ``pulp[cbc]``
or ``cbc`` on ``PATH``, otherwise another available backend)::

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

Useful Functions
------------------

* ``value()`` -- Finds the value of a variable or expression
* ``lpSum()`` -- Given a list of the form [a1*x1, a2*x2, ..., an*xn] will construct a linear expression to be used as a constraint or variable
* ``lpDot()`` -- Given two lists of the form [a1, a2, ..., an] and [x1, x2, ..., xn] will construct a linear expression to be used as a constraint or variable

More Examples
================

Several tutorial are given in `documentation <https://coin-or.github.io/pulp/CaseStudies/index.html>`_ and pure code examples are available in `examples/ directory <https://github.com/coin-or/pulp/tree/master/examples>`_ .

The examples assume CBC is available (for example after ``pip install pulp[cbc]``).
To use other solvers they must be available (installed and accessible). For more
information, see the `guide on configuring solvers <https://coin-or.github.io/pulp/guides/how_to_configure_solvers.html>`_.


For Developers 
================

If you want to install the latest version from GitHub you can run::

    python -m pip install -U "pulp[cbc] @ git+https://github.com/coin-or/pulp.git"

Building from source
--------------------------

This version of PuLP includes a Rust extension (``pulp._rustcore``) that provides the core model, variables, constraints, and expressions. The build uses `maturin <https://github.com/PyO3/maturin>`_ and requires a Rust toolchain in addition to Python.

**Requirements**

* **Python** 3.9 or newer
* **Rust** (latest stable). Install from https://rustup.rs/
* **uv** (recommended for install and dev). Install with: ``curl -LsSf https://astral.sh/uv/install.sh | sh`` (Linux/macOS) or ``powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`` (Windows)
* **OS**: Windows, macOS (x86_64, arm64), or Linux (x86_64, arm64). The Rust extension is built for the host platform.

**Build steps**

From the PuLP root directory, create a virtual environment and install the package in editable mode with dev dependencies::

    uv venv
    uv pip install --group dev -e .[cbc]

Or with plain pip (maturin will be used automatically by the build backend)::

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[cbc]"

**Running tests**

::

    uv run python -m unittest discover -s pulp/tests -v

Building the documentation
--------------------------

The PuLP documentation is built with `Sphinx <https://www.sphinx-doc.org>`_. Use a virtual environment and the dev install above, then::

    cd doc
    make html

A folder named ``html`` will be created inside ``doc/build/``. Open ``doc/build/html/index.html`` in a browser.

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
