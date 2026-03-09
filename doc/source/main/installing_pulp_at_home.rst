.. _installation:

Installing PuLP at Home
=======================

PuLP is a free open source software written in Python. It is used to describe
optimisation problems as mathematical models. PuLP can then call any of numerous
external LP solvers (CBC, GLPK, CPLEX, Gurobi, etc.) to solve this model and then
use Python commands to manipulate and display the solution.

Installing from PyPI
--------------------

PuLP requires **Python 3.9 or newer**.

The easiest way to install PuLP is with ``pip``::

    python -m pip install pulp

Or with ``uv``::

    uv pip install pulp

Building from source
--------------------

This version of PuLP includes a **Rust extension** (``pulp._rustcore``) that
implements the core model, variables, constraints, and affine expressions. The
build uses `maturin <https://github.com/PyO3/maturin>`_, which is invoked
automatically when you install the package from source.

**Requirements for building**

* **Python** 3.9 or newer
* **Rust** (latest stable). Install from https://rustup.rs/
* **uv** (recommended) or **pip** for installing the package
* **OS**: Windows, macOS (x86_64, arm64), or Linux (x86_64, arm64). The Rust
  extension is compiled for your host platform.

**Steps**

1. Clone the repository (or download and extract the source).
2. From the project root, create a virtual environment and install in editable
   mode with dev dependencies.

With **uv** (recommended)::

    uv venv
    uv pip install --group dev -e .

With **pip**::

    python -m venv .venv
    source .venv/bin/activate   # On Windows: .venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install --group dev -e .

3. Run tests to confirm the build::

    uv run python -m unittest discover -s pulp/tests -v

On Linux and macOS you may need to make the default CBC solver executable::

    sudo pulptest

Installing solvers
------------------

PuLP can use a variety of solvers. The default solver is the COIN-OR CBC solver,
which is included with PuLP. For other solvers and configuration, see the
:ref:`guide on configuring solvers <how_to_configure_solvers>`.
