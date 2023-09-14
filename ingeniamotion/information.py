import os
from typing import TYPE_CHECKING, Tuple, Union, Optional
import xml.etree.ElementTree as ET

from ingenialink import Servo
from ingenialink.eoe.network import EoENetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.exceptions import ILError
from ingenialink.register import Register, REG_ACCESS, REG_DTYPE
import ingenialogger

from .exceptions import IMRegisterNotExist, IMException
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

logger = ingenialogger.get_logger(__name__)

class Information(metaclass=MCMetaClass):
    """Information."""

    def __init__(self, motion_controller: "MotionController"):
        self.mc = motion_controller

    def register_info(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> Register:
        """Return register object.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register object.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        drive = self.mc.servos[servo]
        try:
            return drive.dictionary.registers(axis)[register]
        except KeyError:
            raise IMRegisterNotExist(
                "Register: {} axis: {} not exist in dictionary".format(register, axis)
            )

    def register_type(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> REG_DTYPE:
        """Return register dtype.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register dtype.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.dtype

    def register_access(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> REG_ACCESS:
        """Return register access.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register access.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.access

    def register_range(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> Tuple[int, int]:
        """Return register range.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register range, minimum and maximum.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.range

    def register_exists(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> bool:
        """Check if register exists in dictionary.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            ``True`` if register exists, else ``False``.

        """
        drive = self.mc.servos[servo]
        return register in drive.dictionary.registers(axis)
    
    def get_product_name(self, alias: str = DEFAULT_SERVO) -> str:
        """Get the product name of the drive.

        Args:
            alias: alias of the servo.
        Returns:
            If it exists for example: "EVE-NET-E", "CAP-NET-E", etc.
        """
        drive = self.mc.servos[alias]
        product_name = drive.dictionary.part_number
        return f"{product_name}"

    def get_target(self, alias: str = DEFAULT_SERVO) -> Union[int, str]:
        """Get the target of the drive.

        Args:
            alias: alias of the servo.

        Returns:
            The target.
        """
        drive = self.mc.servos[alias]
        net = self.mc._get_network(alias)
        if isinstance(net, EoENetwork):
            return int(net._configured_slaves[drive.target])
        elif isinstance(net, EthernetNetwork):
            return str(drive.target)
        else:
            return int(drive.target)

    def get_name(self, alias: str = DEFAULT_SERVO) -> str:
        """Get the drive name.

        Args:
            alias: Alias of the servo.
        Returns:
            The name of the drive.
        """
        drive = self.mc.servos[alias]
        drive_name = drive.name
        return f"{drive_name}"

    def get_communication_type(self, alias: str = DEFAULT_SERVO) -> str:
        """Get the type of the communication of the connected drive.

        Args:
            alias: alias of the connected drive.

        Returns:
            CANopen, Ethernet, or EtherCAT.

        """
        drive_network = self.mc._get_network(alias)
        if isinstance(drive_network, CanopenNetwork):
            communication_type = "CANopen"
        elif isinstance(drive_network, EoENetwork):
            communication_type = "EtherCAT"
        else:
            communication_type = "Ethernet"
        return communication_type

    def get_full_name(self, alias: str = DEFAULT_SERVO) -> str:
        """Return the full name of the drive [Product name] [Name] ([Target]).

        Args:
            alias: Drive alias.

        Returns:
            Full name.
        """
        prod_name = self.get_product_name(alias)
        name = self.get_name(alias)
        target = self.get_target(alias)
        full_name = f"{prod_name} - {name}"
        net = self.mc._get_network(alias)
        if isinstance(net, EthernetNetwork):
            full_name = f"{full_name} ({target})"
        return full_name

    def get_subnodes(self, alias: str = DEFAULT_SERVO) -> int:
        """Return the number of subnodes.

        Args:
            alias: Drive alias.

        Returns:
            Number of subnodes.
        """
        drive = self.mc.servos[alias]
        return int(drive.subnodes)

    def get_categories(self, alias: str) -> dict[str, str]:
        """Return dictionary categories instance.

        Args:
            alias: Drive alias.

        Returns:
            Categories instance.
        """
        drive = self.mc.servos[alias]
        dictionary_categories = drive.dictionary.categories
        category_ids = dictionary_categories.category_ids
        categories: dict[str, str] = {}
        for cat_id in category_ids:
            categories[cat_id] = dictionary_categories.labels(cat_id)["en_US"]
        return categories

    def get_dictionary_file_name(self, alias: str) -> str:
        """Return dictionary file name.

        Args:
            alias: Drive alias.

        Returns:
            Dictionary file name.
        """
        drive = self.mc.servos[alias]
        return str(os.path.basename(drive.dictionary.path))

    def get_encoded_image_from_dictionary(self, alias: str) -> Optional[str]:
        """Get the encoded product image from a drive dictionary.

        This function reads a dictionary of a drive, and it parses whether the dictionary file has a
        DriveImage tag and its content.

        Args:
            alias: Alias of the drive.

        Returns:
            The encoded image or NoneType object.
        """
        drive = self.mc.servos[alias]
        # Read encoded image in XDF dictionary file
        dictionary_path = drive.dictionary.path
        try:
            with open(dictionary_path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xdf file in the path: {dictionary_path}")
        root = tree.getroot()
        try:
            image_element = root.findall(f"./DriveImage")
            if image_element[0].text is not None and image_element[0].text.strip():
                return f"{image_element[0].text}"
            else:
                # If the content in DriveImage tag is empty
                return None
        except IndexError:
            # If there is no DriveImage tag in dictionary file
            return None

    def get_drive_info_coco_moco(
            self, alias: str
    ) -> tuple[list[Optional[int]], list[Optional[int]], list[Optional[str]], list[Optional[int]]]:
        """Get info from COCO and MOCO registers.

        Args:
            alias: Servo alias.

        Returns:
            Product codes (COCO, MOCO).
            Revision numbers (COCO, MOCO).
            FW versions (COCO, MOCO).
            Serial numbers (COCO, MOCO).

        """
        prod_codes: list[Optional[int]] = [None, None]
        rev_numbers: list[Optional[int]] = [None, None]
        fw_versions: list[Optional[str]] = [None, None]
        serial_number: list[Optional[int]] = [None, None]

        for subnode in [0, 1]:
            # Product codes
            try:
                prod_codes[subnode] = self.mc.communication.get_register(
                    Servo.PRODUCT_ID_REGISTERS[subnode], alias, axis=subnode
                )
            except (
                    ILError,
                    IMException,
            ) as e:
                logger.error(e)
            # Revision numbers
            try:
                rev_numbers[subnode] = self.mc.communication.get_register(
                    Servo.REVISION_NUMBER_REGISTERS[subnode], alias, axis=subnode
                )
            except (ILError, IMException) as e:
                logger.error(e)
            # FW versions
            try:
                fw_versions[subnode] = self.mc.communication.get_register(
                    Servo.SOFTWARE_VERSION_REGISTERS[subnode], alias, axis=subnode
                )
            except (ILError, IMException) as e:
                logger.error(e)
            # Serial numbers
            try:
                serial_number[subnode] = self.mc.communication.get_register(
                    Servo.SERIAL_NUMBER_REGISTERS[subnode], alias, axis=subnode
                )
            except (ILError, IMException) as e:
                logger.error(e)

        return prod_codes, rev_numbers, fw_versions, serial_number

    def get_drive_info(self, alias: str, force_reading: bool = False) -> tuple[int, int, str, int]:
        """Get info from MOCO if it is available or from COCO if it is not.

        Args:
            alias: Servo alias.
            force_reading: If True, cleans the cache before reading the drive.

        Returns:
            Product code.
            Revision number.
            FW version.
            Serial number.
        """
        prod_codes, rev_numbers, fw_versions, serial_numbers = self.get_drive_info_coco_moco(alias)

        prod_code = prod_codes[1] or prod_codes[0] or 0

        rev_number = rev_numbers[1] or rev_numbers[0] or 0

        fw_version = fw_versions[1] or fw_versions[0] or "-"
        fw_version = "_" + ".".join(fw_version.split(".")[:4])

        serial_number = serial_numbers[1] or serial_numbers[0] or 0

        return prod_code, rev_number, fw_version, serial_number

    def get_serial_number(self, alias: str) -> int:
        """Get the serial number of a drive.

        Args:
            alias: Alias of the drive.

        Returns:
            Serial number
        """
        _, _, _, serial_number = self.get_drive_info(alias)
        return serial_number

    def get_fw_version(self, alias: str) -> str:
        """Get the firmware version of a drive.

        Args:
            alias: Alias of the drive.

        Returns:
            Firmware version.
        """
        _, _, fw_version, _ = self.get_drive_info(alias)
        fw_version = fw_version.replace("_", "")
        return fw_version
