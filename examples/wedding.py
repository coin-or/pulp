"""
A set partitioning model of a wedding seating problem

Authors: Stuart Mitchell 2009
"""

import pulp

max_tables = 5
max_table_size = 4
guests = "A B C D E F G I J K L M N O P Q R".split()


def happiness(table):
    """
    Find the happiness of the table
    - by calculating the maximum distance between the letters
    """
    return abs(ord(table[0]) - ord(table[-1]))


# BEGIN possible_tables
# create list of all possible tables
possible_tables = [tuple(c) for c in pulp.allcombinations(guests, max_table_size)]
# END possible_tables

# BEGIN define_x
# create a binary variable to state that a table setting is used
x = pulp.LpVariable.dicts(
    "table", possible_tables, lowBound=0, upBound=1, cat=pulp.LpInteger
)
# END define_x

# BEGIN class_and_obj_fn
seating_model = pulp.LpProblem("Wedding Seating Model", pulp.LpMinimize)

seating_model += pulp.lpSum([happiness(table) * x[table] for table in possible_tables])
# END class_and_obj_fn

# BEGIN total_table_constraint
# specify the maximum number of tables
seating_model += (
    pulp.lpSum([x[table] for table in possible_tables]) <= max_tables,
    "Maximum_number_of_tables",
)
# END total_table_constraint

# BEGIN exactly_one_table_constraint
# A guest must seated at one and only one table
for guest in guests:
    seating_model += (
        pulp.lpSum([x[table] for table in possible_tables if guest in table]) == 1,
        f"Must_seat_{guest}",
    )
# END exactly_one_table_constraint

seating_model.solve()

print(f"The chosen tables are out of a total of {len(possible_tables)}:")
for table in possible_tables:
    if x[table].value() == 1.0:
        print(table)
