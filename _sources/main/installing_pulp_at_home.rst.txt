.. _installation:

Installing PuLP at Home
=======================

PuLP is a free open source software written in Python. It is used to describe
optimisation problems as mathematical models. PuLP can then call any of numerous
external LP solvers (CBC, GLPK, CPLEX, Gurobi, etc.) to solve this model and then
use Python commands to manipulate and display the solution.

.. warning::

   **CBC is not included inside the PuLP wheel.** The legacy ``PULP_CBC_CMD``
   solver (which pointed at a CBC binary shipped inside the package) has been
   **removed**. To use CBC with PuLP:

   * run ``python -m pip install pulp[cbc]`` so the optional ``cbcbox``
     dependency is installed (PuLP will locate its CBC automatically), **or**
   * install CBC yourself and put ``cbc`` (Linux/macOS) or ``cbc.exe`` (Windows)
     on your ``PATH``,

   then use ``COIN_CMD`` or call ``prob.solve()`` when CBC is the default
   available backend. Without any solver, you will get ``PulpError: No solver available``.

Installing from PyPI
--------------------

PuLP requires **Python 3.9 or newer**.

**Recommended** install (PuLP **and** CBC via ``cbcbox``)::

    python -m pip install pulp[cbc]

With ``uv``::

    uv pip install "pulp[cbc]"

Installing only ``pulp`` (no extras) gives the modeler only; you must provide
your own ``cbc`` on ``PATH`` or install another solver and pass it explicitly.

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
   mode with dev dependencies **and** the CBC extra (needed for most tests and
   examples).

With **uv** (recommended)::

    uv venv
    uv pip install --group dev -e ".[cbc]"

With **pip**::

    python -m venv .venv
    source .venv/bin/activate   # On Windows: .venv\Scripts\activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[cbc]"

3. Run tests to confirm the build::

    uv run python -m unittest discover -s pulp/tests -v

Installing solvers
------------------

PuLP can use a variety of solvers. CBC is typically used through ``COIN_CMD``
after ``pip install pulp[cbc]`` or when ``cbc`` is on ``PATH``. For other
solvers and configuration, see the
:ref:`guide on configuring solvers <how_to_configure_solvers>`.
