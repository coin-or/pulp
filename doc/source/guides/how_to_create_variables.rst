.. _create_variables:

How to create variables
========================

In PuLP 4 variables are created **by the problem** and belong to it. Create the
problem first, then its variables:

.. code-block:: python

    from pulp import LpProblem, LpMinimize, LpBinary, LpInteger

    prob = LpProblem("example", LpMinimize)
    x = prob.add_variable("x", lowBound=0, upBound=10)

A variable cannot be used in another problem. Adding an expression that uses a
variable from another problem raises ``PulpError``.

.. contents:: On this page
   :local:
   :depth: 1


One variable: ``add_variable``
-------------------------------

:py:meth:`~pulp.LpProblem.add_variable` takes a name, the bounds and the
category:

.. code-block:: python

    x = prob.add_variable("x", lowBound=0)                 # x >= 0
    y = prob.add_variable("y", upBound=5, cat=LpInteger)   # integer, y <= 5
    z = prob.add_variable("z", cat=LpBinary)               # 0 or 1

* ``lowBound`` and ``upBound`` default to ``None``, which means no bound. A bound
  must be finite; pass ``None`` instead of ``float("inf")``.
* ``cat`` is ``"Continuous"`` (default), ``"Integer"`` or ``"Binary"``. A binary
  variable is stored as an integer variable with bounds 0 and 1, so ``z.cat``
  returns ``"Integer"``. Use ``z.isBinary()`` to check for binaries.
* The variable is part of the problem as soon as it is created, even if no
  constraint uses it yet.


Many variables: ``add_variable_dicts``
---------------------------------------

Most models need one variable per item, or per combination of items.
:py:meth:`~pulp.LpProblem.add_variable_dicts` creates them all in one call and
returns them in a dictionary keyed by the index values. Use it in place of the
3.x ``LpVariable.dicts``. The arguments are:

* ``name``: the prefix of the variable names.
* ``indices``: one iterable of index values, or a tuple of iterables for
  several indices.
* ``lowBound``, ``upBound``, ``cat``: the same as for ``add_variable``. They
  apply to every variable.

With one index you get a flat dictionary. Each name is the prefix and the index
value joined by ``_``:

.. code-block:: python

    warehouses = ["A", "B"]
    bars = [1, 2, 3]

    buy = prob.add_variable_dicts("buy", warehouses, lowBound=0)
    # {'A': buy_A, 'B': buy_B}
    buy["A"]          # the variable called buy_A

With a tuple of indices you get **nested** dictionaries, one level per index:

.. code-block:: python

    flow = prob.add_variable_dicts("flow", (warehouses, bars), lowBound=0, cat=LpInteger)
    flow["A"][2]      # the variable called flow_A_2
    flow["A"]         # {1: flow_A_1, 2: flow_A_2, 3: flow_A_3}

The nested dictionaries work well with ``lpSum``:

.. code-block:: python

    from pulp import lpSum

    supply = {"A": 1000, "B": 4000}
    demand = {1: 500, 2: 900, 3: 1800}
    for w in warehouses:
        prob += lpSum(flow[w][b] for b in bars) <= supply[w], f"supply_{w}"
    for b in bars:
        prob += lpSum(flow[w][b] for w in warehouses) >= demand[b], f"demand_{b}"

Choosing the names
~~~~~~~~~~~~~~~~~~~

If ``name`` contains ``%s``, PuLP fills in one ``%s`` per index instead of
adding ``_%s`` for each:

.. code-block:: python

    route = prob.add_variable_dicts("route_%s_to_%s", (warehouses, bars))
    route["B"][3].name   # 'route_B_to_3'

Index values are converted with ``str()``, and characters that LP and MPS files
cannot hold, such as spaces, are replaced by ``_``. For example, the index
``"new york"`` gives the name ``ship_new_york``. Give each family of variables
its own prefix. Two variables with the same name are accepted, but
``writeLP``, ``writeMPS`` and the solvers that go through those files raise
``PulpError: Repeated variable names``.

Binary variables
~~~~~~~~~~~~~~~~~

``cat=LpBinary`` creates integer variables with bounds 0 and 1 in every level of
the dictionary:

.. code-block:: python

    is_open = prob.add_variable_dicts("open", warehouses, cat=LpBinary)
    is_open["A"].isBinary()   # True


Other shapes: ``add_variable_dict`` and ``add_variable_matrix``
----------------------------------------------------------------

Both take the same arguments as ``add_variable_dicts``:

* :py:meth:`~pulp.LpProblem.add_variable_dict` returns **one flat dictionary**
  keyed by tuples, one key per combination of the indices:

  .. code-block:: python

      assign = prob.add_variable_dict("assign", (warehouses, bars), cat=LpBinary)
      assign["A", 1]    # the variable called assign_A_1

* :py:meth:`~pulp.LpProblem.add_variable_matrix` returns **nested lists**, indexed
  by position instead of by value:

  .. code-block:: python

      grid = prob.add_variable_matrix("grid", (warehouses, bars))
      grid[0][1]        # the variable called grid_A_2

Use whichever shape makes your constraints easier to write.
``add_variable_dicts`` is the usual choice.


Changing a variable after it is created
----------------------------------------

The bounds and the category of a variable can be changed later. This is useful,
for example, to solve the linear relaxation of a problem and then make it
integer again:

.. code-block:: python

    x.lowBound = 2
    x.upBound = None        # no upper bound
    x.cat = LpInteger
    x.cat = "Continuous"    # relax it
    x.cat = LpBinary        # integer with bounds 0 and 1

To add a variable to constraints that already exist, see :ref:`column_wise`.
