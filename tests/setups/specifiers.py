from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property
from pathlib import Path
from typing import Optional, Union

from ingenialink.ethernet.network import VIRTUAL_DRIVE_DICTIONARY

from tests.setups.rack_service_client import PartNumber


class Interface(Enum):
    CANOPEN = auto()
    ETHERNET = auto()
    ETHERCAT = auto()


class PromisedFilePath:
    def __init__(self, firmware_version: str):
        self.firmware_version = firmware_version


@dataclass(frozen=True)
class SetupSpecifier:
    """Generic setup specifier."""


@dataclass(frozen=True)
class VirtualDriveSpecifier(SetupSpecifier):
    ip: str
    port: int

    @cached_property
    def dictionary(self) -> Path:
        return Path(VIRTUAL_DRIVE_DICTIONARY)


@dataclass(frozen=True)
class DriveHwConfigSpecifier(SetupSpecifier):
    """Configuration of a physical hardware drive."""

    part_number: Union[PartNumber, list[PartNumber]]
    """Drive part number to test. If multislave, provide a list."""
    interface: Interface
    """Desired communication interface with the drive."""
    config_file: Optional[Path]
    """Path to configuration file."""


@dataclass
class MultiDriveConfigSpecifier(SetupSpecifier):
    """General multidrive configuration specifier."""

    specifiers: list[DriveHwConfigSpecifier]

    def __post_init__(self):
        for specifier in self.specifiers:
            if specifier.interface is not Interface.ETHERCAT:
                raise RuntimeError(
                    f"Multiple part numbers can only be provided for {Interface.ETHERCAT}"
                )


@dataclass(frozen=True)
class LocalDriveConfigSpecifier(DriveHwConfigSpecifier):
    """Local drive configuration specifier."""

    dictionary: Path
    """Path to dictionary."""
    firmware_file: Path
    """Path to firmware file"""
    revision_number: Optional[int] = None
    """Revision number of the local drive."""
    firmware_version: Optional[str] = None
    """Firmware version of the local drive."""
    serial_number: Optional[str] = None
    """Serial number of the local drive."""


@dataclass(frozen=True)
class MultiLocalDriveConfigSpecifier(MultiDriveConfigSpecifier):
    """Local configuration specifier with multiple drives connected."""

    specifiers: list[LocalDriveConfigSpecifier]


@dataclass(frozen=True)
class RackServiceConfigSpecifier(DriveHwConfigSpecifier):
    """Rack service drive configuration specifier."""

    dictionary: Union[Path, PromisedFilePath]
    """Path to dictionary. If promise is used, the specified firmware version
    should be used to retrieve it with rack service client.
    """
    firmware_file: Union[Path, PromisedFilePath]
    """Path to firmware file. If promise is used, the specified firmware version
    should be used to retrieve it with rack service client.
    """

    @classmethod
    def from_local_firmware(
        cls,
        part_number: Union[PartNumber, list[PartNumber]],
        interface: Interface,
        config_file: Optional[Path],
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
        config_file: Optional[Path],
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


@dataclass(frozen=True)
class MultiRackServiceConfigSpecifier(MultiDriveConfigSpecifier):
    """Rack service configuration specifier with multiple drives connected."""

    specifiers: list[RackServiceConfigSpecifier]
