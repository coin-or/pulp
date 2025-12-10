"""
Column Generation Functions

Authors: Antony Phillips,  Dr Stuart Mitchell  2008
"""

from typing import Dict, List, Optional, Tuple, Union

# Import PuLP modeler functions
from pulp import *


class Pattern:
    """
    Information on a specific pattern in the SpongeRoll Problem
    """

    cost = 1
    trimValue = 0.04
    totalRollLength = 20
    lenOpts = ["5", "7", "9"]

    def __init__(self, name: str, lengths: List[int]) -> None:
        self.name = name
        self.lengthsdict = dict(zip(self.lenOpts, lengths))

    def __str__(self) -> str:
        return self.name

    def trim(self) -> int:
        return Pattern.totalRollLength - sum(
            [int(i) * int(self.lengthsdict[i]) for i in self.lengthsdict]
        )


def masterSolve(
    Patterns: List[Pattern],
    rollData: Dict[str, List[Union[float, int]]],
    relax: bool = True,
) -> Union[Dict[str, Optional[float]], Tuple[float, Dict[str, int]]]:
    # The rollData is made into separate dictionaries
    (rollDemand, surplusPrice) = splitDict(rollData)

    # The variable 'prob' is created
    prob = LpProblem("Cutting Stock Problem", LpMinimize)

    # vartype represents whether or not the variables are relaxed
    if relax:
        vartype = LpContinuous
    else:
        vartype = LpInteger

    # The problem variables are created
    pattVars = LpVariable.dicts("Pattern", Patterns, 0, None, vartype)
    surplusVars = LpVariable.dicts("Surplus", Pattern.lenOpts, 0, None, vartype)

    # The objective function is entered: (the total number of large rolls used * the cost of each) -
    # (the value of the surplus stock) - (the value of the trim)
    prob += (
        lpSum([pattVars[i] * Pattern.cost for i in Patterns])
        - lpSum([surplusVars[i] * surplusPrice[i] for i in Pattern.lenOpts])
        - lpSum([pattVars[i] * i.trim() * Pattern.trimValue for i in Patterns])
    )

    # The demand minimum constraint is entered
    for j in Pattern.lenOpts:
        prob += (
            lpSum([pattVars[i] * i.lengthsdict[j] for i in Patterns]) - surplusVars[j]
            >= rollDemand[j],
            f"Min{j}",
        )

    # The problem is solved
    prob.solve()

    # The variable values are rounded
    prob.roundSolution()

    if relax:
        # Creates a dual variables list
        duals = {}
        for name, i in zip(["Min5", "Min7", "Min9"], Pattern.lenOpts):
            duals[i] = prob.constraints[name].pi

        return duals

    else:
        # Creates a dictionary of the variables and their values
        varsdict: dict[str, int] = {}
        for v in prob.variables():
            if v.varValue is None:
                varsdict[v.name] = 0
            else:
                varsdict[v.name] = int(v.varValue)

        # The number of rolls of each length in each pattern is printed
        for p in Patterns:
            print(p, " = %s" % [p.lengthsdict[j] for j in Pattern.lenOpts])
        my_value: float = value(prob.objective)
        return my_value, varsdict


def subSolve(
    Patterns: List[Pattern], duals: Dict[str, Optional[float]]
) -> Tuple[List[Pattern], bool]:
    # The variable 'prob' is created
    prob = LpProblem("SubProb", LpMinimize)

    # The problem variables are created
    _vars = LpVariable.dicts("Roll Length", Pattern.lenOpts, 0, None, LpInteger)

    trim = LpVariable("Trim", 0, None, LpInteger)

    # The objective function is entered: the reduced cost of a new pattern
    prob += (Pattern.cost - Pattern.trimValue * trim) - lpSum(
        [_vars[i] * duals[i] for i in Pattern.lenOpts]
    ), "Objective"

    # The conservation of length constraint is entered
    prob += (
        lpSum([_vars[i] * int(i) for i in Pattern.lenOpts]) + trim
        == Pattern.totalRollLength,
        "lengthEquate",
    )

    # The problem is solved
    prob.solve()

    # The variable values are rounded
    prob.roundSolution()

    # The new pattern is written to a dictionary
    varsdict: dict[str, int] = {}
    newPattern = {}
    for v in prob.variables():
        if v.varValue is None:
            varsdict[v.name] = 0
        else:
            varsdict[v.name] = int(v.varValue)
    for i, j in zip(
        Pattern.lenOpts, ["Roll_Length_5", "Roll_Length_7", "Roll_Length_9"]
    ):
        newPattern[i] = varsdict[j]

    # Check if there are more patterns which would reduce the master LP objective function further
    if value(prob.objective) < -(10**-5):
        morePatterns = True  # continue adding patterns
        Patterns += [
            Pattern("P" + str(len(Patterns)), [newPattern[i] for i in ["5", "7", "9"]])
        ]
    else:
        morePatterns = False  # all patterns have been added

    return Patterns, morePatterns
