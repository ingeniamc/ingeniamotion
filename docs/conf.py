# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from packaging.version import Version

sys.path.insert(0, os.path.abspath('..'))

from ingenialink import __version__ as ingenialink_version
from ingeniamotion import __version__ as ingeniamotion_version

python_version = "3.12"

# Extract base version (major.minor.patch) without post/dev/local parts
ingenialink_base_version = str(Version(ingenialink_version).base_version)

# -- Project information -----------------------------------------------------

project = 'ingeniamotion'
copyright = '2021, Novanta Technologies Spain S.L.'
author = 'Novanta'
version = ingeniamotion_version

# The full version, including alpha/beta/rc tags
release = version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',
    'sphinx.ext.intersphinx',
    'm2r2'
]

autodoc_default_options = {
    'members': True,
    "undoc-members": True,
    'show-inheritance': True,
}

autodoc_member_order = 'bysource'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

pdf_name = u"ingeniamotion v{}".format(ingeniamotion_version)
pdf_documents = [('index', pdf_name, u'Ingeniamotion', author), ]

intersphinx_mapping = {
    'python': (f"https://docs.python.org/{python_version}", None),
    'ingenialink': (f"https://distext.ingeniamc.com/doc/ingenialink-python/{ingenialink_base_version}", None)
}

napoleon_use_param = True