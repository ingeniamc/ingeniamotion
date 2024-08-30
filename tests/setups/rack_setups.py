from .descriptors import (
    DriveCanOpenSetup,
    DriveEthernetSetup,
    EthercatMultiSlaveSetup,
    DriveEcatSetup,
)

ETH_EVE_SETUP = DriveEthernetSetup(
    dictionary="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_eth_2.4.0.xdf",
    ip="192.168.2.10",
    identifier="eve-xcr-c",
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_2.4.0.sfu",
    use_rack_service=True,
)

ETH_CAP_SETUP = DriveEthernetSetup(
    dictionary="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_eth_2.4.0.xdf",
    ip="192.168.2.11",
    identifier="cap-xcr-c",
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_2.4.0.lfu",
    use_rack_service=True,
)

ECAT_EVE_SETUP = DriveEcatSetup(
    dictionary="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_eoe_2.5.1.xdf",
    identifier="eve-xcr-e",
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_2.5.1.sfu",
    ifname="\\Device\\NPF_{B24AA996-414A-4F95-95E6-2828D346209A}",
    slave=1,
    eoe_comm=True,
    boot_in_app=True,
    use_rack_service=True,
)

ECAT_CAP_SETUP = DriveEcatSetup(
    dictionary="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.5.1/cap-xcr-e_eoe_2.5.1.xdf",
    identifier="cap-xcr-e",
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.5.1/cap-xcr-e_2.5.1.lfu",
    ifname="\\Device\\NPF_{B24AA996-414A-4F95-95E6-2828D346209A}",
    slave=2,
    eoe_comm=True,
    boot_in_app=False,
    use_rack_service=True,
)

CAN_EVE_SETUP = DriveCanOpenSetup(
    dictionary="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_can_2.4.0.xdf",
    identifier="eve-xcr-c",
    config_file="//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.4.0/eve-xcr-c_2.4.0.sfu",
    device="pcan",
    channel=0,
    node_id=20,
    baudrate=1000000,
    use_rack_service=True,
)

CAN_CAP_SETUP = DriveCanOpenSetup(
    dictionary="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_can_2.4.0.xdf",
    identifier="cap-xcr-c",
    config_file="//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml",
    fw_file="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_2.4.0.lfu",
    device="pcan",
    channel=0,
    node_id=21,
    baudrate=1000000,
    use_rack_service=True,
)

ECAT_MULTISLAVE_SETUP = EthercatMultiSlaveSetup([ECAT_EVE_SETUP, CAN_EVE_SETUP])
