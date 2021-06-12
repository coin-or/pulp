PuLP_LPARRAY: PuLP x NumPy, a match made in heaven
======================================================

It's just PuLP under the hood: LpVariable, LpAffineExpression and LpConstraint do the heavy lifting.
All the power of numpy for your linear variable sets: broadcasting, reshaping and indexing tricks galore. Never see a for or indexing variable ever again.
Special support functions that allow efficient linearization of useful operations like min/max, abs, clip-to-binary, boolean operators, and more. Wide support for the axis keyword.

site: https://github.com/qdbp/pulp-lparray

example:

Let's solve an unconstrained SuperSudoku puzzle. A SuperSudoku is a Sudoku with the additional requirement that all digits having box coordinates (x, y) be distinct for all (x, y)::

    from lparray import lparray

    # name      R, C, r, c, n   lb ub type
    X = lparray.create_anon("Board", (3, 3, 3, 3, 9), 0, 1, pp.LpBinary)
    prob = pp.LpProblem("SuperSudoku", pp.LpMinimize)
    (X.sum(axis=-1) == 1).constrain(prob, "OneDigitPerCell")
    (X.sum(axis=(1, 3)) == 1).constrain(prob, "MaxOnePerRow")
    (X.sum(axis=(0, 2)) == 1).constrain(prob, "MaxOnePerCol")
    (X.sum(axis=(2, 3)) == 1).constrain(prob, "MaxOnePerBox")
    (X.sum(axis=(0, 1)) == 1).constrain(prob, "MaxOnePerXY")
    prob.solve()
    board = X.values.argmax(axis=-1)
    print(board)
