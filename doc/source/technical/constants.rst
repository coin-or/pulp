
:mod:`pulp.constants` 
=====================
    
.. automodule:: pulp.constants
     :members:
     :undoc-members:
     :inherited-members:
     :show-inheritance:

.. data:: LpContinuous

    LpContinuous= "Continuous"

.. data:: LpInteger = "Integer"

    LpInteger= "Integer"

.. data:: LpBinary = "Binary"

    LpBinary= "Binary"

.. class:: LpSolveStatus
   :noindex:

Why the solver stopped, as stored in :attr:`pulp.LpSolveStats.status` -- the type
every solve returns. It is an ``IntEnum``. Whether the solver handed back a
feasible solution is kept separately, in :attr:`pulp.LpSolveStats.has_solution`.

  +--------------------------------------+----------------------------------------------+-----------------+
  |  member                              | meaning                                      | numerical value |
  +======================================+==============================================+=================+
  |  ``LpSolveStatus.Optimal``           | proven optimal                               |          1      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.NotSolved``         | not solved yet                               |          0      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.Infeasible``        | proven infeasible                            |         -1      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.Unbounded``         | proven unbounded                             |         -2      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.Undefined``         | inconclusive, e.g. infeasible or unbounded   |         -3      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.TimeLimit``         | time (or deterministic work) limit           |         -4      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.MemoryLimit``       | memory limit                                 |         -5      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.NodeLimit``         | branch and bound node limit                  |         -6      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.GapLimit``          | gap tolerance, or objective cutoff/target    |         -7      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.IterationLimit``    | iteration limit                              |         -8      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.SolutionLimit``     | number of solutions found                    |         -9      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.Interrupted``       | user interrupt or abort                      |        -10      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.Stopped``           | stopped early, the solver does not say why   |        -11      |
  +--------------------------------------+----------------------------------------------+-----------------+
  |  ``LpSolveStatus.NumericalError``    | numerical trouble                            |        -12      |
  +--------------------------------------+----------------------------------------------+-----------------+

.. data:: LpSenses
 
Dictionary of values for :attr:`~pulp.pulp.LpProblem.sense`:

   LpSenses =
   {:data:`LpMaximize`:"Maximize", :data:`LpMinimize`:"Minimize"}
  
 .. data::   LpMinimize 
  
    LpMinimize = 1
 
 .. data::   LpMaximize 
 
    LpMaximize = -1
 
 .. data::   LpConstraintEQ 
  
     LpConstraintEQ = 0
 
 .. data::   LpConstraintLE
 
    LpConstraintLE = -1
 
 .. data::   LpConstraintGE 
 
     LpConstraintGE = 1
  
 .. data:: LpConstraintSenses
  
    +--------------------------+----------------+-----------------+
    | LpConstraint key         | symbolic value | numerical value |
    +==========================+================+=================+
    | :data:`LpConstraintEQ`   | "=="           |     0           |
    +--------------------------+----------------+-----------------+
    | :data:`LpConstraintLE`   | "<="           |     -1          |
    +--------------------------+----------------+-----------------+
    | :data:`LpConstraintGE`   | ">="           |     1           |
    +--------------------------+----------------+-----------------+
  
  
