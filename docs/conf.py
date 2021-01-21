import sys
import re
from os.path import abspath, join, dirname
from datetime import datetime

sys.path.append(abspath(join(dirname(__file__), '..')))

# version
with open(join('..', 'ingeniamotion', '__init__.py')) as f:
    _version = re.search(r'__version__\s+=\s+\'(.*)\'', f.read()).group(1)

# extensions
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon',
              'sphinx.ext.mathjax', 'sphinx.ext.viewcode',
              'sphinx.ext.intersphinx', 'sphinxcontrib.bibtex',
              'matplotlib.sphinxext.plot_directive', 'nbsphinx']

bibtex_bibfiles = ['bibliography.bib']

# general
project = 'ingeniamotion'
version = _version
author = 'Ingenia Motion Control'
year = datetime.now().year
copyright = '%d, Ingenia Motion Control' % year
source_suffix = ['.rst', '.ipynb']
master_doc = 'index'

# html
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'
html_logo = '_static/images/logo.svg'
html_theme_options = {
    'logo_only': True,
    'display_version': False,
}

def setup(app):
    app.add_stylesheet('css/custom.css')

# others
pygments_style = 'sphinx'
autodoc_mock_imports = ['ingenialink', 'numpy']
exclude_patterns = ['_build', '**.ipynb_checkpoints']

# extensions
mathjax_path = 'js/MathJax/MathJax.js?config=TeX-AMS_CHTML,local/local'

intersphinx_mapping = {
        'numpy': ('https://docs.scipy.org/doc/numpy/', None),
        'scipy': ('https://docs.scipy.org/doc/scipy/reference', None)}
