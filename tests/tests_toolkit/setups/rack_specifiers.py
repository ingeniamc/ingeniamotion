from pathlib import Path

from ingenialink.dictionary import Interface

from tests.tests_toolkit.setups.specifiers import (
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
)

ETH_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.ETH,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware_version="2.4.0",
)

ETH_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.ETH,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware_version="2.4.0",
)

ECAT_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_E,
    interface=Interface.ECAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml"),
    firmware_version="2.6.0",
)

ECAT_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_E,
    interface=Interface.ECAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml"),
    firmware_version="2.6.0",
)

CAN_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.CAN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware_version="2.4.0",
)

CAN_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.CAN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware_version="2.4.0",
)

ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier(
    specifiers=[ECAT_EVE_SETUP, ECAT_CAP_SETUP],
)
