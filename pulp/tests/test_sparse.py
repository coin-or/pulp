from pulp.sparse import Matrix


def test_sparse():
    rows = list(range(10))
    cols = list(range(50, 60))
    mat = Matrix(rows, cols)
    mat.add(1, 52, "item")
    mat.add(2, 54, "stuff")
    assert mat.col_based_arrays() == (
        2,
        [0, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2],
        [0, 0, 1, 0, 1, 0, 0, 0, 0, 0],
        [1, 2],
        ["item", "stuff"],
    )
