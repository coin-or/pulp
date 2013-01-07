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
   LpConstraint.makeElasticSubProblem
   FixedElasticSubProblem

.. todo::   LpFractionConstraint, FractionElasticSubProblem

The LpProblem Class
-------------------

.. autoclass:: LpProblem
   :show-inheritance:

   Three important attributes of the problem are:

   .. attribute:: objective

      The objective of the problem, an :obj:`LpAffineExpression`

   .. attribute:: constraints

      An :class:`ordered dictionary<odict.OrderedDict>` of
      :class:`constraints<LpConstraint>` of the problem - indexed by their names.

   .. attribute:: status 

      The return :data:`status <pulp.constants.LpStatus>`
      of the problem from the solver.

   Some of the more important methods:

   .. automethod:: solve
   .. automethod:: roundSolution
   .. automethod:: setObjective
   .. automethod:: writeLP

Variables and Expressions
-------------------------

.. autoclass:: LpElement
    :members:

----

.. autoclass:: LpVariable
   :members:

Example:

>>> x = LpVariable('x',lowBound = 0, cat='Continuous')
>>> y = LpVariable('y', upBound = 5, cat='Integer')

gives  :math:`x \in [0,\infty)`, :math:`y \in (-\infty, 5]`, an
integer.

----

.. autoclass:: LpAffineExpression
   :show-inheritance:

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
   :members: makeElasticSubProblem

.. include::  documentation/elastic.rst

.. autoclass:: FixedElasticSubProblem
   :show-inheritance:
   :members:

Combinations  and Permutations
------------------------------

.. autofunction::  combination

.. autofunction::  allcombinations

.. autofunction::  permutation

.. autofunction::  allpermutations

.. autofunction::  value

