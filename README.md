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

Create *tests/setups/tests_setup.py* file with configuration file.

This file is ignored by git and won't be uploaded to the repository.
Example of a setup:

```python
from pathlib import Path

from summit_testing_framework.setups import LocalDriveConfigSpecifier

DEN_NET_E_SETUP = LocalDriveConfigSpecifier.from_ethercat_configuration(
    identifier="den-net-e",
    dictionary=Path("C://Users//some.user//Downloads//den-net-e_eoe_2.7.3.xdf"),
    config_file=Path("C://Users//some.user//Downloads//den_net_e.xcf"),
    firmware_file=Path("C://Users//some.user//Downloads//den-net-e_2.7.3.lfu"),
    ifname="\\Device\\NPF_{675921D7-B64A-4997-9211-D18E2A6DC96A}",
    slave=1,
    boot_in_app=False,
)
```

For more information, check `summit-testing-framework` documentation.

Run tests selecting the markers that you want and are appropriate for your setup.
Beware that some tests may not be appropiate for the setup that you have and may fail.

```bash
tox -e py39 -- -m soem
```

This will use the default *ingenialink* installation from *[develop]* setting. If you want to send a custom wheel or a different commit, you can do it by changing *INGENIALINK_INSTALL_PATH* variable.

For example, to send a custom wheel:

```python
INGENIALINK_INSTALL_PATH=dist/ingenialink-7.4.1-cp39-cp39-win_amd64.whl tox -e py39
```