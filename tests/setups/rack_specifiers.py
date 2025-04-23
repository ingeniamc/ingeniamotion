from pathlib import Path

from tests.setups.specifiers import (
    Interface,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
)

ETH_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.ETHERNET,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware_version="2.4.0",
)

ETH_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.ETHERNET,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware_version="2.4.0",
)

ECAT_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_E,
    interface=Interface.ETHERCAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml"),
    firmware_version="2.5.1",
)

ECAT_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_E,
    interface=Interface.ETHERCAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml"),
    firmware_version="2.5.1",
)

CAN_EVE_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.CANOPEN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware_version="2.4.0",
)

CAN_CAP_SETUP = RackServiceConfigSpecifier.from_frozen_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.CANOPEN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware_version="2.4.0",
)

ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier(
    specifiers=[ECAT_EVE_SETUP, ECAT_CAP_SETUP],
)
