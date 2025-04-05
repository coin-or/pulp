.. _set-partitioning-problem:

A Set Partitioning Problem
============================

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
    :start-after: # BEGIN possible_tables
    :end-before: # END possible_tables

Then we create a binary variable that will be 1 if the table will be in the solution, or zero otherwise.

.. literalinclude:: ../../../examples/wedding.py
    :start-after: # BEGIN define_x
    :end-before: # END define_x

We create the :class:`~pulp.LpProblem` and then make the objective function. Note that
happiness function used in this script would be difficult to model in any other way.

.. literalinclude:: ../../../examples/wedding.py
    :start-after: # BEGIN class_and_obj_fn
    :end-before: # END class_and_obj_fn


We specify the total number of tables allowed in the solution.

.. literalinclude:: ../../../examples/wedding.py
    :start-after: # BEGIN total_table_constraint
    :end-before: # END total_table_constraint

This set of constraints defines the set partitioning problem by guaranteeing that a guest is allocated to
exactly one table.

.. literalinclude:: ../../../examples/wedding.py
    :start-after: # BEGIN exactly_one_table_constraint
    :end-before: # END exactly_one_table_constraint
    
The full file can be found here :download:`wedding.py <../../../examples/wedding.py>`

.. literalinclude:: ../../../examples/wedding.py

