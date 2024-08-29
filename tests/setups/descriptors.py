from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Setup:
    dictionary: str

    @classmethod
    def from_dict(cls, protocol_name: str, contents: Dict):
        if protocol_name == "eoe":
            return EoESetup(**contents, load_firmware_with_rack_service=False)
        if protocol_name == "soem":
            return SoemSetup(**contents, load_firmware_with_rack_service=False)
        if protocol_name == "canopen":
            return CanOpenSetup(**contents, load_firmware_with_rack_service=False)
        if protocol_name == "virtual":
            return VirtualDriveSetup(**contents)
        else:
            raise NotImplementedError


@dataclass
class EthernetSetup(Setup):
    ip: str


@dataclass
class VirtualDriveSetup(EthernetSetup):
    port: int


@dataclass
class HwSetup(Setup):
    identifier: str
    config_file: str
    fw_file: str
    load_firmware_with_rack_service: bool


@dataclass
class EoESetup(HwSetup, EthernetSetup):
    pass


@dataclass
class SoemSetup(HwSetup):
    ifname: str
    slave: int
    eoe_comm: bool
    boot_in_app: bool


@dataclass
class CanOpenSetup(HwSetup):
    device: str
    channel: int
    node_id: int
    baudrate: int


@dataclass
class Protocol:
    name: str
    setups: List[Setup]

    @classmethod
    def from_dict(cls, name, contents: Dict):
        return cls(name, [Setup.from_dict(name, setup) for setup in contents])


@dataclass
class Configs:
    protocols: Dict[str, Protocol]

    @classmethod
    def from_dict(cls, contents: Dict):
        return cls(
            {name: Protocol.from_dict(name, protocol) for name, protocol in contents.items()}
        )
