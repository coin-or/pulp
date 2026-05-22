*SENSE:Minimize
NAME          test_importMPS_integer
ROWS
 N  obj
 L  c1
 G  c2
 E  c3
COLUMNS
    x         c1         1.000000000000e0
    x         c2         1.000000000000e0
    x         obj        1.100000000000e0
    y         c1         1.000000000000e0
    y         c3        -1.000000000000e0
    y         obj        4.100000000000e0
    MARK      'MARKER'                 'INTORG'
    z         c2         1.000000000000e0
    z         c3         1.000000000000e0
    z         obj        9.100000000000e0
    MARK      'MARKER'                 'INTEND'
RHS
    RHS       c1         5.000000000000e0
    RHS       c2         1.000000000000e1
    RHS       c3         7.500000000000e0
BOUNDS
 UP BND       x          4.000000000000e0
 LO BND       y         -1.000000000000e0
 UP BND       y          1.000000000000e0
 LO BND       z          0.000000000000e0
ENDATA
