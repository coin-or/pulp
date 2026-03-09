How to contribute to PuLP
======================================

This is a minimalistic guide to setup pulp and help you modify the code and send a PR.

The quick summary is:

#. Fork the repo.
#. Clone your forked repo.
#. Install dependencies.
#. Make your changes.
#. Create a test for your changes if needed.
#. Make sure all the tests pass.
#. Lint and format your code with ruff.
#. Ensure the docs are accurate.
#. Submit a Pull Request.


On top of having python installed, we will be using git and the command line. Also, we assume you have a github account and know how to fork a project.
We will use plain git through the command line but feel free to use the git client of your choice.

Forking PuLP
--------------

The PuLP repository is available at `https://github.com/coin-or/pulp <https://github.com/coin-or/pulp>`_.

You can follow the github guides to fork a project: `here <https://guides.github.com/activities/forking/>`_ and `also here <https://docs.github.com/en/github/getting-started-with-github/quickstart/fork-a-repo>`_.

You need a github account to fork a github project. It's free.

Cloning the project
----------------------------

You first need to download the pulp project from your fork. In the following command replace ``<USERNAME>`` with your actual username::

    git clone git@github.com:<USERNAME>/pulp.git

That's it, you will download the whole project.


Installing from source
----------------------------

PuLP includes a Rust extension (``pulp._rustcore``), so building from source requires:

* **Python** 3.9 or newer
* **Rust** (latest stable). Install from https://rustup.rs/
* **uv** (recommended) or **pip**

From the pulp directory, create a virtual environment and install the package in editable mode with dev dependencies.

With **uv** (recommended)::

    cd pulp
    uv venv
    uv pip install --group dev -e .

With **pip**::

    cd pulp
    python3 -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    python3 -m pip install --upgrade pip
    pip install --group dev -e .

This links the pulp package in your environment with the source files. The Rust extension is built automatically by maturin during install.

Running tests
----------------

Run the unit tests with::

    uv run python -m unittest discover -s pulp/tests -v

The test runner will detect solvers on your system and run tests for each one found.

Creating a test
-----------------

When you fix an issue in pulp or add a functionality, you should add a test to the repository. For this you should go to the file `tests/test_pulp.py` and add a new method that tests your change.

Applying the ruff linter / formatter
-----------------------------------------------------

We use `ruff <https://docs.astral.sh/ruff/>`_ for linting and formatting. Before sending your changes, run::

    uv run ruff check pulp
    uv run ruff format pulp

To check without modifying files (e.g. in CI)::

    uv run ruff check pulp && uv run ruff format pulp --check

You can integrate ruff in your IDE so it runs on save; see the `ruff editor docs <https://docs.astral.sh/ruff/integration/>`_.

Checking types
-------------------------------------

We use the **ty** type checker. Before sending your changes, run::

    uv run ty check pulp

Fix any reported errors before pushing.

Building the documentation
----------------------------

The documentation is built with `Sphinx <https://www.sphinx-doc.org/>`_ and reStructuredText. From the project root (with the dev environment activated)::

    cd doc
    make html

A folder named ``html`` will be created inside ``doc/build/``. Open ``doc/build/html/index.html`` in a browser. Rerun ``make html`` to rebuild after changes.

Making a Pull Request
----------------------------

When you're done with the changes in your machine and you're satisfied with the result you have, you can commit it, push it to github and then create a PR.
The first two are easy::

    git status # this shows what's changed
    git add some_modified_file.py # do this for all changes you want to write
    git commit -m "some message" # include a meaningful message
    git push origin

In order to create a PR to the original repository, follow one of github's  `guides <https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request>`_.

