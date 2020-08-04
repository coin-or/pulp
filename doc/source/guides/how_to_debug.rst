How to debug most errors during solving
===========================================

Here I will put all the main questions and advice from years of solving and helping other solve problems with PuLP. Additional answers can be added via a PR.

Giving feedback and asking for help
----------------------------------------

The three ways one can ask for help or report a problem are:

1. The PuLP mailing list: 
2. The github issues page:
3. Stack Overflow `pulp` tag: 

Several things need to be taken into account while asking for help, some of them are common to any library, other are particular to PuLP.
General pointers (that are nonetheless, very important):

1. Always submit a mininum reproducible example (`how to here <https://stackoverflow.com/help/minimal-reproducible-example>`_).
2. Check `this video <https://www.youtube.com/watch?v=Qbr4Vnsi2xY>`_ on how to ask questions. Although aimed to another programming language, the message and recommendations are very good.

Now, specifically to PuLP:

1. Pass the `msg=1` argument to the solver, i.e., `prob.solve(PULP_CBC_CMD(msg=1))`. This will give you more information on the error. Share this information when asking for help.
1. If possible, share an export version of the model. Check `here <https://coin-or.github.io/pulp/guides/how_to_export_models.html>`_ how to export one.
2. Alternatively, share a `mps` version of your model. To produce one, use `writeMPS <https://coin-or.github.io/pulp/technical/pulp.html#pulp.LpProblem.writeMPS>`_.

Other information that is also useful:

1. Version of `pulp`.
2. How did you install `pulp` (via pypi, or from github).
3. What operating system was used.
4. The version of the solver being used (e.g., CPLEX 12.8).


Error while trying to execute cbc.exe
------------------------------------

The complete message is usually something like `pulp.solvers.PulpSolverError: Pulp: Error while trying to execute PATH_TO_CBC/cbc.exe`.

The default solver is CBC and is run via the command line.

1. First of all, pass the `msg=1` argument to the solver, to get more information.
2. **Check the precision of the numbers**. If you have very big numbers (with a high precision), this generally causes problems with solvers. For example, never use a parameter that is `100000000000` inside your problem. Specially if you then have another one that has `1200.09123642123`. If you do not need decimals, round your values when building the model.
3. **Duplicated variables / constraints**. If you have variables that have the same coefficients in *all* constraints and in the objective function, this is an issue. Also, if you have two constraints that have exactly the same variables and coefficients.
4. **Memory issues**. Sometimes your pc runs out of memory. Check if this is the case.
5. **python32 vs python64**. Sometimes you're using the 32-bit version of python, even if your pc is 64-bit. Try to always use the 64-bit if possible, since it handles more memory.
5. **Generate an mps file with PuLP** and pass it to the cbc.exe executable directly like so::

    cbc.exe mpsfile.mps

And see what message you get.

6. Finally, sometimes you may want to try PuLP with a more recent version of CBC. To do this, download the CBC binary and pass the path to it to PuLP.

Infeasible problems
*********************

1. add slack variables. As described here:




