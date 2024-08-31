.. pulp_sphinx documentation master file, created by
   sphinx-quickstart on Sun Nov  1 14:59:49 2009.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Optimization with PuLP
----------------------

PuLP is an linear and mixed integer programming modeler written in Python.

With PuLP, it is simple to create MILP optimisation problems and solve them with the
latest open-source (or proprietary) solvers.  PuLP can generate MPS or LP files and
call solvers such as GLPK_, COIN-OR CLP/`CBC`_, CPLEX_, GUROBI_, MOSEK_, XPRESS_,
CHOCO_, MIPCL_, HiGHS_, SCIP_/FSCIP_.

Here are some ways to get started using PuLP:

* for instructions about installing PuLP see :ref:`installation`.
* If you're new to Python and optimisation we recommend that you read :ref:`optimisation_concepts`, :ref:`optimisation_process`, and the :ref:`getting_started_with_python`. 
* If you want to jump right in then start reading the case studies starting with :ref:`blending_problem`. 

The full PuLP API documentation is available, and useful functions
are also explained in the case studies.
The case studies are in order, so the later case studies will assume you have
(at least) read the earlier case studies. However, we will provide links to any
relevant information you will need.

.. toctree::
   :maxdepth: 2

   main/index
   CaseStudies/index
   guides/index
   develop/index
   technical/index
   plugins/index
   
Authors
=======

The authors of this documentation (the pulp documentation team) include:

.. include:: AUTHORS.txt


.. _GLPK: http://www.gnu.org/software/glpk/glpk.html
.. _CBC: https://github.com/coin-or/Cbc
.. _CPLEX: http://www.cplex.com/
.. _GUROBI: http://www.gurobi.com/
.. _MOSEK: https://www.mosek.com/
.. _XPRESS: https://www.fico.com/es/products/fico-xpress-solver
.. _CHOCO: https://choco-solver.org/
.. _MIPCL: http://mipcl-cpp.appspot.com/
.. _SCIP: https://www.scipopt.org/
.. _HiGHS: https://highs.dev
.. _FSCIP: https://ug.zib.de
