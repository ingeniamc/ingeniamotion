from dataclasses import dataclass


@dataclass
class Setup:
    pass


@dataclass
class EthernetSetup(Setup):
    ip: str


@dataclass
class VirtualDriveSetup(EthernetSetup):
    dictionary: str
    port: int


@dataclass
class DriveHwSetup(Setup):
    dictionary: str
    identifier: str
    config_file: str
    fw_file: str
    load_firmware_with_rack_service: bool


@dataclass
class EoESetup(DriveHwSetup, EthernetSetup):  # TODO Rename to EthernetSetup
    pass


@dataclass
class SoemSetup(DriveHwSetup):  # TODO Rename to EcatSetup
    ifname: str
    slave: int
    eoe_comm: bool
    boot_in_app: bool


@dataclass
class CanOpenSetup(DriveHwSetup):
    device: str
    channel: int
    node_id: int
    baudrate: int


@dataclass
class EthercatMultiSlaveSetup(Setup):
    drives: list[SoemSetup]
