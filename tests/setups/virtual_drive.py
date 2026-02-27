from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

VIRTUAL_DRIVE_ETHERNET_SETUP = VirtualDriveSpecifier.from_ethernet(
    extra_data={"execution_policy": "always"}
)
