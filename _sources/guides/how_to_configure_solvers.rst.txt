How to configure a solver in PuLP
======================================

A typical problem PuLP users have is trying to connect to a solver that is installed in their pc. Here, we show the main concepts and ways to be sure PuLP can talk to the solver in question.

What is an environment variable
--------------------------------------

An environment variable is probably better explained `somewhere else <https://en.wikipedia.org/wiki/Environment_variable>`_. For the sake of this document, it is a text value stored during your session that allows you to configure some applications that make use of them. For example, when you write:

    python

in your command line, it usually opens a python console. But how did your computer know where to find python? It knew because there is an environment variable call "PATH" that stores a list of locations in your hard-drive where your pc looks for executables that match the thing you write.

It has many advantages such as not leaving any trace in the pc and being fairly cross-platform, among many others.

Types of PuLP integrations (API) to solvers
--------------------------------------------------------

API = Application Programming Interface.  
PuLP has usually several ways to connect to solvers. Depending on the way it connects to the solver, configuring the connection may vary. We can summarize the integrations in two big groups:

* Using the command line interface of the solver.
* Using the python library of the solver.

Not all solvers have a python library, but most have a command line interface. I'm not going to cover each one here. If you want to know which one are you using it's easy. If the name of the solver API ends with ``CMD`` (such as ``PULP_CBC_CMD``, ``CPLEX_CMD``, ``GUROBI_CMD``, etc.) it's the former. Otherwise, it is the latter.

Configuring the path to the solver
--------------------------------------------

In order for PuLP to be able to use a solver via the CMD API, the solver needs to be executed by PuLP via the command line. For this to happen one of two things is needed:

1. The user passes the path to the solver to the solver initialization.
2. The user has configured the PATH environment variable to the directory where the solver is.

**We will do the example for CPLEX in Windows, but the idea is the same for other solvers and other Operating Systems**.

Both imply knowing where is solver is. So first we have to go look for it in our pc. Mine is in ``C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64\cplex.exe``.

The first one is really easy. Imagine using the ``CPLEX_CMD`` solver:

.. code-block:: python

    path_to_cplex = r'C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64\cplex.exe'
    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    solver = pl.CPLEX_CMD(path=path_to_cplex)
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('b')
    model += _var + _var2 == 1 
    result = model.solve(solver)

The only thing I had to do was to look for the 'cplex.exe' file (in Windows, although in Linux and Mac is something similar but with 'cplex') and pass the absolute path to the solver.

The second one is a little more cumbersome but you only do it once. You need to configure the ``PATH`` environment variable to include the path to the ``C:\Program Files\IBM\ILOG\CPLEX_Studio128\cplex\bin\x64_win64`` directory.

Here is one random guide to editing environment variables in: `Windows <https://opentechguides.com/how-to/article/windows-10/113/windows-10-set-path.html>`_ or `Linux or Mac <https://askubuntu.com/questions/730/how-do-i-set-environment-variables>`_. The idea is that once it is correctly configured you can forget about it (until you change pc or solver version).

Once we have done that, we just do something very similar to the previous example:

.. code-block:: python

    import pulp as pl
    model = pl.LpProblem("Example", pl.LpMinimize)
    solver = pl.CPLEX_CMD()
    _var = pl.LpVariable('a')
    _var2 = pl.LpVariable('b')
    model += _var + _var2 == 1 
    result = model.solve(solver)

The only difference is that we do not need to tell PuLP where the solver is. The system will find it using the ``PATH`` environment variable just as the ``python`` example above. Magic!

Additional environment variables per solver
------------------------------------------------

Sometimes, giving the path to the solver is not enough. This can be because the solver needs to know where other files are found (dynamic libraries it will use when running) or the PuLP API needs to import some specific python packages that are deployed with the solver (in case of the solvers that do not have a ``_CMD`` at the end).

Whatever the reason, it's better to be safe than sorry. This means knowing what variables are usually used by which solver. Here I'm adding the necessary environment variables that are needed for each solver. The procedure is very similar to what we did with the ``PATH`` variable: sometimes you need to edit an existing variable and sometimes you need to create a new environment variable. So it looks explicit, I will be using my own paths to variables, but you will have to adapt them to your actual paths (e.g., if the version of the solver is not the same). I will be using my **Linux paths, since it just implies copying the last lines of my .bash_profile file**. I've adapted them to the Windows command line but, preferably, you would like to edit them via the GUI in windows.


CPLEX
*******

**Linux / Mac: add the following lines to the .bash_profile file**::

    export CPLEX_HOME="/opt/ibm/ILOG/CPLEX_Studio128/cplex"
    export CPO_HOME="/opt/ibm/ILOG/CPLEX_Studio128/cpoptimizer"
    export PATH="${PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${CPLEX_HOME}/bin/x86-64_linux:${CPO_HOME}/bin/x86-64_linux"
    export PYTHONPATH="${PYTHONPATH}:/opt/ibm/ILOG/CPLEX_Studio128/cplex/python/3.5/x86-64_linux"

**Windows: add the following environment variables (via the command line or the graphical user interface)**::

    set CPLEX_HOME=/opt/ibm/ILOG/CPLEX_Studio128/cplex
    set CPO_HOME=/opt/ibm/ILOG/CPLEX_Studio128/cpoptimizer
    set PATH=%PATH%;%CPLEX_HOME%/bin/x86-64_linux;%CPO_HOME%/bin/x86-64_linux
    set LD_LIBRARY_PATH=%LD_LIBRARY_PATH%;%CPLEX_HOME%/bin/x86-64_linux;%CPO_HOME%/bin/x86-64_linux
    set PYTHONPATH=%PYTHONPATH%;/opt/ibm/ILOG/CPLEX_Studio128/cplex/python/3.5/x86-64_linux


GUROBI
*******

**Linux / Mac: add the following lines to the .bash_profile file**::

    export GUROBI_HOME="/opt/gurobi801/linux64"
    export PATH="${PATH}:${GUROBI_HOME}/bin"
    export LD_LIBRARY_PATH="${GUROBI_HOME}/lib"

**Windows: add the following environment variables (via the command line or graphical user interface)**::

    set GUROBI_HOME=/opt/gurobi801/linux64
    set PATH=%PATH%;%GUROBI_HOME%/bin
    set LD_LIBRARY_PATH=%LD_LIBRARY_PATH%;%GUROBI_HOME%/lib

