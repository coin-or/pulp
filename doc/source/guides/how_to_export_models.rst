How to export models in PuLP
======================================

Warning! This is experimental. Use at your own risk. And write an issue if you see anything weird.

Exporting a model can be useful when the building time takes too long or when the model needs to be passed to another computer to solve. Or many other reasons.
PuLP offers a way to export a model into a dictionary of a json file. The json file saves enough data to be able to rebuild a new model on reading it.

Considerations
------------------

The following considerations need to be taken into account:

#. Variable names need to be unique. PuLP permits having variable names because it uses an internal code for each one. But we do not export that code. So we identify variables by their name only.
#. Variables are not exported in a grouped way. This means that if you had several `dictionaries of many variables each` you will end up with a very long list of variables. This can be seen in the Example 2.
#. Output information is also written. This means that the status, solution status, the values of variables and shadow prices / reduced costs are exported too. This means that it is possible to export a model that has been solved and then read it again only to see the values of the variables.
#. For json, we use the base `json` package. But if `ujson` is available, we use that so the import / export can be really fast.

Example 1
----------------

A very simple example taken from the internal tests. Imagine the following problem::

    from pulp import *
    prob = LpProblem("test_export_dict_MIP", const.LpMinimize)
    x = LpVariable("x", 0, 4)
    y = LpVariable("y", -1, 1)
    z = LpVariable("z", 0, None, const.LpInteger)
    prob += x + 4 * y + 9 * z, "obj"
    prob += x + y <= 5, "c1"
    prob += x + z >= 10, "c2"
    prob += -y + z == 7.5, "c3"

We can now export the problem into a dictionary::

    data = prob.to_dict()

We now have a dictionary with a lot of data::

    {'constraints': [{'coefficients': [{'name': 'x', 'value': 1},
                                       {'name': 'y', 'value': 1}],
                      'constant': -5,
                      'name': 'c1',
                      'pi': None,
                      'sense': -1},
                     {'coefficients': [{'name': 'x', 'value': 1},
                                       {'name': 'z', 'value': 1}],
                      'constant': -10,
                      'name': 'c2',
                      'pi': None,
                      'sense': 1},
                     {'coefficients': [{'name': 'y', 'value': -1},
                                       {'name': 'z', 'value': 1}],
                      'constant': -7.5,
                      'name': 'c3',
                      'pi': None,
                      'sense': 0}],
     'objective': {'coefficients': [{'name': 'x', 'value': 1},
                                    {'name': 'y', 'value': 4},
                                    {'name': 'z', 'value': 9}],
                   'name': 'obj'},
     'parameters': {'name': 'test_export_dict_MIP',
                    'sense': 1,
                    'sol_status': 0,
                    'status': 0},
     'sos1': {},
     'sos2': {},
     'variables': [{'cat': 'Continuous',
                    'dj': None,
                    'lowBound': 0,
                    'name': 'x',
                    'upBound': 4,
                    'varValue': None},
                   {'cat': 'Continuous',
                    'dj': None,
                    'lowBound': -1,
                    'name': 'y',
                    'upBound': 1,
                    'varValue': None},
                   {'cat': 'Integer',
                    'dj': None,
                    'lowBound': 0,
                    'name': 'z',
                    'upBound': None,
                    'varValue': None}]}


We can now import this dictionary::

    var1, prob1 = LpProblem.from_dict(data)
    var1
    # {'x': x, 'y': y, 'z': z}
    prob1
    # test_export_dict_MIP:
    # MINIMIZE
    # 1*x + 4*y + 9*z + 0
    # SUBJECT TO
    # c1: x + y <= 5
    # c2: x + z >= 10
    # c3: - y + z = 7.5
    # VARIABLES
    # x <= 4 Continuous
    # -1 <= y <= 1 Continuous
    # 0 <= z Integer

As you can see we need get a tuple with a variables dictionary and a PuLP model object.
We can now solve that problem::

    prob1.solve()

And the result will be available in our *new* variables::

    var1['x'].value()
    # 3.0


Example 2
----------------

We will use as example the model in :ref:`set-partitioning-problem`::

    import pulp

    max_tables = 5
    max_table_size = 4
    guests = 'A B C D E F G I J K L M N O P Q R'.split()

    def happiness(table):
        """
        Find the happiness of the table
        - by calculating the maximum distance between the letters
        """
        return abs(ord(table[0]) - ord(table[-1]))
                    
    #create list of all possible tables
    possible_tables = [tuple(c) for c in pulp.allcombinations(guests, 
                                            max_table_size)]

    #create a binary variable to state that a table setting is used
    x = pulp.LpVariable.dicts('table', possible_tables, 
                                lowBound = 0,
                                upBound = 1,
                                cat = pulp.LpInteger)

    seating_model = pulp.LpProblem("Wedding_Seating_Model", pulp.LpMinimize)

    seating_model += pulp.lpSum([happiness(table) * x[table] for table in possible_tables])

    #specify the maximum number of tables
    seating_model += pulp.lpSum([x[table] for table in possible_tables]) <= max_tables, \
                                "Maximum_number_of_tables"

    #A guest must seated at one and only one table
    for guest in guests:
        seating_model += pulp.lpSum([x[table] for table in possible_tables
                                    if guest in table]) == 1, "Must_seat_%s"%guest


Right now, we could directly solve the model doing::

    seating_model.solve()

Instead, we are going to export it to a json file::

    seating_model.to_json("seating_model.json")

And re-import it::

    wedding_vars, wedding_model = LpProblem.from_json("seating_model.json")

We can inspect the variables::

    wedding_vars
    {"table_('A',)": table_('A',), "table_('A',_'B')": table_('A',_'B'), "table_('A',_'B',_'C')": table_('A',_'B',_'C'), "table_('A',_'B',_'C',_'D')": table_('A',_'B',_'C',_'D'), "table_('A',_'B',_'C',_'E')": table_('A',_'B',_'C',_'E'), ...}

As can be seen, it is no longer a dictionary indexed by the original tuples. Sadly, it has become a dictionary of concatenated names.

We can still solve the model though::

    wedding_model.solve()

And inspect some of the values::

    wedding_vars["table_('M',_'N')"].value()
    # 1.0
