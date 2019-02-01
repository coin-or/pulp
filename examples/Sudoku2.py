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
prob += choices[5][1][1] == 1
prob += choices[6][2][1] == 1
prob += choices[8][4][1] == 1
prob += choices[4][5][1] == 1
prob += choices[7][6][1] == 1
prob += choices[3][1][2] == 1
prob += choices[9][3][2] == 1
prob += choices[6][7][2] == 1
prob += choices[8][3][3] == 1
prob += choices[1][2][4] == 1
prob += choices[8][5][4] == 1
prob += choices[4][8][4] == 1
prob += choices[7][1][5] == 1
prob += choices[9][2][5] == 1
prob += choices[6][4][5] == 1
prob += choices[2][6][5] == 1
prob += choices[1][8][5] == 1
prob += choices[8][9][5] == 1
prob += choices[5][2][6] == 1
prob += choices[3][5][6] == 1
prob += choices[9][8][6] == 1
prob += choices[2][7][7] == 1
prob += choices[6][3][8] == 1
prob += choices[8][7][8] == 1
prob += choices[7][9][8] == 1
prob += choices[3][4][9] == 1
# Since the previous Sudoku contains only one unique solution, we remove some constraints to contain a Sudoku
# with multiple solutions
# prob += choices[1][5][9] == 1
# prob += choices[6][6][9] == 1
# prob += choices[5][8][9] == 1

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
            if r == 1 or r == 4 or r == 7:
                sudokuout.write("+-------+-------+-------+\n")
            for c in COLS:
                for v in VALS:
                    if value(choices[v][r][c]) == 1:
                        if c == 1 or c == 4 or c == 7:
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
