Ingeniamotion
=============

[![PyPi](https://img.shields.io/pypi/v/ingeniamotion.svg)](https://pypi.python.org/pypi/ingeniamotion)
[![CC by-nc-sa](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](http://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)

Ingeniamotion is a library that works over ingenialink and aims to simplify the interaction with Ingenia's drives.

[![Ingenia Servodrives](https://ingeniamc.com/wp-content/uploads/2021/04/ingenia-servo-drives.jpg)](http://www.ingeniamc.com)

Requirements
------------

* Python 3.6
* [WinPcap](https://www.winpcap.org/install/) 4.1.3

Build Module
------------

Install locally:
```bash
python setup.py build_ext -i
python setup.py install
```

Generate .whl file:
```bash
python setup.py build_ext -i
python setup.py bdist_wheel
```

Generate documentation
----------------------

For develop the documentation it's recommended uninstall the ingeniamotion in the pipenv
and remove all the .pyd files. Now we can ensure sphinx will get the data from the source.

### Build HTML documentation

It's recommended remove first the _docs folder.

```bash
sphinx-build -b html docs _docs
```

### Build PDF documentation

It's recommended remove first the _pdf folder.

```bash
sphinx-build -b pdf docs _pdf
```

Run PyTest
----------

Fill configuration json ``tests/config.json``.

Run tests with target protocol (eoe, soem or canopen). For example:

``pytest --protocol soem``
