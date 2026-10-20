.. _edit_constraints:

How to edit constraints
========================

Once a constraint is added to a problem, the problem keeps its own copy of it.
You change that copy through its :py:class:`~pulp.LpConstraint`, the object the
problem gives back for each of its constraints. **Editing the expression you
added does not change the problem.**

.. contents:: On this page
   :local:
   :depth: 1


Getting the ``LpConstraint``
-----------------------------

There are three ways to get the constraint as stored in the problem:

.. code-block:: python

    from pulp import LpProblem, LpMinimize

    prob = LpProblem("edit", LpMinimize)
    x = prob.add_variable("x", 0, 10)
    y = prob.add_variable("y", 0, 10)

    # 1. keep the one returned by addConstraint
    cap = prob.addConstraint(x + y <= 5, "cap")

    # 2. look it up by name (None if there is no such constraint)
    cap = prob.get_constraint_by_name("cap")

    # 3. take it from the list of all constraints, in the order they were added
    cap = prob.constraints()[0]

``prob += x + y <= 5, "cap"`` adds the constraint too, but returns the problem,
not the constraint. Use ``addConstraint`` when you want to keep the constraint,
or give it a name and look it up afterwards:

.. code-block:: python

    prob += x + y <= 5, "cap"
    cap = prob.get_constraint_by_name("cap")
    cap[x] = 2              # the problem now has 2*x + y <= 5

All three give an object for the same row of the problem: an edit made through
one is visible through the others.


What you can change
--------------------

.. code-block:: python

    cap = prob.addConstraint(x + y <= 5, "cap")   # x + y <= 5

    cap[x] = 2              # 2*x + y <= 5     set a coefficient
    del cap[y]              # 2*x <= 5         remove a term
    cap[y] = 0              # same as del: a coefficient of 0 removes the term
    cap.changeRHS(8)        # 2*x <= 8         set the right-hand side
    cap += 3 * y            # 2*x + 3*y <= 8   add terms to the left-hand side
    cap -= 1                # 2*x + 3*y <= 9   (the left-hand side gets -1)
    cap.sense = LpConstraintGE   # 2*x + 3*y >= 9

* ``cap[x] = value`` and ``cap.set_coefficient(x, value)`` are the same. If
  ``x`` is not in the constraint yet, it is added.
* ``changeRHS(rhs)`` sets the right-hand side. You can also set
  ``cap.constant``, which is the constant on the left-hand side, so
  ``cap.constant = -8`` is the same as ``cap.changeRHS(8)``.
* ``+=`` and ``-=`` accept anything you can add to an expression: a variable, an
  expression, a number, or a list or dict of them. Numbers go to the left-hand
  side, so they move the right-hand side the other way.
* The sense is ``LpConstraintLE``, ``LpConstraintGE`` or ``LpConstraintEQ``
  (from ``pulp``).
* The name can be changed with ``cap.name = "new_name"``.

Each change is checked before it is applied. An invalid change, such as an
infinite or NaN coefficient, a variable from another problem, or
``cap.sense = None``, raises ``PulpError`` and leaves the constraint as it was.

The dual value (``cap.pi``) and the slack (``cap.slack``) of the last solve are
kept after an edit, and the next solve replaces them.


Example: re-solving with new data
----------------------------------

A common use is to solve a model several times with a different right-hand
side:

.. code-block:: python

    demand = prob.addConstraint(lpSum(flow[w]["bar_1"] for w in warehouses) >= 500, "demand_bar_1")

    for value in range(500, 601, 10):
        demand.changeRHS(value)
        stats = prob.solve()
        print(value, stats.objective)

See ``examples/BeerDistributionProblem_resolve.py`` for the complete script.


What does not work: editing the expression
-------------------------------------------

``addConstraint`` (and ``prob += ...``) **copies** the expression into the
problem. Changing the expression afterwards changes only the expression:

.. code-block:: python

    c = x + y <= 5
    prob += c, "c"

    c[x] = 3               # UserWarning; the problem still has x + y <= 5
    c.changeRHS(8)         # UserWarning; same

PuLP warns you when you edit an expression that has a sense (one created with
``<=``, ``>=`` or ``==``), because that is usually this mistake:

.. code-block:: text

    UserWarning: Editing an LpAffineExpression with a sense does not change any
    problem it was added to. To edit a constraint in a problem, edit its
    LpConstraint: get it with prob.get_constraint_by_name(name) or
    prob.constraints(), or keep the one returned by prob.addConstraint(...);
    then e.g. con[x] = 2 or con.changeRHS(3).

To fix the code, edit the ``LpConstraint`` instead:

.. code-block:: python

    c = prob.addConstraint(x + y <= 5, "c")
    c[x] = 3               # the problem now has 3*x + y <= 5

or, if the constraint was added with ``prob += ...``, look it up by name:

.. code-block:: python

    prob += x + y <= 5, "c"
    c = prob.get_constraint_by_name("c")
    c[x] = 3               # the problem now has 3*x + y <= 5

The expression does not know whether it was added to a problem, so the warning
also appears when you edit an expression with a sense **before** adding it:

.. code-block:: python

    c = x <= 5
    c += y                 # UserWarning, although c was not added yet

Build the whole expression before turning it into a constraint, or edit the
``LpConstraint`` after adding it:

.. code-block:: python

    c = x + y <= 5                         # no warning
    c = prob.addConstraint(x <= 5, "c")
    c += y                                 # no warning: edits the problem

Expressions without a sense, such as an objective or ``x + 2 * y``, never warn.
Operators that build a new constraint (``x + y <= 5``, ``-c``,
``c + y``) do not warn either, because they leave ``c`` unchanged.

.. note::

    In PuLP 3.x the problem stored the expression object itself, so editing it
    changed the problem. Code written that way still runs in PuLP 4, but the
    edits no longer reach the problem. The warning shows you where.


Adding variables to existing constraints
-----------------------------------------

``cap[x] = value`` also works for a variable created after the constraint. To add
a new variable to several constraints and to the objective in one call, use
``prob.add_column``; see :ref:`column_wise`.
