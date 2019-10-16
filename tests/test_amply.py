from pulp.amply import Amply, AmplyError
from io import StringIO

from nose.tools import assert_raises

def test_data():
    result = Amply("param T := 4;")['T']
    assert result == 4
    result = Amply("param T := -4;")['T']
    assert result == -4
    result = Amply("param T := 0.04;")['T']
    assert result == 0.04
    result = Amply("param T := -0.04;")['T']
    assert result == -0.04

def test_set():
    result = Amply("set month := Jan Feb Mar Apr;")['month'] 
    assert result == ['Jan', 'Feb', 'Mar', 'Apr']

    result = Amply("set month Jan Feb Mar Apr;")['month'] 
    assert result == ['Jan', 'Feb', 'Mar', 'Apr']
    assert [i for i in result] == ['Jan', 'Feb', 'Mar', 'Apr']
    assert result != []

    assert 'Jan' in result
    assert 'Foo' not in result
    assert len(result) == 4

def test_param():
    result = Amply("param T := 4;")['T']
    assert result != [4]
    result = Amply("param T{foo}; param T := 1 2;")['T']
    assert not (result == 2)
    assert (result != 2)

def test_attr_access():
    result = Amply("param T:= 4;").T
    assert result == 4

def test_from_file():
    try:
        s = StringIO("param T:= 4;")
    except TypeError:
        s = StringIO(u"param T:= 4;")
    assert Amply.from_file(s).T == 4

def test_load_string():
    a = Amply("param T:= 4; param X{foo};")
    a.load_string("param S := 6; param X := 1 2;")
    assert a.T == 4
    assert a.S == 6
    assert a.X[1] == 2

def test_load_file():
    a = Amply("param T:= 4; param X{foo};")
    try:
        s = StringIO("param S := 6; param X := 1 2;")
    except TypeError:
        s = StringIO(u"param S := 6; param X := 1 2;")
    a.load_file(s)
    assert a.T == 4
    assert a.S == 6
    assert a.X[1] == 2

def test_empty_init():
    a = Amply()
    a.load_string("param T := 4;")
    assert a.T == 4

def test_set_dimen2():
    result = Amply(
        """
        set twotups dimen 2;
        set twotups := (1, 2) (2, 3) (4, 2) (3, 1);
        """
    )['twotups']
    assert result == [(1, 2), (2, 3), (4, 2), (3, 1)]

def test_set_dimen_error():
    a = """
        set dim1 dimen 1;
        set dim1 := (1, 2) (2, 3) (3, 2);
        """
    assert_raises(AmplyError, lambda: Amply(a))

def test_set_dimen2_noparen():
    result = Amply(
        """
        set twotups dimen 2;
        set twotups := 1 2 2 3 4 2 3 1;
        """
    )['twotups']
    assert result == [(1, 2), (2, 3), (4, 2), (3, 1)]

def test_set_subscript():
    result = Amply(
        """
        set days{months};
        set days[Jan] := 1 2 3 4;
        set days[Feb] := 5 6 7 8;
        """
    )['days']
    j = result['Jan']
    assert j == [1, 2, 3, 4]
    f = result['Feb']
    assert f == [5, 6, 7, 8]

def test_set_subscript2():
    result = Amply(
        """
        set days{months, days};
        set days[Jan, 3] := 1 2 3 4;
        set days[Feb, 'Ham '] := 5 6 7 8;
        """
    )['days']
    j = result['Jan'][3]
    assert j == [1, 2, 3, 4]
    f = result['Feb']['Ham ']
    assert f == [5, 6, 7, 8]

def test_set_subscript2_tuples():
    result = Amply(
        """
        set days{months, days};
        set days[Jan, 3] := 1 2 3 4;
        set days[Feb, 'Ham '] := 5 6 7 8;
        """
    )['days']
    j = result['Jan', 3]
    assert j == [1, 2, 3, 4]
    f = result['Feb', 'Ham ']
    assert f == [5, 6, 7, 8]

def test_set_matrix():
    result = Amply(
        """
        set A : 1 2 3 :=
            1   + - -
            2   + + -
            3   - + -
        ;
        """
    )
    a = result.A
    assert a == [(1, 1), (2, 1), (2, 2), (3, 2)]

def test_set_matrix_tr():
    result = Amply(
        """
        set A (tr) : 1 2 3 :=
                 1   + - -
                 2   + + -
                 3   - + -
        ;
        """
    )
    a = result.A
    assert a == [(1, 1), (1, 2), (2, 2), (2, 3)]

def test_set_splice():
    result = Amply(
        """
        set A dimen 3;
        set A := (1, 2, 3), (1, 1, *) 2 4 (3, *, *) 1 1;
        """
    )
    a = result.A
    assert a == [(1, 2, 3), (1, 1, 2), (1, 1, 4), (3, 1, 1)]

def test_set_splice_matrix():
    result = Amply(
        """
        set A dimen 3;
        set A (1, *, *) : 1 2 3 :=
                    1     + - -
                    2     + - +
                    3     - - -
              (2, *, *) : 1 2 3 :=
                    1     + - +
                    2     - + -
                    3     - - +
        ;
        """
    )
    a = result.A
    assert a == [(1,1,1),(1,2,1),(1,2,3),(2,1,1),(2,1,3),(2,2,2),
                 (2,3,3)]


def test_simple_params():
    result = Amply("param T := 4;")['T'] 
    assert result == 4


def test_sub1_params():
    result = Amply(
        """
        param foo {s};
        param foo := 1 Jan 2 Feb 3 Mar;
        """
    )
    j = result['foo'][1]
    assert j == 'Jan'
    f = result['foo'][2] 
    assert f == 'Feb'

def test_sub1_param_error():
    a = """
        param foo{s};
        param foo := 1 Jan 2 Feb 3;
        """
    assert_raises(AmplyError, lambda :Amply(a))

def test_param_default():
    result = Amply(
        """
        param foo {s} default 3;
        param foo := Jan 1 Feb 2 Mar 3;
        """
    )
    j = result['foo']['Jan']
    assert j == 1
    m = result['foo']['Mar']
    assert m == 3
    d = result['foo']['FOO']
    assert d == 3

def test_param_undefined():
    result = Amply(
        """
        param foo {s} ;
        param foo := Jan 1 Feb 2 Mar 3;
        """
    )
    j = result['foo']['Jan']
    assert j == 1
    assert_raises(KeyError, lambda : result['foo']['Apr'])

def test_sub2_params():
    result = Amply(
        """
        param foo {s, t};
        param foo := 1 2 Hi 99 3 4;
        """
    )
    h = result['foo'][1][2]
    assert h == 'Hi'
    f = result['foo'][99][3]
    assert f == 4

def test_2d_param():
    result = Amply(
        """
        param demand {item, location};
        param demand
            :   FRA DET LAN :=
        spoons  200 100 30  
        plates  30  120 90
        cups    666 13  29 ;
        """
    )['demand']

    s = result['spoons']
    assert s == { 'FRA': 200, 'DET': 100, 'LAN': 30 }
    assert result['plates'] == { 'FRA': 30, 'DET': 120, 'LAN': 90 }
    assert result['cups'] == { 'FRA': 666, 'DET': 13, 'LAN': 29 }

def test_2d_numeric_param():
    result = Amply(
        """
        param square {x, y};
        param square : 1 2 :=
            4       4   8
            3       3   6
        ;
        """
    )['square']
    f = result[4, 1]
    assert f == 4
    assert result[4, 2] == 8
    assert result[3, 1] == 3
    assert result[3, 2] == 6

def test_2d_param_defaults():
    result = Amply(
        """
        param demand {item, location};
        param demand default 42
            :   FRA DET LAN :=
        spoons  200 . 30  
        plates  30  120 .
        cups    . .  29 ;
        """
    )['demand']

    s = result['spoons']
    assert s == { 'FRA': 200, 'DET': 42, 'LAN': 30 }
    assert result['plates'] == { 'FRA': 30, 'DET': 120, 'LAN': 42 }
    assert result['cups'] == { 'FRA': 42, 'DET': 42, 'LAN': 29 }

def test_2tables():
    result = Amply(
        """
        param demand {item, location};
        param demand default 42
            :   FRA DET LAN :=
        spoons  200 . 30  
        plates  30  120 .
        cups    . .  29 
        ;

        param square {foo, foo};
        param square
            :   A   B :=
        A       1   6
        B       6   36
        ;
        """
    )
    demand = result['demand']
    assert demand['spoons'] == {'FRA': 200, 'DET': 42, 'LAN': 30 }
    assert demand['plates'] == { 'FRA': 30, 'DET': 120, 'LAN': 42 }
    assert demand['cups'] == { 'FRA': 42, 'DET': 42, 'LAN': 29 }

    square = result['square']
    assert square['A'] == {'A': 1, 'B': 6}
    assert square['B'] == {'A': 6, 'B': 36}


def test_2d_param_transpose():
    result = Amply(
        """
        param demand {location, item};
        param demand default 42 (tr)
            :   FRA DET LAN :=
        spoons  200 . 30  
        plates  30  120 .
        cups    . .  29 ;
        """
    )['demand']

    f = result['FRA']
    assert f == { 'spoons': 200, 'plates': 30, 'cups': 42 }
    assert result['DET'] == { 'spoons': 42, 'plates': 120, 'cups': 42 }
    assert result['LAN'] == { 'spoons': 30, 'plates': 42, 'cups': 29 }

def test_2d_slice1():
    result = Amply(
        """
        param demand {location, item};
        param demand :=
            [Jan, *] Foo 1 Bar 2;
        """
    )['demand']
    f = result['Jan']['Foo']
    assert f == 1
    assert result['Jan']['Bar'] == 2

def test_3d_slice2():
    result = Amply(
        """
        param trans_cost{src, dest, product};
        param trans_cost :=
            [*,*,bands]: FRA DET LAN :=
                GARY     30  10  8
                CLEV     22  7   10
            [*,*,coils]: FRA DET LAN :=
                GARY     39  14  11
                CLEV     27  9   12
            [*,*,plate]: FRA DET LAN :=
                GARY     41  15  12
                CLEV     29  9   13
        ;
        """
    )['trans_cost']

    f = result['GARY']['FRA']['bands']
    assert f == 30
    assert result['GARY']['DET']['plate'] == 15
    assert result['CLEV']['LAN']['coils'] == 12

def test_3d_slice2b():
    result = Amply(
        """
        param trans_cost{src, product, dest};
        param trans_cost :=
            [*,bands,*]: FRA DET LAN :=
                GARY     30  10  8
                CLEV     22  7   10
            [*,coils,*]: FRA DET LAN :=
                GARY     39  14  11
                CLEV     27  9   12
            [*,plate,*]: FRA DET LAN :=
                GARY     41  15  12
                CLEV     29  9   13
        ;
        """
    )['trans_cost']

    f = result['GARY']['bands']['FRA']
    assert f == 30
    assert result['GARY']['plate']['DET'] == 15
    assert result['CLEV']['coils']['LAN'] == 12

def test_single_tabbing_data():
    result = Amply(
        """
        set elem;
        param init_stock{elem};
        param cost{elem};
        param value{elem};
        param : init_stock  cost    value :=
        iron    7           25      1
        nickel  35          3       2
        ;
        """
    )
    s = result['init_stock']
    assert s == {'iron': 7, 'nickel': 35}
    assert result['cost'] == {'iron': 25, 'nickel': 3}
    assert result['value'] == {'iron': 1, 'nickel': 2}

def test_single_tabbing_data_with_set():
    result = Amply(
        """
        set elem;
        param init_stock{elem};
        param cost{elem};
        param value{elem};
        param : elem : init_stock  cost    value :=
        iron    7           25      1
        nickel  35          3       2
        ;
        """
    )
    s = result['init_stock']
    assert s == {'iron': 7, 'nickel': 35}
    assert result['cost'] == {'iron': 25, 'nickel': 3}
    assert result['value'] == {'iron': 1, 'nickel': 2}

def test_set2_tabbing():
    result = Amply(
        """
        set elem dimen 2;
        set elem := 0 0 1 1 2 2;
        param cost{elem};
        param value{elem};
        param : cost value :=
        0 0     7   25
        1 1     35  3
        ;
        """
    )

    assert result['elem'] == [(0,0),(1,1),(2,2)]

def test_undefined_tabbing_param():
    assert_raises(AmplyError, lambda: Amply(
        """
        param cost{elem};
        param : cost value :=
        0       1   2
        3       4   5
        ;
        """
    ))

def test_2dset_simpleparam():
    result = Amply(
        """
        set elem dimen 2;
        param foo{elem};
        param foo :=
            1   2   3
            2   3   4
            3   4   5
        ;
        """
    )['foo']

    f = result[1][2]
    assert f == 3
    assert result[2][3] == 4
    assert result[3][4] == 5

def test_tuple_param():
    result = Amply(
        """
        set elem dimen 2;
        param foo{elem};
        param foo :=
            1   2   3
            2   3   4
            3   4   5
        ;
        """
    )['foo']

    f = result[1,2]
    assert f == 3
    assert result[2,3] == 4
    assert result[3,4] == 5

def test_comment():
    result = Amply(
        """
        # a comment
        set elem dimen 2;
        param foo{elem};
        param foo :=
            1   2   3
            2   3   4
            3   4   5
        ;
        """
    )['foo']

    f = result[1,2]
    assert f == 3
    assert result[2,3] == 4
    assert result[3,4] == 5

