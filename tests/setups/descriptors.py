import functools
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Setup:
    """Generic setup"""


@dataclass(frozen=True)
class EthernetSetup(Setup):
    """Any setup that uses Ethernet"""

    ip: str


@dataclass(frozen=True)
class VirtualDriveSetup(EthernetSetup):
    """Setup with virtual drive"""

    dictionary: str
    port: int


@dataclass(frozen=True)
class DriveHwSetup(Setup):
    """Setup with physical hw drive"""

    dictionary: str
    identifier: str
    config_file: Optional[str]
    fw_file: str
    use_rack_service: bool

    @functools.lru_cache
    def get_rack_drive(self, rack_service_client):
        config = rack_service_client.exposed_get_configuration()
        for idx, drive in enumerate(config.drives):
            if self.identifier == drive.identifier:
                return idx, drive

        raise ValueError(
            f"The drive {self.identifier} cannot be found on the rack's configuration."
        )


@dataclass(frozen=True)
class DriveEthernetSetup(DriveHwSetup, EthernetSetup):
    """Setup with drive with Ethernet.

    Can be regular Ethernet or ethernet over Ethercat (EoE)
    """


@dataclass(frozen=True)
class DriveEcatSetup(DriveHwSetup):
    """Setup with drive connected with Ethercat"""

    ifname: str
    slave: int
    eoe_comm: bool
    boot_in_app: bool


@dataclass(frozen=True)
class DriveCanOpenSetup(DriveHwSetup):
    """Setup with drive connected with canopen"""

    device: str
    channel: int
    node_id: int
    baudrate: int


@dataclass(frozen=True)
class EthercatMultiSlaveSetup(Setup):
    """Setup with multiple drives connected with Ethercat"""

    drives: list[DriveEcatSetup]
