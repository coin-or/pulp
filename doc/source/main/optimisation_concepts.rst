Optimisation Concepts
=====================

Linear Programing
-----------------
The simplest type of mathematical program is a linear program. For your 
mathematical program to be a linear program you need the following 
conditions to be true:

* The decision variables must be real variables;
* The objective must be a linear expression;
* The constraints must be linear expressions. 

Linear expressions are any expression of the form

.. math::

    a_1 x_1 + a_2 x_2 + a_3 x_3 + ... a_n x_n \{<= , =, >=\} b 
	 
where the :math:`a_i` and :math:`b` are known constants and :math:`x_i` are variables. The process 
of solving a linear program is called linear programing. Linear programing 
is done via the Revised Simplex Method (also known as the Primal Simplex Method), 
the Dual Simplex Method or an Interior Point Method. Some solvers like cplex 
allow you to specify which method you use, but we won’t go into further detail 
here.

Integer Programing
------------------

Integer programs are almost identical to linear programs with one very 
important exception. Some of the decision variables in integer programs may 
need to have only integer values. The variables are known as integer variables. 
Since most integer programs contain a mix of continuous variables and integer 
variables they are often known as mixed integer programs. While the change 
from linear programing is a minor one, the effect on the solution process is 
enormous. Integer programs can be very difficult problems to solve and there 
is a lot of current research finding “good” ways to solve integer programs. 
Integer programs can be solved using the branch-and-bound process.

Note For MIPs of any reasonable size the solution time grows 
exponentially as the number of integer variables increases. 

