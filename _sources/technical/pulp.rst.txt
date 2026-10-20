=====================================
:mod:`pulp`:  Pulp classes
=====================================
.. module:: pulp

.. currentmodule:: pulp
 
.. autosummary:: 

   LpProblem
   LpVariable
   LpAffineExpression
   LpConstraint

The LpProblem Class
-------------------

.. autoclass:: LpProblem
   :show-inheritance:

   An important attribute of the problem is:

   .. attribute:: objective

      The objective of the problem, an :obj:`LpAffineExpression`

   Creating variables (see :ref:`create_variables`):

   .. automethod:: add_variable
   .. automethod:: add_variable_dicts
   .. automethod:: add_variable_dict
   .. automethod:: add_variable_matrix

   Constraints (see :ref:`edit_constraints`):

   .. automethod:: addConstraint
   .. automethod:: constraints
   .. automethod:: get_constraint_by_name

   Column-wise modelling (see :ref:`column_wise`):

   .. automethod:: add_column
   .. automethod:: remove_variables

   Some of the more important methods:

   .. automethod:: solve
   .. automethod:: roundSolution
   .. automethod:: setObjective
   .. automethod:: writeLP
   .. automethod:: writeMPS
   .. automethod:: toJson
   .. automethod:: fromJson
   .. automethod:: variables

Variables and Expressions
-------------------------

.. autoclass:: LpVariable
   :members:

Example (variables are created from a problem)::

>>> prob = LpProblem("example", LpMinimize)
>>> x = prob.add_variable('x', lowBound=0, cat='Continuous')
>>> y = prob.add_variable('y', upBound=5, cat='Integer')

gives  :math:`x \in [0,\infty)`, :math:`y \in (-\infty, 5]`, an
integer.

----

.. autoclass:: LpAffineExpression
   :show-inheritance:
   :members:
   
   In brief, :math:`\textsf{LpAffineExpression([(x[i],a[i]) for i in
   I])} = \sum_{i \in I} a_i x_i` where  (note the order):

    *   ``x[i]`` is an :class:`LpVariable`
    *   ``a[i]`` is a numerical coefficient. 

----

.. autofunction::  lpSum


Constraints
-----------

.. autoclass::  LpConstraint
   :show-inheritance:
   :members:
   :special-members: __setitem__, __delitem__, __iadd__, __isub__

   A constraint of a problem, as returned by :meth:`LpProblem.addConstraint`,
   :meth:`LpProblem.constraints` and :meth:`LpProblem.get_constraint_by_name`.
   Editing it edits the problem:

   >>> c = prob.addConstraint(x + y <= 5, "c")
   >>> c[x] = 2           # 2*x + y <= 5
   >>> c.changeRHS(8)     # 2*x + y <= 8
   >>> c += 3             # 2*x + y <= 5

   Editing the expression that was added does not; see :ref:`edit_constraints`.


Combinations  and Permutations
------------------------------

.. autofunction::  combination

.. autofunction::  allcombinations

.. autofunction::  permutation

.. autofunction::  allpermutations

.. autofunction::  value

