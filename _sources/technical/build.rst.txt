.. _technical_build:

Build architecture
==================

This version of PuLP ships a **Rust extension** that implements the core data structures and logic. The Python package wraps this extension and adds solver APIs, file I/O, and high-level helpers.

Rust extension (``pulp._rustcore``)
-----------------------------------

The extension is built with `PyO3 <https://pyo3.rs/>`_ and provides:

* **Model** — Container for variables, constraints, and objective (backed by ``ModelCore`` in Rust).
* **Variable** — Handle to a variable (name, bounds, category, value, reduced cost).
* **Constraint** — Handle to a constraint (name, sense, RHS, dual value, slack).
* **AffineExpr** — Affine expression (linear combination of variables plus constant) used for the objective and for constraint left-hand sides.

Enums such as **Category** (continuous/integer/binary), **Sense** (≤ / = / ≥), and **ObjSense** (minimize/maximize) are also defined in Rust and exposed to Python.

The extension is built as a native library (e.g. ``_rustcore.cp312-win_amd64.pyd`` on Windows) and imported as ``pulp._rustcore``.

Build system
------------

* **maturin** is the build backend (see ``pyproject.toml``). It compiles the Rust crate and produces a wheel that includes the extension.
* **Rust** toolchain (stable) is required when building from source. Install via https://rustup.rs/.
* **Python** 3.9+ is required. The wheel is built for the active Python version and platform (Windows, macOS, Linux; x86_64 and arm64 where applicable).

There is no need to run maturin manually when installing: ``pip install -e .`` or ``uv pip install -e .`` invokes the build backend, which runs maturin and compiles the Rust code.
