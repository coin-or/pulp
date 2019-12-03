A Two Stage Production Planning Problem
============================

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



A set partitioning problem determines how the items in one set (S) can be partitioned into smaller 
subsets. All items in S must be contained in one and only one partition. Related problems are:

+ set packing - all items must be contained in zero or one partitions;
+ set covering - all items must be contained in at least one partition.

In this case study a wedding planner must determine guest seating allocations 
for a wedding. To model this problem the tables are modelled as the partitions 
and the guests invited to the wedding are modelled as the elements of S. The 
wedding planner wishes to maximise the total happiness of all of the tables. 

A set partitioning problem may be modelled by explicitly enumerating each
possible subset. Though this approach does become intractable for large numbers
of items (without using column generation) it does have the advantage that the
objective function co-efficients for the partitions can be non-linear 
expressions (like happiness) and still allow this problem to be solved
using Linear Programming.

First we use :func:`~pulp.allcombinations` to generate a list of all 
possible table seatings.

.. literalinclude:: ../../../examples/wedding.py
    :lines: 20-22

Then we create a binary variable that will be 1 if the table will be in the solution, or zero otherwise.

.. literalinclude:: ../../../examples/wedding.py
    :lines: 24-28

We create the :class:`~pulp.LpProblem` and then make the objective function. Note that
happiness function used in this script would be difficult to model in any other way.

.. literalinclude:: ../../../examples/wedding.py
    :lines: 30-32

We specify the total number of tables allowed in the solution.

.. literalinclude:: ../../../examples/wedding.py
    :lines: 34-35

This set of constraints defines the set partitioning problem by guaranteeing that a guest is allocated to
exactly one table.

.. literalinclude:: ../../../examples/wedding.py
    :lines: 38-41
    
The full file can be found here `wedding.py <https://projects.coin-or.org/PuLP/browser/trunk/examples/wedding.py?format=txt>`_

.. literalinclude:: ../../../examples/wedding.py




