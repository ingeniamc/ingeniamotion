import re
import setuptools


with open("docs/what_is_ingeniamotion.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('ingeniamotion/__init__.py') as f:
    __version = re.search(r"__version__\s+=\s+'(.*)'", f.read()).group(1)


def get_docs_url():
    return "https://distext.ingeniamc.com/doc/ingeniamotion/{}".format(__version)


setuptools.setup(
    name="ingeniamotion",
    version=__version,
    packages=setuptools.find_packages(),
    author="Ingenia Motion Control",
    author_email="support@ingeniamc.com",
    description="Motion library for Ingenia servo drives",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url='https://www.ingeniamc.com',
    project_urls={
                "Documentation": get_docs_url(),
                'Source': 'https://github.com/ingeniamc/ingeniamotion'
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'ingenialink>=6.4.1',
        'ingenialogger==0.2.1',
        'ifaddr==0.1.7'
    ],
    extras_require={
        "tests": [
            "pytest==7.0.1",
            "pytest-cov==2.12.1",
            "pytest-mock==3.6.1",
            "ping3==3.0.2",
            "pytest-html==3.1.1",
        ],
        "dev": [
            "sphinx==3.5.4",
            "sphinx-rtd-theme==1.0.0",
            "sphinxcontrib-bibtex==2.4.1",
            "matplotlib==3.3.4",
            "nbsphinx==0.8.7",
            "rst2pdf==0.98",
            "wheel==0.37.1",
            "m2r2==0.3.2"
        ],
    },
    python_requires='>=3.6',
)
