from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tests.setups.rack_service_client import RackServiceClient
from tests.setups.specifiers import Interface, SetupSpecifier, VirtualDriveSpecifier


@dataclass(frozen=True)
class SetupDescriptor:
    """Generic setup"""


@dataclass(frozen=True)
class EthernetSetup(SetupDescriptor):
    """Any setup that uses Ethernet"""

    ip: str


@dataclass(frozen=True)
class VirtualDriveSetup(EthernetSetup):
    """Setup with virtual drive"""

    dictionary: str
    port: int


@dataclass(frozen=True)
class DriveHwSetup(SetupDescriptor):
    """Setup with physical hw drive"""

    dictionary: str
    identifier: str
    config_file: Optional[str]
    fw_file: str
    rack_drive_idx: int
    rack_drive: object


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
    boot_in_app: bool


@dataclass(frozen=True)
class DriveCanOpenSetup(DriveHwSetup):
    """Setup with drive connected with canopen"""

    device: str
    channel: int
    node_id: int
    baudrate: int


@dataclass(frozen=True)
class EthercatMultiSlaveSetup(SetupDescriptor):
    """Setup with multiple drives connected with Ethercat"""

    drives: list[DriveEcatSetup]


def _get_network_from_drive(drive: object, interface: Interface) -> object:
    if interface is Interface.CANOPEN:
        attribute = "node_id"
    elif interface is Interface.ETHERNET:
        attribute = "ip"
    elif interface is Interface.ETHERCAT:
        attribute = "ifname"
    else:
        raise RuntimeError(f"No network associated with {interface=}")

    for node in drive.communications:
        if hasattr(node, attribute):
            return node
    raise RuntimeError(f"No network can be retrieved for {interface=}")


def _get_dictionary_and_firmware_file(
    specifier: SetupSpecifier, rack_service_client: RackServiceClient
) -> tuple[Path, Path]:
    dictionary = (
        specifier.dictionary
        if isinstance(specifier.dictionary, Path)
        else rack_service_client.get_dictionary(specifier.dictionary.firmware_version)
    )
    firmware_file = (
        specifier.firmware_file
        if isinstance(specifier.firmware_file, Path)
        else rack_service_client.get_firmware(specifier.firmware_file.firmware_version)
    )
    return dictionary, firmware_file


def _get_multislave_descriptor(
    specifier: SetupSpecifier, rack_service_client: RackServiceClient
) -> SetupDescriptor:
    drives = []
    for part_number in specifier.part_number:
        rack_drive_idx, rack_drive = rack_service_client.get_drive(part_number)
        network = _get_network_from_drive(drive=rack_drive, interface=specifier.interface)
        dictionary, firmware_file = _get_dictionary_and_firmware_file(
            specifier=specifier, rack_service_client=rack_service_client
        )
        ecat_drive = DriveEcatSetup(
            dictionary=dictionary,
            identifier=rack_drive.identifier,
            config_file=specifier.config_file,
            rack_drive_idx=rack_drive_idx,
            rack_drive=rack_drive,
            fw_file=firmware_file,
            ifname=network.ifname,
            slave=network.slave,
            boot_in_app=network.boot_in_app,
        )
        drives.append(ecat_drive)
    return EthercatMultiSlaveSetup(drives=drives)


def descriptor_from_specifier(
    specifier: SetupSpecifier, rack_service_client: Optional[RackServiceClient]
) -> SetupDescriptor:
    """Returns the setup descriptor that corresponds to an specifier.

    Args:
        specifier: setup specifier.
        rack_service_client: rack service client.
            If the specifier is a virtual drive specifier, should not be provided.

    Returns:
        Descriptor setup.

    Raises:
        RuntimeError: if the specifier is a rack config specifier,
            but no rack service client is provided.
        RuntimeError: if no setup descriptor can be retrieved for the part number and interface.
    """
    if isinstance(specifier, VirtualDriveSpecifier):
        return VirtualDriveSetup(
            ip=specifier.ip, dictionary=specifier.dictionary, port=specifier.port
        )
    if rack_service_client is None:
        raise RuntimeError("Rack service client must be provided for RackServiceConfigSpecifier")
    if specifier.is_multislave:
        return _get_multislave_descriptor(
            specifier=specifier, rack_service_client=rack_service_client
        )

    # Common arguments for DriveHwSetup
    rack_drive_idx, rack_drive = rack_service_client.get_drive(specifier.part_number)
    dictionary, firmware_file = _get_dictionary_and_firmware_file(
        specifier=specifier, rack_service_client=rack_service_client
    )
    args = {
        "dictionary": dictionary,
        "identifier": rack_drive.identifier,
        "config_file": specifier.config_file,
        "fw_file": firmware_file,
        "rack_drive_idx": rack_drive_idx,
        "rack_drive": rack_drive,
    }
    network = _get_network_from_drive(drive=rack_drive, interface=specifier.interface)

    if specifier.interface is Interface.ETHERNET:
        return DriveEthernetSetup(**args, ip=network.ip)
    elif specifier.interface is Interface.CANOPEN:
        return DriveCanOpenSetup(
            **args,
            device=network.device,
            channel=network.channel,
            node_id=network.node_id,
            baudrate=network.baudrate,
        )
    elif specifier.interface is Interface.ETHERCAT:
        return DriveEcatSetup(
            **args, ifname=network.ifname, slave=network.slave, boot_in_app=network.boot_in_app
        )

    raise RuntimeError(
        f"No descriptor for part number {specifier.part_number}, interface {specifier.interface}"
    )
