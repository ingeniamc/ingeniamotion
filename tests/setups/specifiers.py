from dataclasses import dataclass
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
    Setup,
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


class RackServiceConfigSpecifier:
    """Generic specifier."""

    def __init__(
        self,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Path,
        dictionary: Union[Path, PromisedFilePath],
        firmware_file: Union[Path, PromisedFilePath],
        rack_service_client: Optional[RackServiceClient] = None,
    ):
        """Initialize the specifier.

        Args:
            part_number: drive part number to test. If multislave, provide a list.
            interface: desired communication interface with the drive.
            config_file: path to configuration file.
            dictionary: path to dictionary.
                If promise is used, it should be resolved once the rack service client is set.
            firmware_file: path to firmware file.
                If promise is used, it should be resolved once the rack service client is set.
            rack_service_client: rack service client.

        Raises:
            RuntimeError: if multiple part numbers are specified and the interface is not Ethercat.
        """
        if isinstance(part_number, list) and interface is not Interface.ETHERCAT:
            raise RuntimeError(
                f"Multiple part numbers can only be provided for {Interface.ETHERCAT}"
            )
        self._part_number: Union[PartNumber, list[PartNumber]] = part_number
        self._interface: Interface = interface
        self._config_file: Path = config_file
        self._dictionary: Union[Path, PromisedFilePath] = dictionary
        self._firmware_file: Union[Path, PromisedFilePath] = firmware_file

        self.__rack_service_client: Optional[RackServiceClient] = None
        if rack_service_client is not None:
            self.rack_service_client = rack_service_client

    @property
    def rack_service_client(self) -> RackServiceClient:
        if self.__rack_service_client is None:
            raise ValueError("Rack service client has not been set yet.")
        return self.__rack_service_client

    @rack_service_client.setter
    def rack_service_client(self, rack_service_client: RackServiceClient) -> None:
        if self.__rack_service_client is not None:
            raise ValueError("Rack service client has already been set.")
        self.__rack_service_client = rack_service_client

    @cached_property
    def dictionary(self) -> Path:
        if isinstance(self._dictionary, str):
            self._dictionary = Path(self._dictionary)
        if isinstance(self._dictionary, Path):
            return self._dictionary

        if self.__rack_service_client is None:
            raise ValueError(
                "Dictionary file has been requested for download, but no rack service "
                "client has been set."
            )

        return self.rack_service_client.get_dictionary(self._dictionary.firmware_version)

    @cached_property
    def firmware_file(self) -> Path:
        if isinstance(self._firmware_file, str):
            self._firmware_file = Path(self._firmware_file)
        if isinstance(self._firmware_file, Path):
            return self._firmware_file

        if self.__rack_service_client is None:
            raise ValueError(
                "Firmware file has been requested for download, but no rack service "
                "client has been set."
            )

        return self.rack_service_client.get_firmware(self._firmware_file.firmware_version)

    @classmethod
    def from_local_firmware(
        cls,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Path,
        firmware_file: Path,
        dictionary_file: Optional[Path] = None,
        dictionary_firmware_version: Optional[str] = None,
        rack_service_client: Optional[RackServiceClient] = None,
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
            rack_service_client: rack service client.

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
            rack_service_client=rack_service_client,
        )

    @classmethod
    def from_frozen_firmware(
        cls,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Path,
        firmware_version: str,
        rack_service_client: Optional[RackServiceClient] = None,
    ) -> "RackServiceConfigSpecifier":
        """Used to specify a setup with frozen ATT firmware.

        Args:
            part_number: drive part number to test. If multislave, provide a list.
            interface: desired communication interface with the drive.
            config_file: path to configuration file.
            firmware_version: firmware version to be tested.
            rack_service_client: rack service client.
                If not specified, dictionary file and firmware file will be set as promises.
                Rack service client should be specified afterwards to resolve them.

        Returns:
            RackServiceConfigSpecifier instance.
        """
        return cls(
            part_number=part_number,
            interface=interface,
            config_file=config_file,
            dictionary=PromisedFilePath(firmware_version),
            firmware_file=PromisedFilePath(firmware_version),
            rack_service_client=rack_service_client,
        )

    def __get_multislave_descriptor(self, rack_service_client: RackServiceClient) -> Setup:
        drives = []
        for part_number in self._part_number:
            _, drive = rack_service_client.get_drive(part_number)
            network = get_network_from_drive(drive=drive, interface=self._interface)
            ecat_drive = DriveEcatSetup(
                identifier=drive.identifier,
                dictionary=self.dictionary,
                config_file=self._config_file,
                fw_file=self.firmware_file,
                ifname=network.ifname,
                slave=network.slave,
                boot_in_app=network.boot_in_app,
            )
            drives.append(ecat_drive)
        return EthercatMultiSlaveSetup(drives=drives)

    def get_descriptor(self, rack_service_client: Optional[RackServiceClient] = None) -> Setup:
        """Returns the setup descriptor that corresponds to the specifier.

        Args:
            rack_service_client: rack service client. Defaults to None.
                If it is not provided, it should have been previously set.

        Returns:
            Descriptor setup.

        Raises:
            RuntimeError: if rack service client is not specified and it has not been set.
            RuntimeError: if no setup descriptor can be retrieved for the part number and interface.
        """
        if rack_service_client is None:
            if self.__rack_service_client is None:
                raise RuntimeError("Rack service client should be set or provided for this feature")
            rack_service_client = self.rack_service_client

        if isinstance(self._part_number, list):
            return self.__get_multislave_descriptor(rack_service_client)

        _, drive = rack_service_client.get_drive(part_number=self._part_number)
        network = get_network_from_drive(drive=drive, interface=self._interface)
        args = {
            "identifier": drive.identifier,
            "fw_file": self.firmware_file,
            "dictionary": self.dictionary,
            "config_file": self._config_file,
        }

        if self._interface is Interface.ETHERNET:
            return DriveEthernetSetup(**args, ip=network.ip)
        elif self._interface is Interface.CANOPEN:
            return DriveCanOpenSetup(
                **args,
                device=network.device,
                channel=network.channel,
                node_id=network.node_id,
                baudrate=network.baudrate,
            )
        elif self._interface is Interface.ETHERCAT:
            return DriveEcatSetup(
                **args, ifname=network.ifname, slave=network.slave, boot_in_app=network.boot_in_app
            )

        raise RuntimeError(
            f"No descriptor for part number {self._part_number}, interface {self._interface}"
        )


@dataclass(frozen=True)
class VirtualDriveSpecifier:
    ip: str
    port: int

    @cached_property
    def dictionary(self) -> Path:
        return Path(VIRTUAL_DRIVE_DICTIONARY)

    def get_descriptor(self) -> VirtualDriveSetup:
        return VirtualDriveSetup(ip=self.ip, dictionary=self.dictionary, port=self.port)
