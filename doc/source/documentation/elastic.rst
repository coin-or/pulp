Elastic Constraints
^^^^^^^^^^^^^^^^^^^
.. currentmodule:: pulp

A constraint :math:`C(x) = c` (equality may be replaced by :math:`\le`
or :math:`\ge`)
can be elasticized to the form

.. math::   C(x) \in D

where :math:`D` denotes some interval containing the value
:math:`c`.

Define the constraint in two steps:

  #.  instantiate constraint (subclass of :class:`LpConstraint`) with target :math:`c`.
  #.  call its :meth:`~LpConstraint.makeElasticSubProblem` method which returns
      an object of type :class:`FixedElasticSubProblem` 
      (subclass of :class:`LpProblem`) - its objective is the minimization 
      of the distance of :math:`C(x)` from :math:`D`.

.. code-block:: python

   constraint = LpConstraint(..., rhs = c)
   elasticProblem = constraint.makeElasticSubProblem(
                          penalty = <penalty_value>,
                          proportionFreeBound = <freebound_value>,
                          proportionFreeBoundList = <freebound_list_value>,
                          )

where:
  *  ``<penalty_value>`` is a real number
  *  ``<freebound_value>`` :math:`a \in [0,1]` specifies a symmetric
     target interval :math:`D = (c(1-a),c(1+a))` about :math:`c`
  *  ``<freebound_list_value> = [a,b]``, a list of 
     proportions :math:`a, b \in [0,1]` specifying an asymmetric target 
     interval :math:`D = (c(1-a),c(1+b))` about :math:`c`

The penalty applies to the constraint at points :math:`x` where
:math:`C(x) \not \in D`.
The magnitude of ``<penalty_value>`` can be assessed by examining
the final objective function in the ``.lp`` file written by
:meth:`LpProblem.writeLP`.

Example:

>>> constraint_1 = LpConstraint('ex_1',sense=1,rhs=200)
>>> elasticProblem_1 = constraint_1.makeElasticSubproblem(penalty=1, proportionFreeBound = 0.01)
>>> constraint_2 = LpConstraint('ex_2',sense=0,rhs=500)
>>> elasticProblem_2 = constraint_2.makeElasticSubproblem(penalty=1,
proportionFreeBoundList = [0.02, 0.05])

#.    constraint_1 has a penalty-free target interval of 1% either side of the rhs value, 200
#.    constraint_2 has a penalty-free target interval of
      - 2% on left and 5% on the right side of the rhs value, 500

.. image:: _static/freebound.*
   :height:  5in
   :alt:  Freebound interval

Following are the methods of the return-value:

