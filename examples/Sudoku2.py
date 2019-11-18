"""
The Looping Sudoku Problem Formulation for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitchell
edited by Dr Nathan Sudermann-Merx
"""

# Import PuLP modeler functions
from pulp import *

# All rows, columns and values within a Sudoku take values from 1 to 9
VALS = ROWS = COLS = range(1, 10)

# The boxes list is created, with the row and column index of each square in each box
Boxes = [
    [(3 * i + k + 1, 3 * j + l + 1) for k in range(3) for l in range(3)]
    for i in range(3) for j in range(3)
]

# The prob variable is created to contain the problem data
prob = LpProblem("Sudoku Problem")

# The decision variables are created
choices = LpVariable.dicts("Choice", (VALS, ROWS, COLS), cat='Binary')

# We do not define an objective function since none is needed

# A constraint ensuring that only one value can be in each square is created
for r in ROWS:
    for c in COLS:
        prob += lpSum([choices[v][r][c] for v in VALS]) == 1

# The row, column and box constraints are added for each value
for v in VALS:
    for r in ROWS:
        prob += lpSum([choices[v][r][c] for c in COLS]) == 1

    for c in COLS:
        prob += lpSum([choices[v][r][c] for r in ROWS]) == 1

    for b in Boxes:
        prob += lpSum([choices[v][r][c] for (r, c) in b]) == 1

# The starting numbers are entered as constraints
input_data = [
    (5, 1, 1),
    (6, 2, 1),
    (8, 4, 1),
    (4, 5, 1),
    (7, 6, 1),
    (3, 1, 2),
    (9, 3, 2),
    (6, 7, 2),
    (8, 3, 3),
    (1, 2, 4),
    (8, 5, 4),
    (4, 8, 4),
    (7, 1, 5),
    (9, 2, 5),
    (6, 4, 5),
    (2, 6, 5),
    (1, 8, 5),
    (8, 9, 5),
    (5, 2, 6),
    (3, 5, 6),
    (9, 8, 6),
    (2, 7, 7),
    (6, 3, 8),
    (8, 7, 8),
    (7, 9, 8),
    (3, 4, 9),
    # Since the previous Sudoku contains only one unique solution, we remove some numers from the board to obtain a
    # Sudoku with multiple solutions
#    (1, 5, 9),
#    (6, 6, 9),
#    (5, 8, 9)
]

for (v, r, c) in input_data:
    prob += choices[v][r][c] == 1

# The problem data is written to an .lp file
prob.writeLP("Sudoku.lp")

# A file called sudokuout.txt is created/overwritten for writing to
sudokuout = open('sudokuout.txt','w')

while True:
    prob.solve()
    # The status of the solution is printed to the screen
    print("Status:", LpStatus[prob.status])
    # The solution is printed if it was deemed "optimal" i.e met the constraints
    if LpStatus[prob.status] == "Optimal":
        # The solution is written to the sudokuout.txt file
        for r in ROWS:
            if r in [1, 4, 7]:
                sudokuout.write("+-------+-------+-------+\n")
            for c in COLS:
                for v in VALS:
                    if value(choices[v][r][c]) == 1:
                        if c in [1, 4, 7]:
                            sudokuout.write("| ")
                        sudokuout.write(str(v) + " ")
                        if c == 9:
                            sudokuout.write("|\n")
        sudokuout.write("+-------+-------+-------+\n\n")
        # The constraint is added that the same solution cannot be returned again
        prob += lpSum([choices[v][r][c] for v in VALS for r in ROWS for c in COLS
                       if value(choices[v][r][c]) == 1]) <= 80
    # If a new optimal solution cannot be found, we end the program
    else:
        break
sudokuout.close()

# The location of the solutions is give to the user
print("Solutions Written to sudokuout.txt")
