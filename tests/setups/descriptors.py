from dataclasses import dataclass
from typing import Optional


@dataclass
class Setup:
    """Generic setup"""

    pass


@dataclass
class EthernetSetup(Setup):
    """Any setup that uses Ethernet"""

    ip: str


@dataclass
class VirtualDriveSetup(EthernetSetup):
    """Setup with virtual drive"""

    dictionary: str
    port: int


@dataclass
class DriveHwSetup(Setup):
    """Setup with physical hw drive"""

    dictionary: str
    identifier: str
    config_file: Optional[str]
    fw_file: str
    use_rack_service: bool


@dataclass
class DriveEthernetSetup(DriveHwSetup, EthernetSetup):
    """Setup with drive with Ethernet.

    Can be regular Ethernet or ethernet over Ethercat (EoE)
    """

    pass


@dataclass
class DriveEcatSetup(DriveHwSetup):
    """Setup with drive connected with Ethercat"""

    ifname: str
    slave: int
    eoe_comm: bool
    boot_in_app: bool


@dataclass
class DriveCanOpenSetup(DriveHwSetup):
    """Setup with drive connected with canopen"""

    device: str
    channel: int
    node_id: int
    baudrate: int


@dataclass
class EthercatMultiSlaveSetup(Setup):
    """Setup with multiple drives connected with Ethercat"""

    drives: list[DriveEcatSetup]
