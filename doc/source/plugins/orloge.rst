orloge: OR logs parser
===========================================

orloge is a log parser for several MIP solvers that standardizes the contents into a python dictionary with most of the useful information provided. It supports GUROBI, CPLEX and CBC. Information reported includes: best objective, best bound, cuts, gap, nodes, status, time, etc. It also provides a pandas dataframe with the whole progress log of the solver.

site: https://github.com/pchtsp/orloge/

example with GUROBI::

    import orloge as ol
    ol.get_info_log_solver('tests/data/gurobi700-app1-2.out', 'GUROBI')

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
     'first_solution': -41.0,
     'gap': 0.0,
     'matrix': {'constraints': 53467, 'nonzeros': 199175, 'variables': 26871},
     'matrix_post': {'constraints': 35616, 'nonzeros': 149085, 'variables': 22010},
     'nodes': 526.0,
     'presolve': {'cols': 4861, 'rows': 17851, 'time': 3.4},
     'progress':    
     Node NodesLeft   Objective Depth ...  CutsBestBound    Gap ItpNode Time
    0     0         0  -178.94318     0 ...     -178.94318   336%    None   4s
    1     0         0  -171.91701     0 ...     -171.91701   319%    None  15s
    2     0         0  -170.97660     0 ...     -170.97660   317%    None  15s
    [26 rows x 10 columns],
     'rootTime': 0.7,
     'sol_code': 1,
     'solver': 'GUROBI',
     'status': 'Optimal solution found',
     'status_code': 1,
     'time': 46.67,
     'version': '7.0.0'}


