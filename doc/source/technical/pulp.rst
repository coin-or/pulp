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

   Three important attributes of the problem are:

   .. attribute:: objective

      The objective of the problem, an :obj:`LpAffineExpression`

   .. attribute:: constraints

      A :class:`list` of :class:`constraints<LpConstraint>` in model order (same order as rows in the Rust core).

   .. attribute:: status 

      The return :data:`status <pulp.constants.LpStatus>`
      of the problem from the solver.

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


Combinations  and Permutations
------------------------------

.. autofunction::  combination

.. autofunction::  allcombinations

.. autofunction::  permutation

.. autofunction::  allpermutations

.. autofunction::  value

