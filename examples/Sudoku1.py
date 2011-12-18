"""
The Sudoku Problem Formulation for the PuLP Modeller

Authors: Antony Phillips, Dr Stuart Mitcehll
"""

# Import PuLP modeler functions
from pulp import *

# A list of strings from "1" to "9" is created
Sequence = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

# The Vals, Rows and Cols sequences all follow this form
Vals = Sequence
Rows = Sequence
Cols = Sequence

# The boxes list is created, with the row and column index of each square in each box
Boxes =[]
for i in range(3):
    for j in range(3):
        Boxes += [[(Rows[3*i+k],Cols[3*j+l]) for k in range(3) for l in range(3)]]

# The prob variable is created to contain the problem data        
prob = LpProblem("Sudoku Problem",LpMinimize)

# The problem variables are created
choices = LpVariable.dicts("Choice",(Vals,Rows,Cols),0,1,LpInteger)

# The arbitrary objective function is added
prob += 0, "Arbitrary Objective Function"

# A constraint ensuring that only one value can be in each square is created
for r in Rows:
    for c in Cols:
        prob += lpSum([choices[v][r][c] for v in Vals]) == 1, ""

# The row, column and box constraints are added for each value
for v in Vals:
    for r in Rows:
        prob += lpSum([choices[v][r][c] for c in Cols]) == 1,""
        
    for c in Cols:
        prob += lpSum([choices[v][r][c] for r in Rows]) == 1,""

    for b in Boxes:
        prob += lpSum([choices[v][r][c] for (r,c) in b]) == 1,""
                        
# The starting numbers are entered as constraints                
prob += choices["5"]["1"]["1"] == 1,""
prob += choices["6"]["2"]["1"] == 1,""
prob += choices["8"]["4"]["1"] == 1,""
prob += choices["4"]["5"]["1"] == 1,""
prob += choices["7"]["6"]["1"] == 1,""
prob += choices["3"]["1"]["2"] == 1,""
prob += choices["9"]["3"]["2"] == 1,""
prob += choices["6"]["7"]["2"] == 1,""
prob += choices["8"]["3"]["3"] == 1,""
prob += choices["1"]["2"]["4"] == 1,""
prob += choices["8"]["5"]["4"] == 1,""
prob += choices["4"]["8"]["4"] == 1,""
prob += choices["7"]["1"]["5"] == 1,""
prob += choices["9"]["2"]["5"] == 1,""
prob += choices["6"]["4"]["5"] == 1,""
prob += choices["2"]["6"]["5"] == 1,""
prob += choices["1"]["8"]["5"] == 1,""
prob += choices["8"]["9"]["5"] == 1,""
prob += choices["5"]["2"]["6"] == 1,""
prob += choices["3"]["5"]["6"] == 1,""
prob += choices["9"]["8"]["6"] == 1,""
prob += choices["2"]["7"]["7"] == 1,""
prob += choices["6"]["3"]["8"] == 1,""
prob += choices["8"]["7"]["8"] == 1,""
prob += choices["7"]["9"]["8"] == 1,""
prob += choices["3"]["4"]["9"] == 1,""
prob += choices["1"]["5"]["9"] == 1,""
prob += choices["6"]["6"]["9"] == 1,""
prob += choices["5"]["8"]["9"] == 1,""

# The problem data is written to an .lp file
prob.writeLP("Sudoku.lp")

# The problem is solved using PuLP's choice of Solver
prob.solve()

# The status of the solution is printed to the screen
print "Status:", LpStatus[prob.status]

# A file called sudokuout.txt is created/overwritten for writing to
sudokuout = open('sudokuout.txt','w')

# The solution is written to the sudokuout.txt file 
for r in Rows:
    if r == "1" or r == "4" or r == "7":
                    sudokuout.write("+-------+-------+-------+\n")
    for c in Cols:
        for v in Vals:
            if value(choices[v][r][c])==1:
                               
                if c == "1" or c == "4" or c =="7":
                    sudokuout.write("| ")
                    
                sudokuout.write(v + " ")
                
                if c == "9":
                    sudokuout.write("|\n")
sudokuout.write("+-------+-------+-------+")                    
sudokuout.close()

# The location of the solution is give to the user
print "Solution Written to sudokuout.txt"
