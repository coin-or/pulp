
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
  
    Return status from solver:
  
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
  
  .. data:: LpSolution
  
    Return solution status from solver:
  
      +-----------------------------+---------------+-----------------+
      |  LpStatus  key                      | string value  | numerical value |
      +=============================+===============+=================+
      |  :data:`LpSolutionOptimal`          | "Optimal Solution Found"     |          1      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpSolutionNoSolutionFound`  | "No Solution Found"  |          0      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpSolutionStatusInfeasible` | "Infeasible"  |         -1      |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpSolutionStatusUnbounded`  | "Unbounded"   |          -2     |
      +-----------------------------+---------------+-----------------+
      |  :data:`LpSolutionIntegerFeasible`  | "Integer Solution Found"   |          2     |
      +-----------------------------+---------------+-----------------+
      
  
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
  
  
