*SENSE:Maximize
NAME          binary
ROWS
 N  OBJ
 E  _C1
 L  _C2
COLUMNS
    dummy     OBJ       -1.000000000000e0
    MARK      'MARKER'                 'INTORG'
    c1        _C1        1.000000000000e0
    c1        _C2        1.000000000000e0
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    c2        _C1        1.000000000000e0
    MARK      'MARKER'                 'INTEND'
RHS
    RHS       _C1        2.000000000000e0
    RHS       _C2        0.000000000000e0
BOUNDS
 FR BND       dummy   
 BV BND       c1      
 BV BND       c2      
ENDATA
