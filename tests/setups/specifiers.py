from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from pathlib import Path
from typing import Optional, Union

from ingenialink.ethernet.network import VIRTUAL_DRIVE_DICTIONARY

from tests.setups.descriptors import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    EthercatMultiSlaveSetup,
    SetupDescriptor,
    VirtualDriveSetup,
)
from tests.setups.rack_service_client import PartNumber, RackServiceClient


class Interface(Enum):
    CANOPEN = auto()
    ETHERNET = auto()
    ETHERCAT = auto()


class PromisedFilePath:
    def __init__(self, firmware_version: str):
        self.firmware_version = firmware_version


def get_network_from_drive(drive: object, interface: Interface) -> object:
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


def is_rack_service_client_set(func):
    def wrapper(self, *args, **kwargs):
        if getattr(self.__class__, "__rack_service_client") is None:
            raise RuntimeError("Rack service client should be set for this feature")
        return func(self, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class SetupSpecifier:
    """Generic setup specifier."""


@dataclass(frozen=True)
class RackServiceConfigSpecifier(SetupSpecifier):
    """Generic specifier."""

    part_number: Union[PartNumber, list[PartNumber]]
    """Drive part number to test. If multislave, provide a list."""
    interface: Interface
    """Desired communication interface with the drive."""
    config_file: Path
    """Path to configuration file."""
    dictionary: Union[Path, str, PromisedFilePath]
    """Path to dictionary.
    If promise is used, it should be resolved once the rack service client is set.
    """
    firmware_file: Union[Path, str, PromisedFilePath]
    """Path to firmware file.
    If promise is used, it should be resolved once the rack service client is set.
    """
    __rack_service_client: Optional[RackServiceClient] = field(default=None, init=False)
    """Rack service client, should be set with `set_rack_service_client`."""

    def __post_init__(self):
        if self.is_multislave and self.interface is not Interface.ETHERCAT:
            raise RuntimeError(
                f"Multiple part numbers can only be provided for {Interface.ETHERCAT}"
            )

    @cached_property
    def is_multislave(self) -> bool:
        return isinstance(self.part_number, list)

    @property
    def rack_service_client(self) -> RackServiceClient:
        if self.__rack_service_client is None:
            raise ValueError("Rack service client has not been set yet.")
        return self.__rack_service_client

    def set_rack_service_client(self, rack_service_client: RackServiceClient) -> None:
        if self.__rack_service_client is not None:
            raise ValueError("Rack service client has already been set.")
        object.__setattr__(self, "__rack_service_client", rack_service_client)

    @cached_property
    def resolved_dictionary(self) -> Path:
        if not isinstance(self.dictionary, PromisedFilePath):
            if isinstance(self.dictionary, str):
                return Path(self.dictionary)
            return self.dictionary

        if self.__rack_service_client is None:
            raise ValueError(
                "Dictionary file has been requested for download, but no rack service "
                "client has been set."
            )
        return self.rack_service_client.getdictionary(self.dictionary.firmware_version)

    @cached_property
    def resolved_firmware_file(self) -> Path:
        if not isinstance(self.firmware_file, PromisedFilePath):
            if isinstance(self.firmware_file, str):
                return Path(self.firmware_file)
            return self.firmware_file

        if self.__rack_service_client is None:
            raise ValueError(
                "Firmware file has been requested for download, but no rack service "
                "client has been set."
            )
        return self.rack_service_client.get_firmware(self.firmware_file.firmware_version)

    @classmethod
    def from_local_firmware(
        cls,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Path,
        firmware_file: Path,
        dictionary_file: Optional[Path] = None,
        dictionary_firmware_version: Optional[str] = None,
    ) -> "RackServiceConfigSpecifier":
        """Used to specify a setup where a local firmware file will be loaded.

        Args:
            part_number: drive part number to test. If multislave, provide a list.
            interface: desired communication interface with the drive.
            config_file: path to configuration file.
            firmware_file: path to local firmware file.
            dictionary_file: path to dictionary.
                If not specified, `dictionary_firmware_version` must be provided.
            dictionary_firmware_version: firmware version of the dictionary to be retrieved.
                If `dictionary_file` is specified, this attribute can be None.

        Returns:
            RackServiceConfigSpecifier instance.

        Raises:
            RuntimeError: if dictionary file and dictionary firmware version are not provided.
            RuntimeError: if dictionary file and rack service client are not provided.
        """
        if dictionary_file is None:
            if dictionary_firmware_version is None:
                raise RuntimeError(
                    "Dictionary file or dictionary firmware version to download must be provided"
                )
            dictionary = PromisedFilePath(dictionary_firmware_version)
        else:
            dictionary = dictionary_file

        return cls(
            part_number=part_number,
            interface=interface,
            config_file=config_file,
            dictionary=dictionary,
            firmware_file=firmware_file,
        )

    @classmethod
    def from_frozen_firmware(
        cls,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Path,
        firmware_version: str,
    ) -> "RackServiceConfigSpecifier":
        """Used to specify a setup with frozen ATT firmware.

        Args:
            part_number: drive part number to test. If multislave, provide a list.
            interface: desired communication interface with the drive.
            config_file: path to configuration file.
            firmware_version: firmware version to be tested.

        Returns:
            RackServiceConfigSpecifier instance.
        """
        return cls(
            part_number=part_number,
            interface=interface,
            config_file=config_file,
            dictionary=PromisedFilePath(firmware_version),
            firmware_file=PromisedFilePath(firmware_version),
        )

    @cached_property
    @is_rack_service_client_set
    def rack_drive(self) -> Union[list[tuple[int, object]], tuple[int, object]]:
        if self.is_multislave:
            return [
                self.rack_service_client.get_drive(part_number) for part_number in self.part_number
            ]
        return self.rack_service_client.get_drive(self.part_number)

    @is_rack_service_client_set
    def __get_multislave_descriptor(self) -> SetupDescriptor:
        drives = []
        for _, drive in self.rack_drive:
            network = get_network_from_drive(drive=drive, interface=self.interface)
            ecat_drive = DriveEcatSetup(
                identifier=drive.identifier,
                dictionary=self.resolved_dictionary,
                config_file=self.config_file,
                fw_file=self.resolved_firmware_file,
                ifname=network.ifname,
                slave=network.slave,
                boot_in_app=network.boot_in_app,
            )
            drives.append(ecat_drive)
        return EthercatMultiSlaveSetup(drives=drives)

    @cached_property
    @is_rack_service_client_set
    def descriptor(self) -> SetupDescriptor:
        """Returns the setup descriptor that corresponds to the specifier.

        Returns:
            Descriptor setup.

        Raises:
            RuntimeError: if no setup descriptor can be retrieved for the part number and interface.
        """
        if self.is_multislave:
            return self.__get_multislave_descriptor()

        _, drive = self.rack_drive
        network = get_network_from_drive(drive=drive, interface=self.interface)
        args = {
            "identifier": drive.identifier,
            "fw_file": self.resolved_firmware_file,
            "dictionary": self.resolved_dictionary,
            "config_file": self.config_file,
        }

        if self.interface is Interface.ETHERNET:
            return DriveEthernetSetup(**args, ip=network.ip)
        elif self.interface is Interface.CANOPEN:
            return DriveCanOpenSetup(
                **args,
                device=network.device,
                channel=network.channel,
                node_id=network.node_id,
                baudrate=network.baudrate,
            )
        elif self.interface is Interface.ETHERCAT:
            return DriveEcatSetup(
                **args, ifname=network.ifname, slave=network.slave, boot_in_app=network.boot_in_app
            )

        raise RuntimeError(
            f"No descriptor for part number {self.part_number}, interface {self.interface}"
        )


@dataclass(frozen=True)
class VirtualDriveSpecifier(SetupSpecifier):
    ip: str
    port: int

    @cached_property
    def dictionary(self) -> Path:
        return Path(VIRTUAL_DRIVE_DICTIONARY)

    @cached_property
    def descriptor(self) -> SetupDescriptor:
        return VirtualDriveSetup(ip=self.ip, dictionary=self.dictionary, port=self.port)
