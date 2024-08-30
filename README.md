Ingeniamotion
=============

![GitHub branch status](https://img.shields.io/github/checks-status/ingeniamc/ingeniamotion/master?label=Tests)
[![PyPi](https://img.shields.io/pypi/v/ingeniamotion.svg)](https://pypi.python.org/pypi/ingeniamotion)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ingeniamotion?color=2334D058)

[![CC by-nc-sa](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-nd/4.0/)

Ingeniamotion is a library that works over ingenialink and aims to simplify the interaction with Ingenia's drives.

[![Ingenia Servodrives](https://github.com/ingeniamc/ingenialink-python/blob/master/docs/_static/images/main_image.png?raw=true)](http://www.ingeniamc.com)

Requirements
------------

* Python 3.9 or higher
* [WinPcap](https://www.winpcap.org/install/) 4.1.3

Installation
------------

The recommended way to install is by using pip, i.e:
```bash
pip install ingeniamotion
```

Build Module
------------

Install tox and run the following:
```bash
pip install "tox>4"
tox -e build
```

Generate documentation
----------------------

To produce the documentation, run the following command:
```bash
tox -e docs
```

Run PyTest
----------

Fill configuration json ``tests/config.json``.

Run tests with target protocol and Python version (eoe, soem or canopen). For example:

```bash
tox -e py39 -- --protocol soem
```