orloge: OR logs parser
===========================================

orloge is a log parser for several MIP solvers that standardizes the contents into a python dictionary with most of the useful information provided. It supports GUROBI, CPLEX, CBC and CP-SAT. Information reported includes: best objective, best bound, cuts, gap, nodes, status, time, etc. It also provides the whole progress log of the solver, as a list with one dataclass per row.

site: https://github.com/pchtsp/orloge/

orloge is a dependency of PuLP. Solving with ``prob.solve(solver, stats=True)`` has the solver write a log, parses it with orloge, and keeps the result as-is on the returned :py:class:`~pulp.LpSolveStats`, in its ``logs`` attribute. Individual pieces of it are exposed as read-only properties, e.g. ``solver_version``, ``nodes`` and ``matrix``, which fall back to ``None`` when there is no log or orloge could not parse it.

orloge can also be used directly, with GUROBI for example::

    import orloge as ol
    ol.get_info_solver('tests/data/gurobi700-app1-2.out', 'GUROBI')

Creates the following output::

    {'best_bound': -41.0,
     'best_solution': -41.0,
     'cut_info': {'best_bound': -167.97894,
                  'best_solution': -41.0,
                  'cuts': {'Clique': 1,
                           'Gomory': 16,
                           'Implied bound': 23,
                           'MIR': 22},
                  'time': 21.0},
     'first_relaxed': -178.94318,
     'first_solution': {'Node': 0, 'NodesLeft': 0, 'BestInteger': -41.0, 'CutsBestBound': -178.94318},
     'gap': 0,
     'matrix': {'constraints': 53467, 'nonzeros': 199175, 'variables': 26871},
     'matrix_post': {'constraints': 35616, 'nonzeros': 149085, 'variables': 22010},
     'nodes': 526.0,
     'presolve': {'cols': 4861, 'rows': 17851, 'time': 3.4},
     'progress': [GUROBIProgressRow(Node=0, NodesLeft=0, BestInteger=-41.0, CutsBestBound=-178.94318, Time=4.0,
                                     Objective=-178.94318, Depth=0, IInf=282, Gap=336.0, ItpNode=None),
                  GUROBIProgressRow(Node=0, NodesLeft=0, BestInteger=-41.0, CutsBestBound=-171.91701, Time=15.0,
                                     Objective=-171.91701, Depth=0, IInf=268, Gap=319.0, ItpNode=None),
                  ...
                  # 26 rows total
                  ],
     'rootTime': 0.7,
     'sol_code': 1,
     'solver': 'GUROBI',
     'status': 'Optimal solution found',
     'status_code': 1,
     'time': 46.67,
     'version': '7.0.0'}
