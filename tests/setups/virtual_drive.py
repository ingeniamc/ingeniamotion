from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

from tests.dictionaries import VIRTUAL_DRIVE_XDF_PATH

VIRTUAL_DRIVE_ETHERNET_SETUP = VirtualDriveSpecifier.from_ethernet(
    dictionary=VIRTUAL_DRIVE_XDF_PATH, extra_data={"execution_policy": "always"}
)
