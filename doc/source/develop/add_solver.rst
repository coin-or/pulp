How to add a new solver to PuLP
======================================

Solver API are located in the directory ``pulp/apis/`` and are organized as one file per solver. Each file can contain more than one API (usually between 1 and 2).

General information on configuring solvers and how pulp finds solvers installed in a system are in the :doc:`/guides/how_to_configure_solvers` section.


Example
----------

The smallest api for a solver can be found in the file :py:class:`pulp.apis.mipcl_api.MIPCL_CMD` located in ``pulp/apis/mipcl_api.py``. We will use it as an example to list all the changes that need to be done.

Inheriting base classes
------------------------------

The solver needs to inherit one of two classes:  :py:class:`pulp.apis.LpSolver` or  :py:class:`pulp.apis.LpSolver_CMD` located in ``pulp.apis.core.py``. The first one is a generic class. The second one is used for command-line based APIs to solvers. This is the one used for the example::

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
            status = constants.LpStatusNotSolved
            status_sol = constants.LpSolutionNoSolutionFound
            values = None
        else:
            status, values, status_sol = self.readsol(tmpSol)
        self.delete_tmp_files(tmpMps, tmpSol)
        lp.assignStatus(status, status_sol)
        if status not in [constants.LpStatusInfeasible, constants.LpStatusNotSolved]:
            lp.assignVarsVals(values)

        return status

``defaultPath`` method
-------------------------

Only required by :py:class:`pulp.apis.LpSolver_CMD`. It returns the default path of the command-line solver::

    def defaultPath(self):
        return self.executableExtension("mps_mipcl")


Making the solver available to PuLP
---------------------------------------------------

Modify the ``pulp/apis/__init__.py`` file to import your solver and add it to the ``_all_solvers`` list::

    from .mipcl_api import MIPCL_CMD
    _all_solvers = [
    # (...)
    MIPCL_CMD,
    ]

Including the solver in tests suite
--------------------------------------------------

Include the solver in PuLP's test suite by adding a couple of lines corresponding to your solver to the ``pulp/tests/test_pulp.py`` file::

    # (...)
    class MIPCL_CMDTest(BaseSolverTest.PuLPTest):
        solveInst = MIPCL_CMD


Extra: adding a official solver API
---------------------------------------------

There are additional best practices to take into account with these solvers. The ``actualSolve`` method has the following structure::

    def actualSolve(self, lp):
        self.buildSolverModel(lp)
        # set the initial solution
        self.callSolver(lp)
        # get the solution information
        solutionStatus = self.findSolutionValues(lp)
        return solutionStatus

In addition to this, the ``buildSolverModel`` method fills a property named `lp.solverModel` in the LP problem. This property will include a pointer to the model object from the official solver API (e.g., ``gurobipy.Model`` for GUROBI).

These considerations will permit a consistent, more standard way to call official solvers. In particular, they allow for detailed configuration, such as the one explained :ref:`here <solver-specific-config>`.