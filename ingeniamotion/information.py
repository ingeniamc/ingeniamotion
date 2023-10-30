import os
from typing import TYPE_CHECKING, Dict, Optional, Tuple
import xml.etree.ElementTree as ET

from ingenialink.eoe.network import EoENetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.register import Register, REG_ACCESS, REG_DTYPE
import ingenialogger

from ingeniamotion.exceptions import IMRegisterNotExist, IMException
from ingeniamotion.metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.enums import COMMUNICATION_TYPE
from ingeniamotion.comkit import create_comkit_dictionary


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
    ) -> Optional[Tuple[int, int]]:
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
        return register_obj.range  # type: ignore [no-any-return]

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

    @staticmethod
    def create_comkit_dictionary(
        coco_dict_path: str, moco_dict_path: str, dest_file: Optional[str] = None
    ) -> str:
        """Create a dictionary for COMKIT by merging a COCO dictionary and a MOCO dictionary.

        Args:
            coco_dict_path : COCO dictionary path.
            moco_dict_path : MOCO dictionary path.
            dest_file: Path to store the COMKIT dictionary. If it's not provided the
                merged dictionary is stored in the temporary system's folder.

        Returns:
            Path to the COMKIT dictionary.

        Raises:
            ValueError: If destination file has a wrong extension.

        """
        return create_comkit_dictionary(coco_dict_path, moco_dict_path, dest_file)

    def get_product_name(self, alias: str = DEFAULT_SERVO) -> Optional[str]:
        """Get the product name of the drive.

        Args:
            alias: alias of the servo.

        Returns:
            If it exists for example: "EVE-NET-E", "CAP-NET-E", etc.
        """
        drive = self.mc.servos[alias]
        product_name = drive.dictionary.part_number
        if not product_name is None:
            return f"{product_name}"
        return None

    def get_node_id(self, alias: str = DEFAULT_SERVO) -> int:
        """Get the node ID for CANopen communications.

        Args:
            alias: alias of the servo.

        Returns:
            Node ID of the drive.
        """
        net = self.mc._get_network(alias)
        drive = self.mc.servos[alias]
        if isinstance(net, CanopenNetwork):
            return int(drive.target)
        else:
            raise IMException("You need a CANopen communication to use this function")

    def get_ip(self, alias: str = DEFAULT_SERVO) -> str:
        """Get the IP for Ethernet communications.

        Args:
            alias: alias of the servo.

        Returns:
            IP of the drive.
        """
        net = self.mc._get_network(alias)
        drive = self.mc.servos[alias]
        if isinstance(net, EthernetNetwork):
            return str(drive.target)
        else:
            raise IMException("You need an Ethernet communication to use this function")

    def get_slave_id(self, alias: str = DEFAULT_SERVO) -> int:
        """Get the slave ID for EoE communications.

        Args:
            alias: alias of the servo.

        Returns:
            Slave ID of the drive.
        """
        net = self.mc._get_network(alias)
        drive = self.mc.servos[alias]
        if isinstance(net, EoENetwork):
            return int(net._configured_slaves[drive.target])
        else:
            raise IMException("You need a CANopen communication to use this function")

    def get_name(self, alias: str = DEFAULT_SERVO) -> str:
        """Get the drive's name.

        Args:
            alias: Alias of the servo.
        Returns:
            The name of the drive.
        """
        drive = self.mc.servos[alias]
        drive_name = drive.name
        return f"{drive_name}"

    def get_communication_type(self, alias: str = DEFAULT_SERVO) -> COMMUNICATION_TYPE:
        """Get the connected drive's communication type.

        Args:
            alias: alias of the connected drive.

        Returns:
            CANopen, Ethernet, or EtherCAT.

        """
        drive_network = self.mc._get_network(alias)
        if isinstance(drive_network, CanopenNetwork):
            communication_type = COMMUNICATION_TYPE.Canopen
        elif isinstance(drive_network, EthernetNetwork):
            communication_type = COMMUNICATION_TYPE.Ethernet
        elif isinstance(drive_network, (EoENetwork, EthercatNetwork)):
            communication_type = COMMUNICATION_TYPE.Ethercat
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
        full_name = f"{prod_name} - {name}"
        net = self.mc._get_network(alias)
        if isinstance(net, EthernetNetwork):
            ip = self.get_ip(alias)
            full_name = f"{full_name} ({ip})"
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

    def get_categories(self, alias: str) -> Dict[str, str]:
        """Return dictionary categories instance.

        Args:
            alias: Drive alias.

        Returns:
            Categories instance.
        """
        drive = self.mc.servos[alias]
        dictionary_categories = drive.dictionary.categories
        category_ids = dictionary_categories.category_ids
        categories: Dict[str, str] = {}
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

    def get_encoded_image_from_dictionary(self, alias: str, axis: int = 0) -> Optional[str]:
        """Get the encoded product image from a drive dictionary.
        This function reads a dictionary of a drive, and it parses whether the dictionary file has a
        DriveImage tag and its content.
        Args:
            alias: Alias of the drive.
            axis: Drive axis. Used when using  COM-KIT.
        Returns:
            The encoded image or NoneType object.
        """
        drive = self.mc.servos[alias]
        encoded_image: Optional[str] = None
        if axis == 1:
            encoded_image = drive.dictionary.moco_image
        else:
            encoded_image = drive.dictionary.image
        return encoded_image
