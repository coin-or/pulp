.. _column_wise:

How to model column-wise
=========================

Usually a model is written **row by row**: create the variables, then add each
constraint as an expression over them. Some models are easier to write
**column by column**: each new variable comes with its coefficient in the
objective and in the constraints that already exist. The typical case is column
generation, where a problem is solved, new variables (columns) are priced from
the dual values, and the problem is solved again with those columns added.

PuLP supports this on one problem object, without rebuilding it:

* :py:meth:`~pulp.LpProblem.add_column` creates a variable together with its
  objective coefficient and its coefficients in existing constraints.
* :py:meth:`~pulp.LpConstraint.set_coefficient` (or ``con[x] = value``) sets
  one coefficient of an existing constraint.
* :py:meth:`~pulp.LpProblem.remove_variables` takes variables out of the model.
* ``x.cat = ...`` changes a variable's category, for example to make the final
  problem integer.

.. contents:: On this page
   :local:
   :depth: 1


Adding a column
----------------

Create the constraints first and keep them; ``addConstraint`` returns each one
as stored in the problem. A constraint may start with no terms at all:

.. code-block:: python

    from pulp import LpProblem, LpMinimize, lpSum

    prob = LpProblem("column_wise", LpMinimize)
    x = prob.add_variable("x", 0, 1)
    c1 = prob.addConstraint(x >= 1, "c1")
    c2 = prob.addConstraint(lpSum([]) >= 1, "c2")   # empty for now
    prob += x

    y = prob.add_column("y", lowBound=0, upBound=1, obj=2, coefficients={c1: 1, c2: 1})
    z = prob.add_column("z", lowBound=0, upBound=1, obj=3, coefficients={c2: 1})

    # c1: x + y >= 1
    # c2: y + z >= 1
    # objective: x + 2*y + 3*z

``add_column`` takes the same ``name``, ``lowBound``, ``upBound`` and ``cat`` as
:py:meth:`~pulp.LpProblem.add_variable`, plus:

* ``obj``: the coefficient in the objective (default 0). If the problem has no
  objective yet and ``obj`` is not 0, one is created.
* ``coefficients``: a dict from each ``LpConstraint`` of this problem to the
  coefficient of the new variable in it. Constraints that are not in the dict do
  not get the variable. A coefficient of 0 is skipped.

Everything is checked before the variable is created. If a coefficient is
infinite or NaN, ``add_column`` raises ``ValueError`` and the problem is left as
it was.

The new term goes at the end of each constraint, so a problem built column by
column writes the same LP and MPS files as the same problem built row by row.

Setting one coefficient
------------------------

To put an existing variable into a constraint, or change its coefficient, set
it on the constraint:

.. code-block:: python

    c1[z] = 0.5        # c1: x + y + 0.5*z >= 1
    del c1[x]          # c1: y + 0.5*z >= 1

See :ref:`edit_constraints` for everything you can change on a constraint.


Removing columns
-----------------

``prob.remove_variables(variables)`` takes the variables out of every
constraint, the objective and every SOS group:

.. code-block:: python

    prob.remove_variables([z])

The variables stay valid: you can still read them and put them back with
``c[z] = value``. A variable that no constraint and no objective uses is left
out of the LP and MPS files and is not sent to the solvers.


Example: cutting stock by column generation
--------------------------------------------

Rolls of width 100 are cut into pieces to meet the demand for four widths. Each
variable is a *pattern*: how many pieces of each width are cut from one roll.
There are too many patterns to list, so the problem starts with one simple
pattern per width and adds a better pattern while one exists:

1. Solve the linear relaxation of the master problem and read the duals
   ``pi`` of the demand constraints.
2. Solve a knapsack problem to find the pattern with the largest total dual
   value that fits in a roll.
3. If that value is more than 1 (the cost of one roll), the pattern improves the
   master problem: add it with ``add_column`` and go back to step 1.
4. Otherwise, make the patterns integer and solve once more.

.. code-block:: python

    from pulp import LpInteger, LpMaximize, LpMinimize, LpProblem, getSolver, lpSum

    roll_width = 100
    orders = {"w45": (45, 97), "w36": (36, 610), "w31": (31, 395), "w14": (14, 211)}
    solver = getSolver("HiGHS", msg=False)   # any solver that returns duals

    # Master problem: one pattern per width, as many pieces as fit in a roll.
    master = LpProblem("cutting_stock", LpMinimize)
    patterns = []
    demand = {}
    for item, (width, quantity) in orders.items():
        x = master.add_variable(f"pattern_{len(patterns)}", lowBound=0)
        patterns.append(x)
        demand[item] = master.addConstraint(
            (roll_width // width) * x >= quantity, f"demand_{item}"
        )
    master += lpSum(patterns)

    while True:
        master.solve(solver)
        duals = {item: c.pi for item, c in demand.items()}

        # Pricing: the pattern with the largest total dual value.
        pricing = LpProblem("pricing", LpMaximize)
        n = pricing.add_variable_dicts("n", orders, lowBound=0, cat=LpInteger)
        pricing += lpSum(duals[i] * n[i] for i in orders)
        pricing += lpSum(width * n[i] for i, (width, _) in orders.items()) <= roll_width
        pricing.solve(solver)
        if 1 - pricing.objective.value() >= -1e-9:
            break   # no pattern improves the master problem

        pattern = {i: round(n[i].varValue) for i in orders}
        new = master.add_column(
            f"pattern_{len(patterns)}",
            lowBound=0,
            obj=1,
            coefficients={demand[i]: k for i, k in pattern.items() if k},
        )
        patterns.append(new)

    print("LP bound:", master.objective.value())   # 452.25

    # Make the patterns integer and solve the final problem.
    for x in patterns:
        x.cat = LpInteger
    stats = master.solve(solver)
    print("rolls:", stats.objective)                # 453.0

The loop adds two patterns before no further improvement is possible. The same
``master`` problem is solved each time: it is never rebuilt, and the demand
constraints found in step 1 are the ones the new columns are added to.


Notes
------

* The coefficients of ``add_column`` are given per ``LpConstraint``, so keep the
  constraints when you create them (``addConstraint`` returns them), or look
  them up with ``prob.get_constraint_by_name(name)``.
* Duals and slacks are only available from solvers that return them, and only
  for linear problems. Solve the relaxation (continuous variables) while
  generating columns, then change the category with ``x.cat = LpInteger``.
* Editing a constraint, adding a column or changing a category keeps the
  values (``varValue``, ``pi``, ``slack``) of the last solve until the next one.
* In PuLP 3.x column-wise modelling used ``LpConstraintVar`` and
  ``LpVariable(..., e=...)``. Both were removed in 4.0; ``add_column`` replaces
  them.
