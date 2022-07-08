How to warm-start a solver
======================================

Many solvers permit the possibility of giving a valid (or parcially valid in some cases) solution so the solver can start from that solution. This can lead to performance gains.


Supported solver APIs
-----------------------

The present solver APIs that work with PuLP warm-start are the following: ``CPLEX_CMD``, ``GUROBI_CMD``, ``PULP_CBC_CMD``, ``CBC_CMD``, ``CPLEX_PY``, ``GUROBI``, ``XPRESS``.

Example problem
----------------

We will use as example the model in :ref:`set-partitioning-problem`. At the end is the complete modified code.


Filling a variable with a value
--------------------------------

If a model has been previously solved, each variable has already a value. To check the value of a variable we can do it via the ``value`` method of the variable.

In our example, if we solve the problem, we could just do the following afterwards:

.. code-block:: python

    x[('O', 'P', 'Q', 'R')].value() # 1.0
    x[('K', 'N', 'O', 'R')].value() # 0.0

If we have not yet solved the model, we can use the ``setInitialValue`` method to assign a value to the variable.

In our example, if we want to get those two same values, we would do the following:

.. code-block:: python

    x[('O', 'P', 'Q', 'R')].setInitialValue(1)
    x[('K', 'N', 'O', 'R')].setInitialValue(0)


Activating MIP start
---------------------

Once we have assigned values to all variables and we want to run a model while reusing those values, we just need to pass the ``warmStart=True`` argument to the solver when initiating it.

For example, using the default PuLP solver we would do:

.. code-block:: python

    seating_model.solve(pulp.PULP_CBC_CMD(msg=True, warmStart=True))

I usually turn ``msg=True`` so I can see the messages from the solver confirming it loaded the solution correctly.

Fixing a variable
-------------------

Assigning values to variables also permits fixing those variables to that value. In order to do that, we use the ``fixValue`` method of the variable.

For our example, if we know some variable needs to be 1, we can do:


.. code-block:: python

    _variable = x[('O', 'P', 'Q', 'R')]
    _variable.setInitialValue(1)
    _variable.fixValue()

This implies setting the lower bound and the upperbound to the value of the variable.


Whole Example
-------------

If you want to see the complete code of the warm start version of the example, :download:`click here <../../../examples/wedding_initial.py>` or see below.

.. literalinclude:: ../../../examples/wedding_initial.py
