A Two Stage Production Planning Problem
=======================================

In a production planning problem, the decision maker must decide how to purchase material,
labor, and other resources in order to produce end products to maximize profit.

In this case study a company (GTC) produces wrenches and pliers,
subject to the availability of steel, machine capabilities (molding and assembly),
labor, and market demand.  GTC would like to determine how much steel to purchase.
Complicating the problem is that the available assembly capacity and the
product contribution to earnings are unknown presently,
but will be known at the beginning of the next period.

So, in this period, GTC must:

* determine how much steel to purchase.

At the beginning of the next period, after GTC finds out how much assembly capacity is available and
the revenue per unit of wrenches and pliers, GTC will determine

* How many wrenches and pliers to produce.

The uncertainty is expressed as one of four possible scenarios, each with equal probability.

We begin by importing the `PuLP` package.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 29-31

Next, we will read in the data.  Here, we read in the data as vectors.
In actual use, this may be read from databases.  First, the data
elements that do not change with scenarios.  These each have two
values, one corresponding to wrenches, the other pliers.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 33-42

The next set of parameters are those that correspond to the four scenarios.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 43-47

Next, we will create lists that represent the combination of products and
scenarios. These will later be used to create dictionaries for the
parameters.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 49-51

Next, we use `dict(zip(...))` to convert these lists to dictionaries.  This
is done so that we can refer to parameters by meaningful names.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 54-58

To define our decision variables, we use the function `pulp.LpVariable.dicts()`,
which creates dictionaries with associated indexing values.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 61-63


We create the :class:`~pulp.LpProblem` and then make the objective function.
Note that this is a maximization problem, as the goal is to maximize net revenue.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 66

The objective function is specified using the `pulp.lpSum()` function. Note
that it is added to the problem using `+=`.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 69-72

We then add in constraints.  Constraints here in sets based on scenarios
and products and are specified using the `for i in list:` notation.
Within each constraint, summations are expressed using list comprehensions.
Note that constraints are differentiated from the objective function as each
constraint ends in a logical comparison (usually <= or >=, but can be ==) while
Finally, here, the file gives each constraint a name which includes the specific
scenario or product the constraint applies to.

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
    :lines: 73-85


The full file can be found here :download:`Two_stage_Stochastic_GemstoneTools.py <../../../examples/Two_stage_Stochastic_GemstoneTools.py>`

.. literalinclude:: ../../../examples/Two_stage_Stochastic_GemstoneTools.py
