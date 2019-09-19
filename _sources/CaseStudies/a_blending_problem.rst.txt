A Blending Problem 
===================

Problem Description
-------------------

.. image:: images/whiskas_label.jpg

Whiskas cat food, shown above, is manufactured by Uncle Ben’s. 
Uncle Ben’s want to produce their cat food products as cheaply as possible 
while ensuring they meet the stated nutritional analysis requirements 
shown on the cans. Thus they want to vary the quantities of each 
ingredient used (the main ingredients being chicken, beef, mutton, 
rice, wheat and gel) while still meeting their nutritional standards.

.. image:: images/whiskas_blend.jpg

The costs of the chicken, beef, and mutton are $0.013, $0.008 and
$0.010 respectively, while the costs of the rice, wheat and gel are
$0.002, $0.005 and $0.001 respectively. (All costs are per gram.) For
this exercise we will ignore the vitamin and mineral ingredients. (Any
costs for these are likely to be very small anyway.)

Each ingredient contributes to the total weight of protein, fat,
fibre and salt in the final product. The contributions (in grams) per
gram of ingredient are given in the table below.


    ============ ========= ========= ======== ======= 
     Stuff        Protein   Fat       Fibre    Salt   
    ============ ========= ========= ======== ======= 
     Chicken      0.100     0.080     0.001    0.002  
     Beef         0.200     0.100     0.005    0.005  
     Rice         0.000     0.010     0.100    0.002  
     Wheat bran   0.040     0.010     0.150    0.008  
    ============ ========= ========= ======== ======= 

Simplified Formulation 
~~~~~~~~~~~~~~~~~~~~~~

First we will consider a simplified problem to build a simple Python model.

Identify the Decision Variables
+++++++++++++++++++++++++++++++++++

Assume Whiskas want to make their cat food out of just two ingredients: 
Chicken and Beef. We will first define our decision variables:

.. math::

      x_1 &=  \text{ percentage of chicken meat in a can of cat food }\\
      x_2 &= \text{ percentage of beef used in a can of cat food }
   
The limitations on these variables (greater than zero) must be noted but 
for the Python implementation, they are not entered or listed separately or with the other constraints.
   
Formulate the Objective Function
++++++++++++++++++++++++++++++++

The objective function becomes:

.. math:: \textbf{ min } 0.013 x_1 + 0.008 x_2

The Constraints
+++++++++++++++

The constraints on the variables are that they must sum to 100 and that the nutritional requirements are met:
   
.. math::

   1.000 x_1  + 1.000 x_2 &= 100.0\\
   0.100 x_1  + 0.200 x_2 &\ge 8.0\\
   0.080 x_1  + 0.100 x_2 &\ge 6.0\\
   0.001 x_1  + 0.005 x_2 &\le 2.0\\
   0.002 x_1  + 0.005 x_2 &\le 0.4\\

Solution to Simplified Problem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To obtain the solution to this Linear Program, we can write a short
program in Python to call PuLP's modelling functions, which will then
call a solver. This will explain step-by-step how to write this Python
program. It is suggested that you repeat the exercise yourself. The code
for this example is found in `WhiskasModel1.py <https://projects.coin-or.org/PuLP/browser/trunk/examples/WhiskasModel1.py?format=txt>`_

The start of the your file should then be headed with a short commenting section outlining the purpose of the program. For example:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 1-5
   
Then you will import PuLP's functions for use in your code:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 7-8

A variable called ``prob`` (although its name is not important) is
created using the :class:`~pulp.LpProblem` function. It has two parameters, the first
being the arbitrary name of this problem (as a string), and the second
parameter being either ``LpMinimize`` or ``LpMaximize`` depending on the
type of LP you are trying to solve:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 10-11

The problem variables ``x1`` and ``x2`` are created using the
:class:`~pulp.LpVariable` class. It has four parameters, the first is the
arbitrary name of what this variable represents, the second is the lower
bound on this variable, the third is the upper bound, and the fourth
is essentially the type of data (discrete or continuous). The options
for the fourth parameter are ``LpContinuous`` or ``LpInteger``, with the
default as ``LpContinuous``. If we were modelling the number of cans
to produce, we would need to input ``LpInteger`` since it is discrete
data. The bounds can be entered directly as a number, or ``None`` to
represent no bound (i.e. positive or negative infinity), with ``None``
as the default. If the first few parameters are entered and the rest
are ignored (as shown), they take their default values. However, if you
wish to specify the third parameter, but you want the second to be the
default value, you will need to specifically set the second parameter as
it's default value. i.e you cannot leave a parameter entry blank.
e.g::

    LpVariable("example", None, 100)

or::

    LpVariable("example", upBound = 100)

To explicitly create the two variables needed for this problem:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 13-15

The variable ``prob`` now begins collecting problem data with the
``+=`` operator. The objective function is logically entered first, with
an important comma ``,`` at the end of the statement and a short string
explaining what this objective function is:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 17-18
   
The constraints are now entered (Note: any "non-negative"
constraints were already included when defining the variables). This is
done with the '+=' operator again, since we are adding more data to the
``prob`` variable. The constraint is logically entered after this, with a
comma at the end of the constraint equation and a brief description of
the cause of that constraint:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 20-25

Now that all the problem data is entered, the :meth:`~pulp.LpProblem.writeLP` function
can be used to copy this information into a .lp file into the directory
that your code-block is running from. Once your code runs successfully, you
can open this .lp file with a text editor to see what the above steps were
doing. You will notice that there is no assignment operator (such as an
equals sign) on this line. This is because the function/method called
:meth:`~pulp.LpProblem.writeLP` is being performed to the
variable/object ``prob`` (and the
string ``"WhiskasModel.lp"`` is an additional parameter). The dot ``.``
between the variable/object and the function/method is important and is
seen frequently in Object Oriented software (such as this):


.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 27-28

The LP is solved using the solver that PuLP chooses. The input
brackets after :meth:`~pulp.LpProblem.solve` are left empty in this case, however they can be
used to specify which solver to use (e.g ``prob.solve(CPLEX())`` ):

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 30-31

Now the results of the solver call can be displayed as output to
us. Firstly, we request the status of the solution, which can be one of
"Not Solved", "Infeasible", "Unbounded", "Undefined" or "Optimal". The
value of ``prob`` (:attr:`pulp.pulp.LpProblem.status`) is returned as an integer, which must be converted
to its significant text meaning using the
:attr:`~pulp.constants.LpStatus` dictionary. Since
:attr:`~pulp.constants.LpStatus` is a dictionary(:obj:`dict`), its input must be in square brackets:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 33-34

The variables and their resolved optimum values can now be printed
to the screen. 

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 36-38

The ``for`` loop makes ``variable`` cycle through all
the problem variable names (in this case just ``ChickenPercent`` and
``BeefPercent``). Then it prints each variable name, followed by an
equals sign, followed by its optimum value.
:attr:`~pulp.LpVariable.name` and
:attr:`~pulp.LpVariable.varValue` are
properties of the object ``variable``.


The optimised objective function value is printed to the screen,
using the value function. This ensures that the number is in the right
format to be displayed. :attr:`~pulp.LpProblem.objective` is an attribute of the object
``prob``:

.. literalinclude:: ../../../examples/WhiskasModel1.py
    :lines: 40-41

Running this file should then produce the output to show that 
Chicken will make up 33.33%, Beef will make up 66.67% and the 
Total cost of ingredients per can is 96 cents.

Full Formulation
----------------
 
Now we will formulate the problem fully with
all the variables. Whilst it could be implemented into Python with
little addition to our method above, we will look at a better way which
does not mix the problem data, and the formulation as much. This will
make it easier to change any problem data for other tests. We will start
the same way by algebraically defining the problem:

#. Identify the Decision Variables 
   For the Whiskas Cat Food Problem the decision variables are the percentages of 
   the different ingredients we include in the can. 
   Since the can is 100g, these percentages also represent the amount in g of each 
   ingredient included.
   We must formally define our decision variables, being sure to state the units 
   we are using.
      
   .. math::

      x_1 &= \text{percentage of chicken meat in a can of cat food}\\
      x_2 &= \text{percentage of beef used in a can of cat food}\\
      x_3 &= \text{percentage of mutton used in a can of cat food}\\
      x_4 &= \text{percentage of rice used in a can of cat food}\\
      x_5 &= \text{percentage of wheat bran used in a can of cat food}\\
      x_6 &= \text{percentage of gel used in a can of cat food}
      
   Note that these percentages must be between 0 and 100.
#. Formulate the Objective Function
   For the Whiskas Cat Food Problem the objective is to minimise the total cost 
   of ingredients per can of cat food.
   We know the cost per g of each ingredient. We decide the percentage of each 
   ingredient in the can, so we must divide by 100 and multiply by the weight of 
   the can in g. This will give us the weight in g of each
   ingredient:

   .. math::

      \min \$0.013 x_1 + \$0.008 x_2 + \$0.010 x_3 + \$0.002 x_4 + \$0.005 x_5 + \$0.001 x_6

#. Formulate the Constraints
   The constraints for the Whiskas Cat Food Problem are that:

   * The sum of the percentages must make up the whole can (= 100%).
   * The stated nutritional analysis requirements are met.
     
   The constraint for the "whole can" is:

   .. math:: x_1 + x_2 + x_3 + x_4 + x_5 +x _6 = 100

   To meet the nutritional analysis requirements, we need to have at
   least 8g of Protein per 100g, 6g of fat, but no more than 2g of fibre
   and 0.4g of salt.  To formulate these constraints we make use of the
   previous table of contributions from each ingredient. This allows us
   to formulate the following constraints on the total contributions of
   protein, fat, fibre and salt from the ingredients:

   .. math::

      0.100 x_1 +0.200 x_2 +0.150 x_3 +0.000 x_4 +0.040 x_5 +0.0 x_6 0&\ge 8.0 \\
      0.080 x_1 +0.100 x_2 +0.110 x_3 +0.010 x_4 +0.010 x_5 0+0.0 x_6 &\ge 6.0 \\ 
      0.001 x_1 +0.005 x_2 +0.003 x_3 +0.100 x_4 0+0.150 x_5 +0.0 x_6 &\le 2.0 \\
      0.002 x_1 +0.005 x_2 +0.007 x_3 0+0.002 x_4 +0.008 x_5 +0.0 x_6 &\le 0.4

Solution to Full Problem 
~~~~~~~~~~~~~~~~~~~~~~~~

To obtain the solution to this Linear Program, we again write a
short program in Python to call PuLP's modelling functions, which will
then call a solver. This will explain step-by-step how to write this
Python program with it's improvement to the above model. It is suggested
that you repeat the exercise yourself. The code for this example is
found in the `WhiskasModel2.py <https://projects.coin-or.org/PuLP/browser/trunk/examples/WhiskasModel2.py?format=txt>`_

As with last time, it is advisable to head your file with commenting on its 
purpose, and the author name and date. Importing of the PuLP functions is also done in the same way:

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 1-8

Next, before the ``prob`` variable or type of problem are defined,
the key problem data is entered into dictionaries. This includes the
list of Ingredients, followed by the cost of each Ingredient, and it's
percentage of each of the four nutrients. These values are clearly laid
out and could easily be changed by someone with little knowledge of
programming. The ingredients are the reference keys, with the numbers as
the data.

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 10-51

The ``prob`` variable is created to contain the formulation, and the
usual parameters are passed into :obj:`~pulp.LpProblem`.

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 53-54

A dictionary called ``ingredient_vars`` is created which contains
the LP variables, with their defined lower bound of zero. The reference
keys to the dictionary are the Ingredient names, and the data is
``Ingr_IngredientName``. (e.g. MUTTON: Ingr_MUTTON)

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 56-57
   
Since ``costs`` and ``ingredient_vars`` are now dictionaries with the
reference keys as the Ingredient names, the data can be simply extracted
with a list comprehension as shown. The :func:`~pulp.lpSum` function will add the
elements of the resulting list. Thus the objective function is simply
entered and assigned a name:

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 59-60
    
Further list comprehensions are used to define the other 5 constraints, which are also each given names describing them.

.. literalinclude:: ../../../examples/WhiskasModel2.py
    :lines: 62-67
 
Following this, the :ref:`writeLP<writeLP>` line etc follow exactly the same as
in the simplified example.

The optimal solution is 60% Beef and 40% Gel leading to a objective
Function value of 52 cents per can.

