"""setuptools based setup script for Biopython.

This uses setuptools which is now the standard python mechanism for
installing packages. If you have downloaded and uncompressed the
Biopython source code, or fetched it from git, for the simplest
installation just type the command::

    python -m pip install

However, you would normally install the latest Biopython release from
the PyPI archive with::

    pip install biopython

For more in-depth instructions, see the installation section of the
Biopython manual, linked to from:

http://biopython.org/wiki/Documentation

Or, if all else fails, feel free to write to the sign up to the Biopython
mailing list and ask for help.  See:

http://biopython.org/wiki/Mailing_lists
"""

import ast
import os
import sys

try:
    from setuptools import Command
    from setuptools import setup
except ImportError:
    sys.exit(
        "We need the Python library setuptools to be installed. "
        "Try running: python -m ensurepip"
    )


class test_biopython(Command):
    """Run all of the tests for the package.

    This is a automatic test run class to make distutils kind of act like
    perl. With this you can do:

    python -m build
    python -m pip install
    python setup.py test

    """

    description = "Automatically run the test suite for Biopython."
    user_options = [("offline", None, "Don't run online tests")]

    def initialize_options(self):
        """No-op, initialise options."""
        self.offline = None

    def finalize_options(self):
        """No-op, finalise options."""
        pass

    def run(self):
        """Run the tests."""
        this_dir = os.getcwd()

        # change to the test dir and run the tests
        os.chdir("Tests")
        sys.path.insert(0, "")
        import run_tests

        if self.offline:
            run_tests.main(["--offline"])
        else:
            run_tests.main([])

        # change back to the current directory
        os.chdir(this_dir)


def get_version():
    """Get version number from __init__.py."""
    for line in open("Bio/__init__.py"):
        if line.startswith("__version__ = "):
            return ast.literal_eval(line.split("=")[1].strip())
    return "Undefined"


__version__ = get_version()

setup(
    version=__version__,
)
