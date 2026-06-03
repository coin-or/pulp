# PuLP : Python LP Modeler
# Version 1.20

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id: __init__.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Module file that imports all of the pulp functions

Copyright 2007- Stuart Mitchell (s.mitchell@auckland.ac.nz)
"""

# Pre-load highspy's C extension with RTLD_GLOBAL before any other imports.
# highspy._core uses C++ exception handling (__cxa_throw etc.) that must be globally
# visible when pulp._rustcore (a Rust/pyo3 extension) is later loaded into the same
# process. Without RTLD_GLOBAL, the C++ runtime state gets split across multiple
# symbol scopes, causing a segfault when highspy.Highs.run() is called.
# We use find_spec("highspy") (the package) not find_spec("highspy._core") (the
# submodule) to avoid triggering highspy/__init__.py which would import _core with
# RTLD_LOCAL before our explicit RTLD_GLOBAL call can take effect.
try:
    import ctypes as _ctypes
    import glob as _glob
    import importlib.util as _ilu

    _pkg_spec = _ilu.find_spec("highspy")
    if _pkg_spec is not None and _pkg_spec.submodule_search_locations:
        for _loc in _pkg_spec.submodule_search_locations:
            for _so in _glob.glob(_loc + "/_core*.so"):
                _ctypes.CDLL(_so, _ctypes.RTLD_GLOBAL)
                break
    del _ctypes, _glob, _ilu, _pkg_spec
except Exception:
    pass

from importlib.metadata import version

__version__ = version("PuLP")

from .apis import *
from .constants import *
from .pulp import *
from .utilities import *
