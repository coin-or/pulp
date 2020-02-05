import tsplib95 as tsplib95

import pulp


def tsp_solve_exact(problem):
    print(f"Solving Exactly {problem.name}")
    cities, edges, edge_dist_list, matrix, is_symmetric = get_problem_data(problem)
    arcs = [(i, j) for i in cities for j in cities]
    model = pulp.LpProblem(f"TSP_{problem.name}", sense=pulp.LpMinimize)
    x = {arc: pulp.LpVariable(f"X_{tuple(arc)}".replace(" ", ""), lowBound=0, upBound=1, cat=pulp.LpBinary) for
         arc in arcs}
    y = {city: pulp.LpVariable(f"Y_{city}", lowBound=0, cat=pulp.LpContinuous) for city in cities}
    model.setObjective(
        pulp.lpSum(matrix[i][j] * x[(i, j)] for i, j in arcs if i != j)
    )
    [model.addConstraint(
        pulp.LpConstraint(
            pulp.lpSum(x[(i, j)] for i in cities if i != j), sense=pulp.LpConstraintEQ, name=f"C1{j}", rhs=1)
    ) for j in cities]
    [model.addConstraint(
        pulp.LpConstraint(
            pulp.lpSum(x[(i, j)] for j in cities if i != j), sense=pulp.LpConstraintEQ, name=f"C2{i}", rhs=1)
    ) for i in cities]
    for i in cities[1:]:
        for j in cities[1:]:
            if i != j:
                model.addConstraint(
                    pulp.LpConstraint(pulp.lpSum(y[i] - y[j] + len(arcs) * x[(i, j)]),
                                      sense=pulp.LpConstraintLE,
                                      name=f"C3{i}_{j}", rhs=len(arcs) - 1)
                )
    # model.writeLP(f"./lp_files/{problem.name}.lp")
    solver = _get_best_solver()
    model.solve(solver(msg=True, maxSeconds=60))
    visited = [arc for arc, attributes in x.items() if attributes.varValue and attributes.varValue > 0.95]
    # tour = make_tour_from_edges(visited, cities)
    # dist = wrap_up_tsp(problem, tour, f"Exact ({solver.__name__})", "exact")
    # return tour, dist


def get_problem_data(problem):
    cities = list(problem.get_nodes())
    edges = list(problem.get_edges())
    edge_dist_list = {edge: problem.wfunc(*edge) for edge in edges}
    matrix = {i: {j: problem.wfunc(i, j) for j in cities if i != j} for i in cities}
    return cities, edges, edge_dist_list, matrix, problem.is_symmetric()


def _get_best_solver():
    solvers = [
        # pulp.GUROBI_CMD,

        # pulp.CPLEX_DLL,
        # pulp.CPLEX_CMD,
        # pulp.CPLEX_PY,

        pulp.GUROBI,


        pulp.COIN_CMD,
        pulp.PULP_CBC_CMD,
        pulp.COINMP_DLL,

        # pulp.GLPK_CMD,
        # pulp.XPRESS,
        # pulp.PYGLPK,
        # pulp.YAPOSIB,
        pulp.PULP_CHOCO_CMD
    ]
    for solver in solvers:
        if solver().available():
            print(f"Solver {solver} is available")
            return solver


if __name__ == '__main__':
    path = "D:/phd_projects/project_mercury/data/tsp/tsp/att48.tsp"
    problem = tsplib95.load_problem(path)
    _get_best_solver()
    tsp_solve_exact(problem)
