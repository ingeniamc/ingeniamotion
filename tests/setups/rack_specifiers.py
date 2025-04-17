from tests.setups.specifiers import Interface, PartNumber, RackServiceConfigSpecifier

# TODO: INGM-541 use from_frozen_firmware(firmware_version=2.4.0)
ETH_EVE_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.ETHERNET,
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_eth_2.4.0.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_2.4.0.sfu",
)

# TODO: INGM-541 use from_frozen_firmware(firmware_version=2.4.0)
ETH_CAP_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.ETHERNET,
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_eth_2.4.0.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_2.4.0.lfu",
)

# TODO: INGM-541 use from_frozen_firmware(firmware_version=2.5.1)
ECAT_EVE_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.EVE_XCR_E,
    interface=Interface.ETHERCAT,
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_eoe_2.5.1.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_2.5.1.sfu",
)

# TODO: INGM-541 use from_frozen_firmware (firmware_version=2.5.1)
ECAT_CAP_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.CAP_XCR_E,
    interface=Interface.ETHERCAT,
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.5.1/cap-xcr-e_eoe_2.5.1.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.5.1/cap-xcr-e_2.5.1.lfu",
)

# TODO: INGM-541 use from_frozen_firmware (firmware_version=2.4.0)
CAN_EVE_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.CANOPEN,
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_can_2.4.0.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_2.4.0.sfu",
)

# TODO: INGM-541 use from_frozen_firmware (firmware_version=2.4.0)
CAN_CAP_SETUP = RackServiceConfigSpecifier.from_local_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.CANOPEN,
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml",
    dictionary_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_can_2.4.0.xdf",
    firmware_file="//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_2.4.0.lfu",
)
