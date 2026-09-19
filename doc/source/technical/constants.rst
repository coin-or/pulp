
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

.. data:: LpStatus
  
    Why the solver stopped, see :meth:`~pulp.pulp.LpProblem.getSolverStatus`:
  
      +-----------------------------+---------------+-----------------+
      |  LpStatus  key              | string value  | numerical value |
      +=============================+===============+=================+
      |  :data:`LpStatusOptimal`    | "Optimal"     |          1      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusNotSolved`  | "Not Solved"  |          0      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusInfeasible` | "Infeasible"  |         -1      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusUnbounded`  | "Unbounded"   |          -2     |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusUndefined`  | "Undefined"   |          -3     |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusTimeLimit`  | "Time Limit"  |          2      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusMemoryLimit`| "Memory Limit"|          3      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpStatusNodeLimit`  | "Node Limit"  |          4      |
      +-----------------------------+---------------+-----------------+
 
.. data:: LpStatusOptimal 
 
    LpStatusOptimal = 1
 
.. data:: LpStatusNotSolved 
 
    LpStatusNotSolved = 0
 
.. data:: LpStatusInfeasible

    LpStatusInfeasible = -1

.. data:: LpStatusUnbounded 

    LpStatusUnbounded = -2

.. data:: LpStatusUndefined 

    LpStatusUndefined = -3

.. data:: LpStatusTimeLimit

    LpStatusTimeLimit = 2

.. data:: LpStatusMemoryLimit

    LpStatusMemoryLimit = 3

.. data:: LpStatusNodeLimit

    LpStatusNodeLimit = 4

.. data:: LpSolution

What the solver returned, see :meth:`~pulp.pulp.LpProblem.getSolutionStatus`:

  +----------------------------------------+------------------------------+-----------------+
  |  LpStatus  key                         | string value                 | numerical value |
  +========================================+==============================+=================+
  |  :data:`LpSolutionOptimal`             | "Optimal Solution Found"     |          1      |
  +----------------------------------------+------------------------------+-----------------+
  |  :data:`LpSolutionNoSolutionFound`     | "No Solution Found"          |          0      |
  +----------------------------------------+------------------------------+-----------------+
  |  :data:`LpSolutionInfeasible`          |"No Solution Exists"          |         -1      |
  +----------------------------------------+------------------------------+-----------------+
  |  :data:`LpSolutionUnbounded`           | "Solution is Unbounded"      |          -2     |
  +----------------------------------------+------------------------------+-----------------+
  |  :data:`LpSolutionIntegerFeasible`     | "Solution Found"             |          2      |
  +----------------------------------------+------------------------------+-----------------+
  

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
  
  
