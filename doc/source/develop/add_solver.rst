How to add a new solver to PuLP
======================================

Solver API are located in the directory ``pulp/apis/`` and are organized as one file per solver. Each file can contain more than one API (usually between 1 and 2).

General information on configuring solvers and how pulp finds solvers installed in a system are in the :doc:`/guides/how_to_configure_solvers` section.


Example
----------

The smallest api for a solver can be found in the file :py:class:`pulp.apis.mipcl.MIPCL_CMD` located in ``pulp/apis/mipcl.py``. We will use it as an example to list all the changes that need to be done.

Inheriting base classes
------------------------------

The solver needs to inherit one of three classes:  :py:class:`pulp.apis.LpSolver`, :py:class:`pulp.apis.LpSolver_API` or :py:class:`pulp.apis.LpSolver_CMD` located in ``pulp.apis.core.py``. The first one is a generic class. The second one is used for solvers driven through their official python interface (see :ref:`below <solver-api>`). The third one is used for command-line based APIs to solvers. This is the one used for the example::

    from .core import LpSolver_CMD, subprocess, PulpSolverError
    import os
    from .. import constants
    import warnings

    class MIPCL_CMD(LpSolver_CMD):

        name = "MIPCL_CMD"

        def __init__(
            self,
            path=None,
            keepFiles=False,
            mip=True,
            msg=True,
            options=None,
            timeLimit=None,
        ):
            LpSolver_CMD.__init__(
                self,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                options=options,
                path=path,
                keepFiles=keepFiles,
            )

As can be seen in the example, the main things when declaring a solver are:

#. declaring a class-level attribute with its name.
#. defining some arguments for the solver (ideally, following the convention of other solvers).
#. initializing the parent class with available data.
#. (optional) doing some other particular logic.

In addition to these some minimal methods are expected to be implemented by the solver. We will cover each one.

``available`` method
--------------------------

Required by :py:class:`pulp.apis.LpSolver` and :py:class:`pulp.apis.LpSolver_CMD`.

Returns ``True`` if the solver is available and operational. ``False`` otherwise::

    def available(self):
        return self.executable(self.path)

``actualSolve`` method
--------------------------

Required by :py:class:`pulp.apis.LpSolver` and :py:class:`pulp.apis.LpSolver_CMD`.

Takes an :py:class:`pulp.pulp.LpProblem` as argument, solves it, stores the solution, and returns a status code::

    def actualSolve(self, lp):
        """Solve a well formulated lp problem"""
        start = clocks()
        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)
        tmpMps, tmpSol = self.create_tmp_files(lp.name, "mps", "sol")
        if lp.sense == constants.LpMaximize:
            # we swap the objectives
            # because it does not handle maximization.
            warnings.warn(
                "MIPCL_CMD does not allow maximization, "
                "we will minimize the inverse of the objective function."
            )
            lp += -lp.objective
        lp.checkDuplicateVars()
        lp.checkDuplicateConstraints()
        lp.checkLengthVars(52)
        lp.writeMPS(tmpMps, mpsSense=lp.sense)

        # just to report duplicated variables:
        try:
            os.remove(tmpSol)
        except:
            pass
        cmd = [self.path]
        cmd.append(tmpMps)
        cmd.extend(["-solfile", tmpSol])
        if self.timeLimit is not None:
            cmd.extend(["-time", f"{self.timeLimit}"])
        for option in self.options:
            cmd.append(option)
        if lp.isMIP():
            if not self.mip:
                warnings.warn("MIPCL_CMD cannot solve the relaxation of a problem")
        if self.msg:
            pipe = None
        else:
            pipe = open(os.devnull, "w")

        return_code = subprocess.call(cmd, stdout=pipe, stderr=pipe)
        # We need to undo the objective swap before finishing
        if lp.sense == constants.LpMaximize:
            lp += -lp.objective
        if return_code != 0:
            raise PulpSolverError("PuLP: Error while trying to execute " + self.path)
        if not os.path.exists(tmpSol):
            status = constants.LpSolveStatus.NotSolved
            has_solution = False
            values = None
        else:
            status, values, has_solution = self.readsol(tmpSol)
        self.delete_tmp_files(tmpMps, tmpSol)
        if values is not None and has_solution:
            lp.assignVarsVals(values)

        return self.buildStats(lp, status, has_solution, start=start)

``self.buildStats(lp, status, has_solution, start=start)`` is the only place an
:py:class:`~pulp.LpSolveStats` gets built, and every ``actualSolve`` ends by
returning it. ``status`` is why the solver stopped: use the most specific
:class:`~pulp.constants.LpSolveStatus` member the solver reports, e.g.
``TimeLimit`` or ``NodeLimit``, not just ``Optimal``/``NotSolved``. ``has_solution``
says whether it handed back a feasible solution -- pass what the solver actually
told you, since most limit statuses can come with or without one. ``start`` is
:func:`~pulp.apis.core.clocks` taken at the top of ``actualSolve``, so the
reported time covers the whole solve; pass ``best_bound=`` too when the solver
reports one.

``defaultPath`` method
-------------------------

Only required by :py:class:`pulp.apis.LpSolver_CMD`. It returns the default path of the command-line solver::

    def defaultPath(self):
        return self.executableExtension("mps_mipcl")


Making the solver available to PuLP
---------------------------------------------------

Modify the ``pulp/apis/__init__.py`` file to import your solver and add it to the ``_all_solvers`` list::

    from .mipcl import MIPCL_CMD
    _all_solvers = [
    # (...)
    MIPCL_CMD,
    ]

Including the solver in tests suite
--------------------------------------------------

Include the solver in PuLP's test suite by creating ``pulp/tests/test_<solver>.py`` (for example ``pulp/tests/test_mipcl_cmd.py``)::

    from pulp.tests.solver_common import BaseSolverTest
    import pulp.apis as solvers

    class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
        solveInst = solvers.MIPCL_CMD

Add ``pulp_test_overrides`` in that file when the solver's acceptable statuses or results differ from the defaults in ``solver_common.py``.


.. _solver-api:

Extra: adding a official solver API
---------------------------------------------

A solver driven through its official python interface inherits :py:class:`pulp.apis.LpSolver_API`. Instead of ``actualSolve``, it implements three steps, which ``LpSolver_API.actualSolve`` calls in order::

    class MY_SOLVER(LpSolver_API):

        name = "MY_SOLVER"

        def buildSolverModel(self, lp):
            # create the solver's model, store it in lp.solverModel, load the problem
            # and apply the options
            ...
            self.configureSolver(lp)

        def configureSolver(self, lp):
            # apply msg, timeLimit, gapRel, logPath, etc. to lp.solverModel
            ...

        def callSolver(self, lp, *, changes=None, **kwargs):
            # solve lp.solverModel; kwargs are the arguments given to solve,
            # e.g. a callback
            ...

        def findSolutionValues(self, lp, result=None):
            # write the values back into lp; result is what callSolver returned
            ...
            return status, has_solution

``buildSolverModel`` fills the property ``lp.solverModel`` of the LP problem with the model object from the official solver API (e.g., ``gurobipy.Model`` for GUROBI). Anything ``findSolutionValues`` needs besides that model (e.g., a solution object) is returned by ``callSolver``, which ``actualSolve`` hands over as ``result``. A solver that proves a bound can also implement ``findBestBound(lp)``.

These steps permit a consistent, more standard way to call official solvers. In particular, they allow for detailed configuration, such as the one explained :ref:`here <solver-specific-config>`.

To support ``LpProblem.resolve``, updating ``lp.solverModel`` in place instead of building it again, a solver also implements ``canUpdate(lp)`` (return True when ``lp.solverModel`` can be updated) and ``applyChanges(lp, changes)``, which replays the edits made to the problem since the last solve. ``LpSolver_API.actualResolve`` then calls ``applyChanges``, ``configureSolver`` and ``callSolver(lp, changes=changes)``. When an edit cannot be replayed, ``applyChanges`` raises ``pulp.apis.core._RebuildNeeded`` before touching the model, and the model is built again.
