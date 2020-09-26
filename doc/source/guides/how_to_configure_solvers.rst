How to configure a solver in PuLP
======================================

A typical problem PuLP users have is trying to connect to a solver that is installed in their pc. Here, we show the main concepts and ways to be sure PuLP can talk to the solver in question.

Checking which solvers PuLP has access to
------------------------------------------------

PuLP has some helper functions that permit a user to query which solvers are available and initialize a solver from its name.

.. code-block:: python

    import pulp as pl
    solver_list = pl.list_solvers()
    # ['GLPK_CMD', 'PYGLPK', 'CPLEX_CMD', 'CPLEX_PY', 'CPLEX_DLL', 'GUROBI', 'GUROBI_CMD', 'MOSEK', 'XPRESS', 'PULP_CBC_CMD', 'COIN_CMD', 'COINMP_DLL', 'CHOCO_CMD', 'PULP_CHOCO_CMD', 'MIPCL_CMD', 'SCIP_CMD']

If passed the `only_available=True` argument, PuLP lists the solvers that are currently available::

    import pulp as pl
    solver_list = pl.list_solvers(available_only=True)
    # ['GLPK_CMD', 'CPLEX_CMD', 'CPLEX_PY', 'GUROBI', 'GUROBI_CMD', 'PULP_CBC_CMD', 'COIN_CMD', 'PULP_CHOCO_CMD']

Also, it's possible to get a solver object by using the name of the solver. Any arguments passed to this function are passed to the constructor:

.. code-block:: python

    import pulp as pl
    solver = pl.get_solver('CPLEX_CMD')
    solver = pl.get_solver('CPLEX_CMD', timeLimit=10)

In the next sections, we will explain how to configure a solver to be accessible by PuLP.

What is an environment variable
--------------------------------------

An environment variable is probably better explained `somewhere else <https://en.wikipedia.org/wiki/Environment_variable>`_. For the sake of this document, it is a text value stored during your session that allows you to configure some applications that make use of them. For example, when you write:

    python

in your command line, it usually opens a python console. But how did your computer know where to find python? It knew because there is an environment variable call "PATH" that stores a list of locations in your hard-drive where your pc looks for executables that match the thing you write.

It has many advantages such as not leaving any trace in the pc and being fairly cross-platform, among many others.

Types of PuLP integrations (API) to solvers
--------------------------------------------------------

API means "Application Programming Interface". PuLP has usually several ways to connect to solvers. Depending on the way it connects to the solver, configuring the connection may vary. We can summarize the integrations in two big groups:

* Using the command line interface of the solver.
* Using the python library of the solver.

Not all solvers have a python library, but most have a command line interface. If you want to know which one are you using it's easy. If the name of the solver API ends with ``CMD`` (such as ``PULP_CBC_CMD``, ``CPLEX_CMD``, ``GUROBI_CMD``, etc.) it's the former. Otherwise, it is the latter.

Configuring the path to the solver
--------------------------------------------

In order for PuLP to be able to use a solver via the CMD API, the solver needs to be executed by PuLP via the command line. For this to happen one of two things is needed:

1. The user passes the path to the solver to the solver initialization.
2. The user has configured the PATH environment variable to the directory where the solver is.

**We will do the example for CPLEX in Windows, but the idea is the same for other solvers and other Operating Systems**.

Both options imply knowing where the solver is. So first we have to go look for it in the pc. Mine is in ``C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64\cplex.exe``.

Imagine using the ``CPLEX_CMD`` solver, the first one is really simple:

.. code-block:: python

    path_to_cplex = r'C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64\cplex.exe'
    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    solver = pl.CPLEX_CMD(path=path_to_cplex)
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('a2')
    model += _var + _var2 == 1 
    result = model.solve(solver)

The only to do was to look for the 'cplex.exe' file (in Windows, although in Linux and Mac is something similar but with 'cplex') and pass the absolute path to the solver.

The second one is a little more cumbersome but you only do it once per machine. You need to configure the ``PATH`` environment variable to include the path to the ``C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64`` directory.

Here is one random guide to editing environment variables in: `Windows <https://opentechguides.com/how-to/article/windows-10/113/windows-10-set-path.html>`_ or `Linux or Mac <https://askubuntu.com/questions/730/how-do-i-set-environment-variables>`_. The idea is that once it is correctly configured you can forget about it (until you change pc or solver version).

Once we have done that, we just do something very similar to the previous example:

.. code-block:: python

    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    solver = pl.CPLEX_CMD()
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('a2')
    model += _var + _var2 == 1 
    result = model.solve(solver)

The only difference is that we do not need to tell PuLP where the solver is. The system will find it using the ``PATH`` environment variable just as the ``python`` example above. Magic!

Additional environment variables per solver
------------------------------------------------

Sometimes, giving the path to the solver is not enough. This can be because the solver needs to know where other files are found (dynamic libraries it will use when running) or the PuLP API needs to import some specific python packages that are deployed with the solver (in case of the solvers that do not have a ``_CMD`` at the end).

Whatever the reason, it's better to be safe than sorry and this means knowing what variables are usually used by which solver. Here are the necessary environment variables that are needed for each solver. The procedure is very similar to what we did with the ``PATH`` variable: sometimes you need to edit an existing environment variable and sometimes you need to create a new environment variable. So it looks explicit, I will be using my own paths to variables, but you will have to adapt them to your actual paths (e.g., if the version of the solver is not the same). I will be using my **Linux paths, since it just implies copying the last lines of my ~.bashrc file**. I've adapted them to the Windows command line but, preferably, you would like to edit them via the GUI in windows.


CPLEX
*******

**Linux / Mac: add the following lines to the ~.bashrc file**::

    export CPLEX_HOME="/opt/ibm/ILOG/CPLEX_Studio128/cplex"
    export CPO_HOME="/opt/ibm/ILOG/CPLEX_Studio128/cpoptimizer"
    export PATH="${PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"
    export PYTHONPATH="${PYTHONPATH}:/opt/ibm/ILOG/CPLEX_Studio128/cplex/python/3.5/x86-64_linux"

**Windows: add the following environment variables (via the command line or the graphical user interface)**::

    set CPLEX_HOME=C:/Program Files/IBM/ILOG/CPLEX_Studio128/cplex
    set CPO_HOME=C:/Program Files/IBM/ILOG/CPLEX_Studio128/cpoptimizer
    set PATH=%PATH%;%CPLEX_HOME%/bin/x64_win64;%CPO_HOME%/bin/x64_win64
    set LD_LIBRARY_PATH=%LD_LIBRARY_PATH%;%CPLEX_HOME%/bin/x64_win64;%CPO_HOME%/bin/x64_win64
    set PYTHONPATH=%PYTHONPATH%;/opt/ibm/ILOG/CPLEX_Studio128/cplex/python/3.5/x64_win64

GUROBI
*******

**Linux / Mac: add the following lines to the ~.bashrc file**::

    export GUROBI_HOME="/opt/gurobi801/linux64"
    export PATH="${PATH}:${GUROBI_HOME}/bin"
    export LD_LIBRARY_PATH="${GUROBI_HOME}/lib"

**Windows: add the following environment variables (via the command line or graphical user interface)**::

    set GUROBI_HOME=/opt/gurobi801/linux64
    set PATH=%PATH%;%GUROBI_HOME%/bin
    set LD_LIBRARY_PATH=%LD_LIBRARY_PATH%;%GUROBI_HOME%/lib


Configuring where the CMD solvers write their temporary files
---------------------------------------------------------------------------

In the case of solver APIs that use the command line (again, those that end in ``CMD``, sometimes a user wants to control where the files are written. There are plenty of options.

By default, PuLP does not keep the intermediary files (the \*.mps, \*.lp, \*.mst, \*.sol) and they are written in a temporary directory of the operating system. PuLP looks for the TEMP, TMP and TMPDIR environment variables to write the file (in that order). After using them, PuLP deletes them. If you change any of these environment variables before solving, you should be able to choose where you want PuLP to write the results.

.. code-block:: python

    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('a2')
    model += _var + _var2 == 1 
    solver = pl.PULP_CBC_CMD()
    result = model.solve(solver)

Another option, is passing the argument `KeepFiles=True` to the solver. With this, the solver creates the files in the current directory and they are not deleted (although they will be overwritten if you re-execute).

.. code-block:: python

    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('a2')
    model += _var + _var2 == 1 
    solver = pl.PULP_CBC_CMD(keepFiles=True)
    result = model.solve(solver)

Finally, one can manually edit the tmpDir attribute of the solver object before actually solving.

.. code-block:: python

    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('a2')
    model += _var + _var2 == 1 
    solver = pl.PULP_CBC_CMD()
    solver.tmpDir = 'PUT_SOME_ALTERNATIVE_PATH_HERE'
    result = model.solve(solver)


Using the official solver API
-----------------------------------------

PuLP has the integrations with the official python API solvers for the following solvers:

* Mosek (MOSEK)
* Gurobi (GUROBI)
* Cplex (CPLEX_PY)

These API offer a series of advantages over using the command line option:

* They are usually faster to initialize a problem (they do not involve writing files to disk).
* They offer a lot more functionality and information (extreme rays, dual prices, reduced costs).

In order to access this functionality, the user needs to use the solver object included inside the PuLP problem. PuLP uses the ``solverModel`` attribute on the problem object. This attribute is created and filled when the method ``buildSolverModel()`` is executed.

For example, using the ``CPLEX_PY`` API we can access the api object after the solving is done:

.. code-block:: python

    import pulp

    x = pulp.LpVariable('x', lowBound=0)
    prob = pulp.LpProblem('name', pulp.LpMinimize)
    prob += x

    solver = pulp.CPLEX_PY()
    status = prob.solve(solver)
    # you can now access the information from the cplex API python object
    prob.solverModel  

Also, you can access the python api object before solving by using the lower-level methods:

.. code-block:: python

    import pulp

    x = pulp.LpVariable('x', lowBound=0)
    prob = pulp.LpProblem('name', pulp.LpMinimize)
    prob += x

    solver = pulp.CPLEX_PY()
    solver.self.buildSolverModel(lp)
    # you can now edit the object or do something with it before solving
    solver.solverModel
    # the, you can call the solver to solve the problem
    solver.callSolver(lp)
    # finally, you fill the PuLP variables with the solution
    status = solver.findSolutionValues(lp)

For more information on how to use the `solverModel`, one needs to check the official documentation depending on the solver.


Importing and exporting a solver
-----------------------------------

Exporting a solver can be useful to backup the configuration that was used to solve a model.

In order to export it one needs can export it to a dictionary or a json file::

    import pulp
    solver = pulp.PULP_CBC_CMD()
    solver_dict = solver.to_dict()

The structure of the returned dictionary is quite simple::

    {'keepFiles': 0,
     'mip': True,
     'msg': True,
     'options': [],
     'solver': 'PULP_CBC_CMD',
     'timeLimit': None,
     'warmStart': False}

It's also possible to export it directly to a json file::

    solver.to_json("some_file_name.json")

In order to import it, one needs to do::

    import pulp
    solver = pulp.get_solver_from_dict(solver_dict)

Or from a file::

    import pulp
    solver = pulp.get_solver_from_json("some_file_name.json")

For json, we use the base `json` package. But if `ujson` is available, we use that so the import / export can be really fast.
