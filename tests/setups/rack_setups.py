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
    dictionary="C://Program Files (x86)//MotionLab3//_internal//resources//dictionaries//cap-net-c_eth_2.5.0.xdf",
    ip="192.168.2.22",
    identifier="cap-xcr-c",
    # config_file="C://Users//martin.acosta//OneDrive - Novanta//Documents//issues//MOT3-4469//cap_net_c_eth_conf.xcf",
    config_file=None,
    fw_file="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.4.0/cap-xcr-c_2.4.0.lfu",
    use_rack_service=False,
)

ECAT_EVE_SETUP = DriveEcatSetup(
    dictionary="C://Program Files (x86)//MotionLab3//_internal//resources//dictionaries//eve-net-e_eoe_2.5.0.xdf",
    identifier="eve-xcr-e",
    config_file="C://Users//martin.acosta//OneDrive - Novanta//Documents//issues//eve-net-e_conf_2.xcf",
    fw_file="//awe-srv-max-prd/distext/products/EVE-XCR/firmware/2.5.1/eve-xcr-e_2.5.1.sfu",
    ifname="\\Device\\NPF_{51BCF26D-647F-489D-A782-D69CBCB20BD2}",
    slave=1,
    eoe_comm=True,
    boot_in_app=True,
    use_rack_service=False,
)

ECAT_CAP_SETUP = DriveEcatSetup(
    dictionary="C://Program Files (x86)//MotionLab3//_internal//resources//dictionaries//cap-net-e_eoe_2.5.1.xdf",
    identifier="cap-xcr-e",
    config_file="C://Users//martin.acosta//OneDrive - Novanta//Documents//issues//INGM-376//cap-net-e_conf.xcf",
    fw_file="//awe-srv-max-prd/distext/products/CAP-XCR/firmware/2.5.1/cap-xcr-e_2.5.1.lfu",
    ifname="\\Device\\NPF_{51BCF26D-647F-489D-A782-D69CBCB20BD2}",
    slave=1,
    eoe_comm=True,
    boot_in_app=False,
    use_rack_service=False,
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
    dictionary="C://Program Files (x86)//MotionLab3//_internal//resources//dictionaries//cap-net-c_can_2.5.1.xdf",
    identifier="cap-xcr-c",
    config_file="C://Users//martin.acosta//OneDrive - Novanta//Documents//issues//INGM-376//cap-net-c_conf.xcf",
    fw_file="C://Users//martin.acosta//Downloads//cap-net-c_2.5.0.lfu",
    device="pcan",
    channel=0,
    node_id=32,
    baudrate=1000000,
    use_rack_service=True,
)

ECAT_MULTISLAVE_SETUP = EthercatMultiSlaveSetup([ECAT_EVE_SETUP, ECAT_CAP_SETUP])
