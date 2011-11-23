Amply
======


Introduction
------------

Amply allows you to load and manipulate AMPL data as Python data structures.

Amply only supports a specific subset of the AMPL syntax:

* set declarations
* set data statements
* parameter declarations
* parameter data statements

Declarations and data statements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Typically, problems expressed in AMPL consist of two parts, a *model* section and a *data* section.
Amply is only designed to parse the parameter and set statements contained within AMPL data sections.
However, in order to parse these statements correctly, information that would usually be contained 
within the model section may be required. For instance, it may not be possible to infer the dimension
of a set purely from its data statement. Therefore, Amply also supports set and parameter declarations. 
These do not have to be put in a separate section, they only need to occur before the corresponding
data statement.


The declaration syntax supported is extremely limited, and does not include most
elements of the AMPL programming language. The intention is that this library
is used as a way of loading data specified in an AMPL-like syntax.

Furthermore, Amply does not perform any validation on data statements.

About this document
^^^^^^^^^^^^^^^^^^^^

This document is intended as a guide to the syntax supported by Amply, and not as a general
AMPL reference manual. For more in depth coverage see the `GNU MathProg manual, Chapter 5: Model data
<http://www.cs.unb.ca/~bremner/docs/glpk/gmpl.pdf>`_ or the following links:

* `Sets in AMPL <http://twiki.esc.auckland.ac.nz/twiki/bin/view/OpsRes/SetsInAMPL>`_
* `Parameters in AMPL <http://twiki.esc.auckland.ac.nz/twiki/bin/view/OpsRes/ParametersInAMPL>`_

Quickstart Guide
----------------

.. testsetup:: 

  >>> from pulp import Amply

Import the class: ::

  >>> from pulp import Amply

A simple set. Sets behave a lot like lists.

.. doctest::

  >>> data = Amply("set CITIES := Auckland Wellington Christchurch;")
  >>> print data.CITIES
  <SetObject: ['Auckland', 'Wellington', 'Christchurch']>
  >>> print data['CITIES']
  <SetObject: ['Auckland', 'Wellington', 'Christchurch']>
  >>> for c in data.CITIES: print c
  ...
  Auckland
  Wellington
  Christchurch
  >>> print data.CITIES[0]
  Auckland
  >>> print len(data.CITIES)
  3


Data can be integers, reals, symbolic, or quoted strings:

.. doctest::
  
  >>> data = Amply("""
  ...   set BitsNPieces := 0 3.2 -6e4 Hello "Hello, World!";
  ... """)
  >>> print data.BitsNPieces
  <SetObject: [0.0, 3.2000000000000002, -60000.0, 'Hello', 'Hello, World!']>

Sets can contain multidimensional data, but we have to declare them to be so first.

.. doctest::

  >>> data = Amply("""
  ... set pairs dimen 2;
  ... set pairs := (1, 2) (2, 3) (3, 4);
  ... """)
  >>> print data.pairs
  <SetObject: [(1, 2), (2, 3), (3, 4)]>

Sets themselves can be multidimensional (i.e. be subscriptable):

.. doctest::

  >>> data = Amply("""
  ... set CITIES{COUNTRIES};
  ... set CITIES[Australia] := Adelaide Melbourne Sydney;
  ... set CITIES[Italy] := Florence Milan Rome;
  ... """)
  >>> print data.CITIES['Australia']
  ['Adelaide', 'Melbourne', 'Sydney']
  >>> print data.CITIES['Italy']
  ['Florence', 'Milan', 'Rome']

Note that in the above example, the set COUNTRIES didn't actually have to exist itself.
Amply does not perform any validation on subscripts, it only uses them to figure out
how many subscripts a set has. To specify more than one, separate them by commas:

.. doctest::
  
  >>> data = Amply("""
  ... set SUBURBS{COUNTRIES, CITIES};
  ... set SUBURBS[Australia, Melbourne] := Docklands 'South Wharf' Kensington;
  ... """)
  >>> print data.SUBURBS['Australia', 'Melbourne']
  ['Docklands', 'South Wharf', 'Kensington']

*Slices* can be used to simplify the entry of multi-dimensional data.

.. doctest::

  >>> data=Amply("""
  ... set TRIPLES dimen 3;
  ... set TRIPLES := (1, 1, *) 2 3 4 (*, 2, *) 6 7 8 9 (*, *, *) (1, 1, 1);
  ... """)
  >>> print data.TRIPLES
  <SetObject: [(1, 1, 2), (1, 1, 3), (1, 1, 4), (6, 2, 7), (8, 2, 9), (1, 1, 1)]>
  >

Set data can also be specified using a matrix notation.
A '+' indicates that the pair is included in the set whereas a '-' indicates a
pair not in the set. 

.. doctest::

  >>> data=Amply("""
  ... set ROUTES dimen 2;
  ... set ROUTES : A B C D :=
  ...            E + - - +
  ...            F + + - -
  ... ;
  ... """)
  >>> print data.ROUTES
  <SetObject: [('E', 'A'), ('E', 'D'), ('F', 'A'), ('F', 'B')]>

Matrices can also be transposed: 

.. doctest::

  >>> data=Amply("""
  ... set ROUTES dimen 2;
  ... set ROUTES (tr) : E F :=
  ...                 A + +
  ...                 B - +
  ...                 C - -
  ...                 D + -
  ... ;
  ... """)
  >>> print data.ROUTES
  <SetObject: [('E', 'A'), ('F', 'A'), ('F', 'B'), ('E', 'D')]>

Matrices only specify 2d data, however they can be combined with slices
to define higher-dimensional data:

.. doctest::

  >>> data = Amply("""
  ... set QUADS dimen 2;
  ... set QUADS :=
  ... (1, 1, *, *) : 2 3 4 :=
  ...              2 + - +
  ...              3 - + +
  ... (1, 2, *, *) : 2 3 4 :=
  ...              2 - + -
  ...              3 + - -
  ... ;
  ... """)
  >>> print data.QUADS
  <SetObject: [(1, 1, 2, 2), (1, 1, 2, 4), (1, 1, 3, 3), (1, 1, 3, 4), (1, 2, 2, 3), (1, 2, 3, 2)]>

Parameters are also supported:

.. doctest::

  >>> data = Amply("""
  ... param T := 30;
  ... param n := 5;
  ... """)
  >>> print data.T
  30
  >>> print data.n
  5
   
Parameters are commonly indexed over sets. No validation is done by Amply,
and the sets do not have to exist. Parameter objects are represented
as a mapping.

.. doctest::

  >>> data = Amply("""
  ... param COSTS{PRODUCTS};
  ... param COSTS :=
  ...   FISH 8.5
  ...   CARROTS 2.4
  ...   POTATOES 1.6
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'POTATOES': 1.6000000000000001, 'FISH': 8.5, 'CARROTS': 2.3999999999999999}>
  >>> print data.COSTS['FISH']
  8.5

Parameter data statements can include a *default* clause. If a '.' is included
in the data, it is replaced with the default value:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{P};
  ... param COSTS default 2 :=
  ... F 2
  ... E 1
  ... D .
  ... ;
  ... """)
  >>> print data.COSTS['D']
  2.0

Parameter declarations can also have a default clause. For these parameters,
any attempt to access the parameter for a key that has not been defined
will return the default value:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{P} default 42;
  ... param COSTS :=
  ... F 2
  ... E 1
  ... ;
  ... """)
  >>> print data.COSTS['DOES NOT EXIST']
  42.0

Parameters can be indexed over multiple sets. The resulting values can be
accessed by treating the parameter object as a nested dictionary, or by
using a tuple as an index:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{CITIES, PRODUCTS};
  ... param COSTS :=
  ...  Auckland FISH 5
  ...  Auckland CHIPS 3
  ...  Wellington FISH 4
  ...  Wellington CHIPS 1
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'Wellington': {'FISH': 4.0, 'CHIPS': 1.0}, 'Auckland': {'FISH': 5.0, 'CHIPS': 3.0}}>
  >>> print data.COSTS['Wellington']['CHIPS'] # nested dict
  1.0
  >>> print data.COSTS['Wellington', 'CHIPS'] # tuple as key
  1.0

Parameters support a slice syntax similar to that of sets:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{CITIES, PRODUCTS};
  ... param COSTS :=
  ...  [Auckland, * ]
  ...   FISH 5
  ...   CHIPS 3
  ...  [Wellington, * ]
  ...   FISH 4
  ...   CHIPS 1
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'Wellington': {'FISH': 4.0, 'CHIPS': 1.0}, 'Auckland': {'FISH': 5.0, 'CHIPS': 3.0}}>



Parameters indexed over two sets can also be specified in tabular format:


.. doctest::

  >>> data = Amply("""
  ... param COSTS{CITIES, PRODUCTS};
  ... param COSTS: FISH CHIPS :=
  ...  Auckland    5    3
  ...  Wellington  4    1
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'Wellington': {'FISH': 4.0, 'CHIPS': 1.0}, 'Auckland': {'FISH': 5.0, 'CHIPS': 3.0}}>

Tabular data can also be transposed:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{CITIES, PRODUCTS};
  ... param COSTS (tr): Auckland Wellington :=
  ...            FISH   5        4
  ...            CHIPS  3        1
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'Wellington': {'FISH': 4.0, 'CHIPS': 1.0}, 'Auckland': {'FISH': 5.0, 'CHIPS': 3.0}}>
   
   
Slices can be combined with tabular data for parameters indexed over more than
2 sets:

.. doctest::

  >>> data = Amply("""
  ... param COSTS{CITIES, PRODUCTS, SIZE};
  ... param COSTS :=
  ...  [Auckland, *, *] :   SMALL LARGE :=
  ...                 FISH  5     9
  ...                 CHIPS 3     5
  ...  [Wellington, *, *] : SMALL LARGE :=
  ...                 FISH  4     7
  ...                 CHIPS 1     2
  ... ;
  ... """)
  >>> print data.COSTS
  <ParamObject: {'Wellington': {'FISH': {'SMALL': 4.0, 'LARGE': 7.0}, 'CHIPS': {'SMALL': 1.0, 'LARGE': 2.0}}, 'Auckland': {'FISH': {'SMALL': 5.0, 'LARGE': 9.0}, '


API
---

All functionality is contained within the ``Amply`` class.

.. class:: Amply(string="")

  .. method:: load_string(string)

    Parse string data.

  .. method:: load_file(file)

    Parse contents of file or file-like object (has a read() method).

  .. staticmethod:: from_file(file)

    Alternate constructor. Create Amply object from contents of file or file-like object.


The parsed data structures can then be accessed from an ``Amply`` object via
attribute lookup (if the name of the symbol is a valid Python name) or item
lookup. ::

    from pulp import Amply

    data = Amply("set CITIES := Auckland Hamilton Wellington")

    # attribute lookup
    assert data.CITIES == ['Auckland', 'Hamilton', 'Wellington']

    # item lookup
    assert data['CITIES'] == data.CITIES

Note that additional data may be loaded into an Amply object simply by calling
one of its methods. A common idiom might be to specify the set and parameter
declarations within your Python script, then load the actual data from
external files. ::

    from pulp import Amply

    data = Amply("""
      set CITIES;
      set ROUTES dimen 2;
      param COSTS{ROUTES};
      param DISTANCES{ROUTES};
    """)

    for data_file in ('cities.dat', 'routes.dat', 'costs.dat', 'distances.dat'):
        data.load_file(open(data_file))

.. Commented out the below, not sure if we need it (incomplete)

    Reference
    ---------

    Sets
    ^^^^

    Set declarations
    ~~~~~~~~~~~~~~~~

    A set declaration is an extremely limited version of set statements which are valid in AMPL models.
    They determine the *subscript domain* and *data dimension* of the set. If not specified, the default
    subscript domain is an empty set and the default dimension is 1.

    .. productionlist::
        set_def_stmt: "set" `name` [`subscript_domain`] ["dimen" `integer`] ";"
        subscript_domain: "{" `name` ("," `name`)* "}"

    The following statment declares a set named "countries". ::
        
        set countries;

    The following statement declares a set named "cities" which is indexed over "countries". ::

        set cities {countries};

    The following declares a set named "routes" with 2d data. ::

        set routes dimen 2;

    Set data statements
    ~~~~~~~~~~~~~~~~~~~~~

    A set data statement is used to specify the members of a set. It consists of one or more
    *data records*. There are four types of data records: simple data, slice records, matrix
    data and transposed matrix data.

    .. productionlist::
        set_stmt: "set" `name` [`set_member`] `data_record`+ ";"
        data_record: `simple_data` | `set_slice_record` | `matrix_data` | `tr_matrix_data`

    Simple Data
    ############

    A simple data record is an optionally comma-separated list of data values.

    .. productionlist::
        simple_data: `data` ([","] `data`)*

    For instance: ::
        
        set CITIES := Auckland Hamilton 'Palmerston North' Wellington;

    ::
        
        set ROUTES dimen 2;
        set ROUTES := (Auckland, Hamilton) (Auckland, Wellington);

    Slice Records
    ###############

    Slice records are used to simplify the entry of multi-dimensional sets. They allow you to partially
    specify the values of elements. A slice affects all data records that follow it (until a new slice
    is specified). 

    .. productionlist::
        set_slice_record: "(" `set_slice_component` ("," `set_slice_component`)* ")"
        set_slice_component: `number` | `symbol` | "*"

    This is best demonstrated by some examples. The sets A and B are identical: ::

        set A dimen 3;
        set B dimen 3;

        set A := (1, 2, 3) (1, 3, 2) (1, 4, 6) (1, 8, 8) (2, 1, 3) (2, 1, 1) (2, 1, 2);
        set B := (1, *, *) (2, 3) (3, 2) (4, 6) (8, 8) (2, 1, *) 3 1 2;

    The number of asterisks in a slice is called the *slice dimension*. Any data records that follow
    are interpreted as being of the same dimension; the value is taken as the value of the slice with
    the asterisks replaced with the value of the record.

    Matrix records
    ################

    Matrix records are a convenient way of specifying 2-dimensional data. The data record looks like
    a matrix with row and column headings, where the values are either '+' if the combination is in
    the set, and '-' if the combination is not in the set. A common use-case is for defining the
    set of arcs that exist between a set of nodes.

    .. productionlist::
        matrix_data: ":" `matrix_columns` ":=" `matrix_row`+
        matrix_columns: `data`+
        matrix_row: `data` ("+"|"-")+
        tr_matrix_data: "(tr)" `matrix_data`

    Matrices can also be transposed by including ``(tr)`` immediately preceding the record.

    In the example below the sets A, B and C are identical: ::

        set A dimen 2;
        set B dimen 2;
        set C dimen 2;

        set A := (1, 1) (1, 3) (2, 2) (3, 1) (3, 2) (3, 3);
        set B : 1 2 3 :=
              1 + - +
              2 - + -
              3 + + +
        ;
        set C (tr) : 1 2 3 :=
                   1 + - +
                   2 - + +
                   3 + - +
        ;


    Matrices can be used for sets with higher dimensions by placing them after 2 dimensional
    slice records.


    Set examples
    ~~~~~~~~~~~~

    Parameters
    ^^^^^^^^^^^^

    Plain Data
    ~~~~~~~~~~~~~

    Tabular data
    ~~~~~~~~~~~~~~

    Tabbing Data
    ~~~~~~~~~~~~~~



