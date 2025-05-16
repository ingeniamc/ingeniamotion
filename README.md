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
from .descriptors import DriveEcatSetup

TESTS_SETUP = DriveEcatSetup(
    dictionary="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_eoe_2.5.1.xdf",
    identifier="eve-xcr-e",
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_2.5.1.sfu",
    ifname="\\Device\\NPF_{B24AA996-414A-4F95-95E6-2828D346209A}",
    slave=1,
    eoe_comm=True,
    boot_in_app=True,
    load_firmware_with_rack_service=False,
)
```

To obtain *ifname* setting, can run the following:

```python
from ingeniamotion.communication import Communication

def main() -> None:
    network_adapters = Communication.get_network_adapters()
    for adapter_name, adapter_guid in network_adapters.items():
        print(f"{adapter_name}: {adapter_guid}")

if __name__ == "__main__":
    main()
```

This will print a list of adapters, select the one that you are currently using (check your network settings).

Run tests selecting the markers that you want and are appropriate for your setup.
Beware that some tests may not be appropiate for the setup that you have and may fail.

```bash
tox -e py39 -- -m soem
```

This will use the default *ingenialink* installation from *[develop]* setting. If you want to send a custom wheel or a different commit, you can do it by changing *INGENIALINK_INSTALL_PATH* variable.

For example, to send a custom wheel:

```bash
INGENIALINK_INSTALL_PATH=dist/ingenialink-7.4.1-cp39-cp39-win_amd64.whl tox -e py39
```

To install *FSoE*, do the same with *FSOE_PACKAGE*:

```bash
FSOE_PACKAGE=".[FSoE]" tox -e py39
```
