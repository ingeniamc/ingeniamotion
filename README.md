Ingeniamotion
=============

[![PyPi](https://img.shields.io/pypi/v/ingeniamotion.svg)](https://pypi.python.org/pypi/ingeniamotion)
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

Create tests/setups/tests_setup.py file with configuration file 
Example of a setup:

```python
from .descriptors import SoemSetup

TESTS_SETUP = SoemSetup(
    dictionary="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_eoe_2.5.1.xdf",
    identifier="eve-xcr-e",
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_2.5.1.sfu",
    ifname="\\Device\\NPF_{B24AA996-414A-4F95-95E6-2828D346209A}",
    slave=1,
    eoe_comm=True,
    boot_in_app=True,
    load_firmware_with_rack_service=True,
)
```

Run tests with target protocol and Python version (eoe, soem or canopen). For example:

```bash
tox -e py39 -- --protocol soem
```