.. _migrate_to_v4:

How to migrate from PuLP 3.x to 4.0
======================================

PuLP 4.0 moves the model into a Rust core. Most modelling code keeps working:
``prob += ...``, ``lpSum``, ``lpDot``, ``value``, constraint names, ``writeLP``,
``writeMPS`` and the solver classes are the same. The breaking changes are in
four places:

* variables are created **by the problem** (``prob.add_variable(...)``), not with
  ``LpVariable(...)``,
* ``prob.constraints`` is a **method that returns a list**, not a dict,
* ``solve()`` returns an :py:class:`~pulp.LpSolveStats` object instead of an
  integer, and the status constants are replaced by the ``LpSolveStatus`` enum,
* CBC is no longer bundled: ``PULP_CBC_CMD`` is gone, use ``COIN_CMD``.

This guide lists every breaking change with the code to write instead.

.. contents:: On this page
   :local:
   :depth: 1


Before you upgrade: run 3.3.2 with warnings on
-----------------------------------------------

PuLP 3.3.1 and 3.3.2 emit a ``DeprecationWarning`` for most of the calls that
4.0 removes, and they already include the new methods (``add_variable``,
``add_variable_dicts``, ``constraints()``...). The smoothest path is:

1. Install ``pulp==3.3.2`` and run your code (or your tests) with warnings
   turned into errors::

       python -W error::DeprecationWarning my_model.py

2. Fix every warning using the sections below. Your code now runs on both 3.3.2
   and 4.0 for the modelling part.
3. Upgrade to 4.0 and update the code that reads the solve result
   (see `Solving and reading the status`_), which cannot be written in a way
   that works on both versions.

Remove any call to ``set_v4_migration_warnings(...)`` when you upgrade: the
function does not exist in 4.0.


Quick reference
----------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - PuLP 3.x
     - PuLP 4.0
   * - ``x = LpVariable("x", 0, 10)``
     - ``x = prob.add_variable("x", 0, 10)``
   * - ``LpVariable.dicts("x", idx, 0)``
     - ``prob.add_variable_dicts("x", idx, 0)``
   * - ``LpVariable.dict("x", idx, 0)``
     - ``prob.add_variable_dict("x", idx, 0)``
   * - ``LpVariable.matrix("x", idx, 0)``
     - ``prob.add_variable_matrix("x", idx, 0)``
   * - ``prob.addVariable(x)`` / ``prob.addVariables(xs)``
     - not needed: variables belong to the problem that created them
   * - ``LpAffineExpression({x: 1, y: 2}, constant=3)``
     - ``LpAffineExpression.from_dict({x: 1, y: 2}, constant=3)``
   * - ``LpConstraint(e, LpConstraintLE, "c", 5)``
     - ``prob += e <= 5, "c"``
   * - ``prob.constraints["c"]``
     - ``prob.get_constraint_by_name("c")``
   * - ``prob.constraints.values()``
     - ``prob.constraints()``
   * - ``status = prob.solve()``
     - ``stats = prob.solve()``
   * - ``prob.status``
     - ``stats.status``
   * - ``LpStatus[prob.status]``
     - ``stats.status_str``
   * - ``LpStatusOptimal``, ``LpStatusInfeasible``, ...
     - ``LpSolveStatus.Optimal``, ``LpSolveStatus.Infeasible``, ...
   * - ``prob.sol_status``, ``LpSolution*``
     - ``stats.has_solution``
   * - ``prob.solutionTime`` / ``prob.solutionCpuTime``
     - ``stats.time`` / ``stats.cpu_time``
   * - ``prob.bestBound``
     - ``stats.best_bound``
   * - ``PULP_CBC_CMD(...)``
     - ``COIN_CMD(...)`` (with ``pip install pulp[cbc]``)
   * - ``from pulp.apis.coin_api import COIN_CMD``
     - ``from pulp.apis.coin import COIN_CMD`` (or just ``from pulp import COIN_CMD``)
   * - ``pickle.dumps(prob)``
     - ``prob.toDict()`` / ``prob.toJson(path)``


Installation
-------------

* PuLP 4.0 requires **Python 3.12 or newer**.
* PuLP 4.0 ships a compiled extension, so it is installed as a platform wheel.
  It also depends on `orloge <https://github.com/pchtsp/orloge>`_, which is
  installed automatically and is used to read solver logs.
* **CBC is no longer bundled** and ``PULP_CBC_CMD`` has been removed. Install CBC
  with the ``cbc`` extra (or put a ``cbc`` executable on your ``PATH``) and use
  ``COIN_CMD``::

      python -m pip install pulp[cbc]

  .. code-block:: python

      # 3.x
      prob.solve(PULP_CBC_CMD(msg=False, timeLimit=60))

      # 4.0
      prob.solve(COIN_CMD(msg=False, timeLimit=60))

  ``COIN_CMD`` accepts the same arguments ``PULP_CBC_CMD`` did. ``getSolver("PULP_CBC_CMD")``
  and solver JSON files with ``"solver": "PULP_CBC_CMD"`` must be changed to ``COIN_CMD`` too.

  ``prob.solve()`` with no solver still uses CBC when it is available, and
  otherwise the first other solver it finds. Run ``listSolvers(onlyAvailable=True)``
  to see which solvers PuLP can find.


Creating variables
-------------------

In 3.x a variable was a free-standing object that joined a problem the first
time it appeared in the objective or a constraint. In 4.0 a variable is created
by the problem and belongs to it. ``LpVariable(...)`` can no longer be called
directly (it raises ``TypeError``), and ``LpVariable.dicts``, ``LpVariable.dict``
and ``LpVariable.matrix`` have been removed.

Every method takes the same arguments as its 3.x counterpart (``name``,
``indices``, ``lowBound``, ``upBound``, ``cat``) and names the variables the same
way.

.. code-block:: python

    # 3.x
    prob = LpProblem("example", LpMinimize)
    x = LpVariable("x", lowBound=0, upBound=10)
    y = LpVariable("y", cat=LpBinary)
    flows = LpVariable.dicts("flow", (warehouses, bars), lowBound=0, cat=LpInteger)
    assign = LpVariable.dict("assign", (people, tables), cat=LpBinary)
    grid = LpVariable.matrix("grid", (rows, cols), lowBound=0)

    # 4.0
    prob = LpProblem("example", LpMinimize)
    x = prob.add_variable("x", lowBound=0, upBound=10)
    y = prob.add_variable("y", cat=LpBinary)
    flows = prob.add_variable_dicts("flow", (warehouses, bars), lowBound=0, cat=LpInteger)
    assign = prob.add_variable_dict("assign", (people, tables), cat=LpBinary)
    grid = prob.add_variable_matrix("grid", (rows, cols), lowBound=0)

This means **the problem must exist before its variables**. Code that created
the variables first and the problem later needs to be reordered, and helper
functions that build variables need the problem passed in:

.. code-block:: python

    # 3.x
    def make_vars(items):
        return LpVariable.dicts("buy", items, cat=LpBinary)

    # 4.0
    def make_vars(prob, items):
        return prob.add_variable_dicts("buy", items, cat=LpBinary)

Other changes around variables:

* ``prob.addVariable(x)`` and ``prob.addVariables(xs)`` have been removed. They
  are not needed: a variable is in the problem from the moment it is created,
  even if no constraint uses it yet.
* **A variable cannot be used in another problem.** Adding an expression with a
  variable from problem ``A`` to problem ``B`` raises
  ``PulpError: Expression is bound to a different model``. If you built several
  problems from the same variables, create the variables in each problem.
* ``prob.copy()`` and ``prob.deepcopy()`` now copy the whole model, variables
  included. Use the copy's own variables, looked up by name:

  .. code-block:: python

      # 3.x
      other = prob.copy()
      other += x <= 1          # x shared by both problems

      # 4.0
      other = prob.copy()
      other_vars = other.variablesDict()
      other += other_vars["x"] <= 1

* Binary variables are stored as integer variables with bounds 0 and 1, so
  ``y.cat`` returns ``"Integer"`` for a variable created with ``cat=LpBinary``.
  Use ``y.isBinary()`` to check for binaries.
* ``LpVariable.fromDict(data)`` and ``LpVariable.fromDataclass(mps)`` now take the
  problem as their first argument: ``LpVariable.fromDict(prob, data)``.
* Column-wise modelling (``LpConstraintVar`` and ``LpVariable(..., e=...)``) has
  been removed. Build the constraints row by row instead.


Expressions and constraints
----------------------------

Operators work as before: ``2 * x + y``, ``lpSum(...)``, ``lpDot(...)``,
``x + y <= 5``, ``prob += expr, "name"`` and ``prob.addConstraint(expr, "name")``
need no changes.

What changed is building expressions and constraints through their
constructors, which now only wrap internal objects:

.. code-block:: python

    # 3.x
    e = LpAffineExpression({x: 1, y: 2}, constant=3, name="e")
    e = LpAffineExpression([(x, 1), (y, 2)])
    c = LpConstraint(e, LpConstraintLE, "cap", 10)
    prob += c

    # 4.0
    e = LpAffineExpression.from_dict({x: 1, y: 2}, constant=3, name="e")
    e = LpAffineExpression.from_list([(x, 1), (y, 2)])
    prob += e <= 10, "cap"

``LpAffineExpression`` also has ``empty()``, ``from_variable(x)`` and
``from_constant(3)``.

Reading constraints back
~~~~~~~~~~~~~~~~~~~~~~~~~

``prob.constraints`` is now a method returning the constraints as a list, in
the order they were added. Indexing it by name raises ``TypeError``, and
calling ``.items()``, ``.values()`` or ``.keys()`` on it raises ``AttributeError``.

.. code-block:: python

    # 3.x
    for name, c in prob.constraints.items():
        print(name, c.pi, c.slack)
    cap = prob.constraints["cap"]

    # 4.0
    for c in prob.constraints():
        print(c.name, c.pi, c.slack)
    cap = prob.get_constraint_by_name("cap")

``get_constraint_by_name`` returns ``None`` when there is no constraint with
that name. It is also available in PuLP 3.3.1 and later, so you can switch to it
before upgrading. If you look up many constraints by name, build a dictionary
once after the model is complete:
``constraints = {c.name: c for c in prob.constraints()}``.

Removed problem features
~~~~~~~~~~~~~~~~~~~~~~~~~

These 3.x features have no direct equivalent in 4.0:

* **Elastic constraints**: ``LpConstraint.makeElasticSubProblem``,
  ``FixedElasticSubProblem``, ``FractionElasticSubProblem`` and
  ``LpProblem.extend``. Model the penalty explicitly: add non-negative slack
  variables to the constraint and a penalty on them in the objective.
* ``LpFractionConstraint`` and ``LpElement``.
* ``LpProblem.normalisedNames``, ``unusedConstraintName``, ``startClock`` /
  ``stopClock``, ``assignStatus``.


Solving and reading the status
-------------------------------

This is the change that affects almost every script. In 3.x ``prob.solve()``
returned an integer and stored the status on the problem. In 4.0 it returns an
:py:class:`~pulp.LpSolveStats` object, and the problem no longer has
``status``, ``sol_status``, ``solutionTime``, ``solutionCpuTime`` or
``bestBound`` attributes.

.. code-block:: python

    # 3.x
    prob.solve(COIN_CMD(msg=False))
    print("Status:", LpStatus[prob.status])
    if prob.status == LpStatusOptimal:
        print(value(prob.objective), prob.solutionTime)

    # 4.0
    stats = prob.solve(COIN_CMD(msg=False))
    print("Status:", stats.status_str)
    if stats.status == LpSolveStatus.Optimal:
        print(stats.objective, stats.time)

``solver.solve(prob)`` and ``prob.resolve()`` return an ``LpSolveStats`` too, and
``prob.sequentialSolve(...)`` returns a list of them, one per objective.

Variable values, ``value(prob.objective)``, ``c.pi`` and ``c.slack`` are read the
same way as before.

The status enum
~~~~~~~~~~~~~~~~

The ``LpStatus*`` constants and the ``LpStatus`` dictionary are replaced by the
:py:class:`~pulp.constants.LpSolveStatus` enum. It is an ``IntEnum`` and keeps
the old numbers, so a comparison with a plain integer (``stats.status == 1``)
still works.

.. list-table::
   :header-rows: 1

   * - PuLP 3.x
     - PuLP 4.0
     - Value
   * - ``LpStatusNotSolved``
     - ``LpSolveStatus.NotSolved``
     - 0
   * - ``LpStatusOptimal``
     - ``LpSolveStatus.Optimal``
     - 1
   * - ``LpStatusInfeasible``
     - ``LpSolveStatus.Infeasible``
     - -1
   * - ``LpStatusUnbounded``
     - ``LpSolveStatus.Unbounded``
     - -2
   * - ``LpStatusUndefined``
     - ``LpSolveStatus.Undefined``
     - -3
   * - (new)
     - ``LpSolveStatus.TimeLimit``
     - -4
   * - (new)
     - ``LpSolveStatus.MemoryLimit``
     - -5
   * - (new)
     - ``LpSolveStatus.NodeLimit``
     - -6
   * - (new)
     - ``LpSolveStatus.GapLimit``
     - -7
   * - (new)
     - ``LpSolveStatus.IterationLimit``
     - -8
   * - (new)
     - ``LpSolveStatus.SolutionLimit``
     - -9
   * - (new)
     - ``LpSolveStatus.Interrupted``
     - -10
   * - (new)
     - ``LpSolveStatus.Stopped``
     - -11
   * - (new)
     - ``LpSolveStatus.NumericalError``
     - -12

``stats.status_str`` is the member's name, so the text changes slightly:
``"Not Solved"`` becomes ``"NotSolved"``. If you compared ``LpStatus[...]``
strings, compare the enum instead. To turn a stored integer into a name, use
``LpSolveStatus(code).name``.

"Optimal" now means optimal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In 3.x a solver that stopped at a time limit with a feasible solution usually
reported ``LpStatusOptimal`` (1), and only ``prob.sol_status`` told you the
solution was not proven optimal. In 4.0 the status says why the solver stopped
(``TimeLimit``, ``GapLimit``, ``NodeLimit``...), and whether it returned a
solution is a separate flag, ``stats.has_solution``.

So code like this, which used to accept time-limited solutions, **now treats
them as failures**:

.. code-block:: python

    # 3.x: also true for a feasible solution found before the time limit
    if prob.status == LpStatusOptimal:
        use_solution()

Decide which of the two you mean:

.. code-block:: python

    # 4.0: any feasible solution the solver returned
    if stats.has_solution:
        use_solution()

    # 4.0: only proven optimal solutions
    if stats.status == LpSolveStatus.Optimal:
        use_solution()

The ``LpSolution*`` constants (``LpSolutionOptimal``, ``LpSolutionIntegerFeasible``,
``LpSolutionNoSolutionFound``, ...) and ``LpStatusToSolution`` have been removed;
use ``has_solution`` together with ``status``:

.. list-table::
   :header-rows: 1

   * - PuLP 3.x ``prob.sol_status``
     - PuLP 4.0
   * - ``LpSolutionOptimal``
     - ``stats.has_solution and stats.status == LpSolveStatus.Optimal``
   * - ``LpSolutionIntegerFeasible``
     - ``stats.has_solution and stats.status != LpSolveStatus.Optimal``
   * - ``LpSolutionNoSolutionFound``, ``LpSolutionInfeasible``, ``LpSolutionUnbounded``
     - ``not stats.has_solution`` (and ``stats.status`` for the reason)

What else is in ``LpSolveStats``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Besides ``status`` and ``has_solution``, the object has:

* ``solver``, ``time``, ``cpu_time``, ``objective``, ``best_bound``, ``gap_abs``,
  ``gap_rel``, ``num_variables``, ``num_constraints``, ``is_mip``,
  ``solver_options``.
* For solvers whose log PuLP can read (``COIN_CMD``, ``CPLEX_CMD``, ``CPLEX_PY``,
  ``GUROBI``, ``GUROBI_CMD``, ``CPSAT``): ``solver_version``, ``nodes``,
  ``root_time``, ``presolve``, ``matrix``, ``cut_info``, ``first_solution`` and the
  full parsed log in ``logs``. These are ``None`` for the other solvers.

``print(stats)`` shows a short summary, and ``stats.toDict()`` /
``stats.toJson(path)`` export it.


Saving and loading problems
----------------------------

* ``LpProblem`` objects **cannot be pickled** any more (``pickle.dumps(prob)``
  raises ``TypeError``), and neither can objects that hold one, such as
  ``multiprocessing`` arguments. Pass the model as a dictionary or JSON and
  rebuild it on the other side:

  .. code-block:: python

      data = prob.toDict()                  # or prob.toJson("model.json")
      variables, prob = LpProblem.fromDict(data)  # or LpProblem.fromJson("model.json")

  ``variables`` is a dictionary from variable name to the new problem's
  variables.
* JSON files written by 3.x load in 4.0. Files written by 4.0 no longer contain
  ``status`` and ``sol_status``, so PuLP 3.x cannot read them.
* ``LpProblem.to_dict``, ``from_dict``, ``to_json`` and ``from_json`` still work
  but are deprecated; use ``toDict``, ``fromDict``, ``toJson`` and ``fromJson``.


Solver modules and custom solvers
----------------------------------

Most code imports solvers from ``pulp`` directly and needs no change. If you
import from the solver modules, drop the ``_api`` suffix:

.. code-block:: python

    # 3.x
    from pulp.apis.coin_api import COIN_CMD
    from pulp.apis.gurobi_api import GUROBI

    # 4.0
    from pulp.apis.coin import COIN_CMD
    from pulp.apis.gurobi import GUROBI

If you wrote your own solver class by subclassing ``LpSolver`` or
``LpSolver_CMD``:

* ``actualSolve(lp)`` must return an ``LpSolveStats``. Build it with
  ``self.buildStats(lp, status, has_solution, start=start)``, where ``start`` is
  ``clocks()`` (from ``pulp.apis.core``) taken at the beginning of
  ``actualSolve``. Do not call ``lp.assignStatus`` (removed).
* The API solvers' ``findSolutionValues(lp)`` returns a
  ``(status, has_solution)`` tuple instead of a status.
* Register the class with ``pulp.apis.addSolver(MySolver)`` so that
  ``getSolver("MY_SOLVER")`` and ``listSolvers()`` can find it.

See :doc:`../develop/add_solver` for a complete example.


Removed top-level names
------------------------

These names can no longer be imported from ``pulp``:

* ``PULP_CBC_CMD``: use ``COIN_CMD``.
* ``LpStatus``, ``LpStatusNotSolved``, ``LpStatusOptimal``, ``LpStatusInfeasible``,
  ``LpStatusUnbounded``, ``LpStatusUndefined``: use ``LpSolveStatus``.
* ``LpSolution``, ``LpSolutionNoSolutionFound``, ``LpSolutionOptimal``,
  ``LpSolutionIntegerFeasible``, ``LpSolutionInfeasible``, ``LpSolutionUnbounded``,
  ``LpStatusToSolution``: use ``LpSolveStats.has_solution``.
* ``LpConstraintVar``, ``LpElement``, ``LpFractionConstraint``,
  ``FixedElasticSubProblem``, ``FractionElasticSubProblem``.
* ``set_v4_migration_warnings``, ``pulpTestAll``, ``configSolvers``, ``clock``,
  ``VERSION``: use ``pulp.__version__`` for the version.


A complete example
-------------------

.. code-block:: python

    # PuLP 3.x
    from pulp import *

    prob = LpProblem("production", LpMaximize)
    products = ["A", "B"]
    make = LpVariable.dicts("make", products, lowBound=0, cat=LpInteger)
    prob += 3 * make["A"] + 5 * make["B"], "profit"
    prob += 2 * make["A"] + 4 * make["B"] <= 40, "machine_hours"
    prob += make["A"] + make["B"] <= 15, "labour"

    prob.solve(PULP_CBC_CMD(msg=False, timeLimit=30))
    print(LpStatus[prob.status], value(prob.objective))
    if prob.status == LpStatusOptimal:
        print({p: make[p].varValue for p in products})
        print(prob.constraints["labour"].slack)

.. code-block:: python

    # PuLP 4.0
    from pulp import *

    prob = LpProblem("production", LpMaximize)
    products = ["A", "B"]
    make = prob.add_variable_dicts("make", products, lowBound=0, cat=LpInteger)
    prob += 3 * make["A"] + 5 * make["B"], "profit"
    prob += 2 * make["A"] + 4 * make["B"] <= 40, "machine_hours"
    prob += make["A"] + make["B"] <= 15, "labour"

    stats = prob.solve(COIN_CMD(msg=False, timeLimit=30))
    print(stats.status_str, stats.objective)
    if stats.has_solution:
        print({p: make[p].varValue for p in products})
        print(prob.get_constraint_by_name("labour").slack)
