# Utility functions
from typing import (
    Any,
    Optional,
    Union,
    Dict,
    List,
    Tuple,
    Type,
    TypeVar,
    Protocol,
    cast,
    TYPE_CHECKING,
)
import itertools
import collections

if TYPE_CHECKING:
    from pulp.pulp import LpAffineExpression, LpVariable

_KT = TypeVar("_KT")
_T = TypeVar("_T")

import os

if os.name == "posix":

    def resource_clock() -> float:
        import resource

        return resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime


def isNumber(x: Any) -> bool:
    """Returns true if x is an int or a float"""
    return isinstance(x, (int, float))


def value(
    x: Union[int, float, "LpVariable", "LpAffineExpression", None]
) -> Union[int, float, None]:
    """Returns the value of the variable/expression x, or x if it is a number"""
    if x is None:
        return None
    elif isNumber(x):
        x = cast(Union[int, float], x)
        return x
    else:
        x = cast("Union[LpVariable, LpAffineExpression]", x)
        return x.value()


def valueOrDefault(
    x: Union[int, float, "LpVariable", "LpAffineExpression"]
) -> Union[int, float]:
    """Returns the value of the variable/expression x, or x if it is a number
    Variable without value (None) are affected a possible value (within their
    bounds)."""
    if isNumber(x):
        x = cast(Union[int, float], x)
        return x
    else:
        x = cast(Union["LpVariable", "LpAffineExpression"], x)
        return x.valueOrDefault()


# target is python 3.7, useless compatibility code removed
from itertools import combinations as combination
from itertools import permutations as permutation


def allpermutations(orgset: List[_T], k: int) -> "itertools.chain[Tuple[_T, ...]]":
    """
    returns all permutations of orgset with up to k items

    :param orgset: the list to be iterated
    :param k: the maxcardinality of the subsets

    :return: an iterator of the subsets

    example:

    >>> c = allpermutations([1,2,3,4],2)
    >>> for s in c:
    ...     print(s)
    (1,)
    (2,)
    (3,)
    (4,)
    (1, 2)
    (1, 3)
    (1, 4)
    (2, 1)
    (2, 3)
    (2, 4)
    (3, 1)
    (3, 2)
    (3, 4)
    (4, 1)
    (4, 2)
    (4, 3)
    """
    return itertools.chain(*[permutation(orgset, i) for i in range(1, k + 1)])


def allcombinations(orgset: List[_T], k: int) -> "itertools.chain[Tuple[_T, ...]]":
    """
    returns all combinations of orgset with up to k items

    :param orgset: the list to be iterated
    :param k: the maxcardinality of the subsets

    :return: an iterator of the subsets

    example:

    >>> c = allcombinations([1,2,3,4],2)
    >>> for s in c:
    ...     print(s)
    (1,)
    (2,)
    (3,)
    (4,)
    (1, 2)
    (1, 3)
    (1, 4)
    (2, 3)
    (2, 4)
    (3, 4)
    """
    return itertools.chain(*[combination(orgset, i) for i in range(1, k + 1)])


_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")


def makeDict(
    headers: List[List[_T1]], array: List[_T2], default: Any = None
) -> Dict[_T1, Dict[_T1, _T2]]:
    """
    makes a list into a dictionary with the headings given in headings
    headers is a list of header lists
    array is a list with the data
    """
    result, _defdict = __makeDict(headers, array, default)
    return result


def __makeDict(headers: Any, array: Any, default: Optional[Any] = None) -> Any:
    # this is a recursive function so end the recursion as follows
    result = {}
    returndefaultvalue = None
    if len(headers) == 1:
        result.update(dict(zip(headers[0], array)))  # type: ignore
        defaultvalue = default
    else:
        for i, h in enumerate(headers[0]):
            result[h], defaultvalue = __makeDict(headers[1:], array[i], default)
            result = result
    if default is not None:
        # defaultvalue = cast(Any, defaultvalue)
        f = lambda: defaultvalue  # type: ignore
        defresult = collections.defaultdict(f)  # type: ignore
        result = result
        defresult.update(result)  # type: ignore
        result = defresult  # type: ignore
        returndefaultvalue = collections.defaultdict(f)  # type: ignore
    return result, returndefaultvalue


def splitDict(data: Dict[_KT, List[_T]]) -> Tuple[Dict[_KT, _T], ...]:
    """
    Split a dictionary with lists as the data, into smaller dictionaries

    :param dict data: A dictionary with lists as the values

    :return: A tuple of dictionaries each containing the data separately,
            with the same dictionary keys
    """
    # find the maximum number of items in the dictionary
    maxitems = max([len(values) for values in data.values()])
    output: List[Dict[_KT, _T]] = [dict() for _ in range(maxitems)]
    for key, values in data.items():
        for i, val in enumerate(values):
            output[i][key] = val

    return tuple(output)


class Constructable(Protocol):
    def __init__(self, *args: Any, **kwargs: Any): ...


_T_class = TypeVar("_T_class", bound=Constructable)


def read_table(
    data: str, coerce_type: Type[_T_class], transpose: bool = False
) -> Dict[Tuple[str, str], _T_class]:
    """
    Reads in data from a simple table and forces it to be a particular type

    This is a helper function that allows data to be easily constained in a
    simple script
    ::return: a dictionary of with the keys being a tuple of the strings
       in the first row and colum of the table
    :param str data: the multiline string containing the table data
    :param coerce_type: the type that the table data is converted to
    :param bool transpose: reverses the data if needed

    Example:
    >>> table_data = '''
    ...         L1      L2      L3      L4      L5      L6
    ... C1      6736    42658   70414   45170   184679  111569
    ... C2      217266  227190  249640  203029  153531  117487
    ... C3      35936   28768   126316  2498    130317  74034
    ... C4      73446   52077   108368  75011   49827   62850
    ... C5      174664  177461  151589  153300  59916   135162
    ... C6      186302  189099  147026  164938  149836  286307
    ... '''
    >>> table = read_table(table_data, int)
    >>> table[("C1","L1")]
    6736
    >>> table[("C6","L5")]
    149836
    """
    lines = data.splitlines()
    headings = lines[1].split()
    result: Dict[Tuple[str, str], _T_class] = {}
    for row in lines[2:]:
        items = row.split()
        for i, item in enumerate(items[1:]):
            if transpose:
                key = (headings[i], items[0])
            else:
                key = (items[0], headings[i])
            result[key] = coerce_type(item)
    return result
