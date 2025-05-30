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
#. Lint your code with black.
#. Ensure the docs are accurate.
#. Submit a Pull Request.


On top of having python installed, we will be using git and the command line. Also, we assume you have a github account and know how to fork a project.
We will use plain git through the command line but feel free to use the git client of your choice.

Forking PuLP
--------------

You can follow the github guides to fork a project: `here <https://guides.github.com/activities/forking/>`_ and `also here <https://docs.github.com/en/github/getting-started-with-github/quickstart/fork-a-repo>`_.

You need a github account to fork a github project. It's free.

Cloning the project
----------------------------

You first need to download the pulp project from your fork. In the following command replace ``pchtsp`` with your actual username::

    git clone git@github.com:pchtsp/pulp.git

That's it, you will download the whole project.


Installing from source
----------------------------

To build pulp from source we wil get inside the pulp directory, then we will create a virtual environment and install dependencies. I assume Linux / Mac. Windows has very similar commands::

    cd pulp
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install --upgrade pip
    pip install --group=dev --editable .

This will link the pulp version on your virtual environment with the source files in the pulp directory. You can now use pulp from that virtual environment and you will be using the files in the pulp directory. We assume you have run this successfully for all further steps.

Running tests
----------------

To run tests of pulp you need to run::

    python3 pulp/tests/run_tests.py

It will detect the solvers in your system and test all of the ones it finds.

Creating a test
-----------------

When you fix an issue in pulp or add a functionality, you should add a test to the repository. For this you should go to the file `tests/test_pulp.py` and add a new method that tests your change.

Applying the black linter / formatter
-----------------------------------------------------

We use `the black formatter <https://black.readthedocs.io/en/stable/>`_. Before sending your changes, be sure to execute the black package to style the resulting files.
The quickest way to do this is to run::

    python -m black pulp

And it will do the changes directly on the files.

The easiest way is to integrate it inside your IDE so it runs every time you save a file. Learn how to do that `in the black integration docs <https://black.readthedocs.io/en/stable/integrations/editors.html>`_.

Checking types with mypy
-------------------------------------

We use `the mypy type checker <https://mypy.readthedocs.io/en/stable/index.html>`_. Before sending your changes, be sure to execute the mypy package to check the types.
The quickest way to do this is to run::

    python -m mypy ./

Fix all the errors you see before pushing the changes.

Building the documentation
----------------------------

The documentation is based in `Sphinx and reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`_.

To build the documentation::

    cd pulp/doc
    make html

A folder named html will be created inside the ``build/`` directory. The home page for the documentation is ``doc/build/html/index.html`` which can be opened in a browser.
You only need to execute ``make html`` to rebuild the docs each time.

Making a Pull Request
----------------------------

When you're done with the changes in your machine and you're satisfied with the result you have, you can commit it, push it to github and then create a PR.
The first two are easy::

    git status # this shows what's changed
    git add some_modified_file.py # do this for all changes you want to write
    git commit -m "some message" # include a meaningful message
    git push origin

In order to create a PR to the original repository, follow one of github's  `guides <https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request>`_.

