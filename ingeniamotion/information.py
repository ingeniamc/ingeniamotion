import os
from typing import TYPE_CHECKING, Optional, Union

import ingenialogger
from ingenialink import CanBaudrate
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.dictionary import SubnodeType
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.eoe.network import EoENetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.register import Register

from ingeniamotion.enums import CommunicationType
from ingeniamotion.exceptions import IMError, IMRegisterNotExistError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

logger = ingenialogger.get_logger(__name__)


class Information:
    """Information."""

    PRODUCT_CODE_COMKIT = 0x3214001
    PART_NUMBER_COMKIT = "COM-KIT"

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
            IMRegisterNotExistError: If register does not exist in dictionary.

        """
        drive = self.mc._get_drive(servo)
        try:
            return drive.dictionary.registers(axis)[register]
        except KeyError:
            raise IMRegisterNotExistError(
                f"Register: {register} axis: {axis} not exist in dictionary"
            )

    def register_type(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> RegDtype:
        """Return register dtype.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register dtype.

        Raises:
            IMRegisterNotExistError: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.dtype

    def register_access(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> RegAccess:
        """Return register access.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register access.

        Raises:
            IMRegisterNotExistError: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.access

    def register_range(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> Union[tuple[None, None], tuple[int, int], tuple[float, float], tuple[str, str]]:
        """Return register range.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register range, minimum and maximum.

        Raises:
            IMRegisterNotExistError: If register does not exist in dictionary.

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
        drive = self.mc._get_drive(servo)
        return register in drive.dictionary.registers(axis)

    def get_product_name(self, servo: str = DEFAULT_SERVO) -> Optional[str]:
        """Get the product name of the drive.

        Args:
            servo: alias of the servo.

        Returns:
            If it exists for example: "EVE-NET-E", "CAP-NET-E", etc.
        """
        drive = self.mc._get_drive(servo)
        product_name = drive.dictionary.part_number
        if self.is_comkit(servo):
            return f"{product_name} + {self.PART_NUMBER_COMKIT}"
        return product_name

    def get_node_id(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the node ID for CANopen communications.

        Args:
            servo: alias of the servo.

        Returns:
            Node ID of the drive.
        """
        drive = self.mc._get_drive(servo)
        net = self.mc._get_network(servo)
        if isinstance(net, CanopenNetwork):
            return int(drive.target)
        else:
            raise IMError("You need a CANopen communication to use this function")

    def get_baudrate(self, servo: str = DEFAULT_SERVO) -> CanBaudrate:
        """Get the baudrate of target servo.

        Args:
            servo: alias of the servo.

        Returns:
            Baudrate of the drive.
        """
        net = self.mc._get_network(servo)
        if isinstance(net, CanopenNetwork):
            return CanBaudrate(net.baudrate)
        raise IMError(f"The servo {servo} is not a CANopen device.")

    def get_ip(self, servo: str = DEFAULT_SERVO) -> str:
        """Get the IP for Ethernet communications.

        Args:
            servo: alias of the servo.

        Returns:
            IP of the drive.
        """
        drive = self.mc._get_drive(servo)
        net = self.mc._get_network(servo)
        if isinstance(net, EthernetNetwork):
            return str(drive.target)
        else:
            raise IMError("You need an Ethernet communication to use this function")

    def get_slave_id(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the EtherCAT slave ID of a given servo.

        Args:
            servo: alias of the servo.

        Returns:
            Slave ID of the servo.

        """
        drive = self.mc._get_drive(servo)
        net = self.mc._get_network(servo)
        if isinstance(net, EoENetwork) and isinstance(drive.target, str):
            return net._configured_slaves[drive.target]
        elif isinstance(net, EthercatNetwork) and isinstance(drive.target, int):
            return drive.target
        raise IMError(f"The servo {servo} is not an EtherCAT slave.")

    def get_name(self, servo: str = DEFAULT_SERVO) -> str:
        """Get the drive's name.

        Args:
            servo: Alias of the servo.

        Returns:
            The name of the drive.
        """
        drive = self.mc._get_drive(servo)
        drive_name = drive.name
        return f"{drive_name}"

    def get_communication_type(self, servo: str = DEFAULT_SERVO) -> CommunicationType:
        """Get the connected drive's communication type.

        Args:
            servo: alias of the connected drive.

        Returns:
            CANopen, Ethernet, or EtherCAT.

        """
        drive_network = self.mc._get_network(servo)
        if isinstance(drive_network, CanopenNetwork):
            communication_type = CommunicationType.Canopen
        elif isinstance(drive_network, EthernetNetwork):
            communication_type = CommunicationType.Ethernet
        elif isinstance(drive_network, (EoENetwork, EthercatNetwork)):
            communication_type = CommunicationType.Ethercat
        else:
            raise NotImplementedError("Unknown communication type.")
        return communication_type

    def get_full_name(self, servo: str = DEFAULT_SERVO) -> str:
        """Return the full name of the drive [Product name] [Name] ([Target]).

        Args:
            servo: Drive alias.

        Returns:
            Full name.
        """
        prod_name = self.get_product_name(servo)
        name = self.get_name(servo)
        full_name = f"{prod_name} - {name}"
        net = self.mc._get_network(servo)
        if isinstance(net, EthernetNetwork):
            ip = self.get_ip(servo)
            full_name = f"{full_name} ({ip})"
        return full_name

    def get_subnodes(self, servo: str = DEFAULT_SERVO) -> dict[int, SubnodeType]:
        """Return a dictionary with the subnodes IDs as keys and their type as values.

        Args:
            servo: Drive alias.

        Returns:
            Dictionary of subnode ids and their type.
        """
        drive = self.mc._get_drive(servo)
        return drive.subnodes

    def get_categories(self, servo: str = DEFAULT_SERVO) -> dict[str, str]:
        """Return dictionary categories instance.

        Args:
            servo: Drive alias.

        Returns:
            Categories instance.
        """
        drive = self.mc._get_drive(servo)
        dictionary_categories = drive.dictionary.categories
        if not dictionary_categories:
            raise IMError("Dictionary categories are not defined.")
        category_ids = dictionary_categories.category_ids
        categories: dict[str, str] = {}
        for cat_id in category_ids:
            categories[cat_id] = dictionary_categories.labels(cat_id)["en_US"]
        return categories

    def get_dictionary_file_name(self, servo: str = DEFAULT_SERVO) -> str:
        """Return dictionary file name.

        Args:
            servo: Drive alias.

        Returns:
            Dictionary file name.
        """
        drive = self.mc._get_drive(servo)
        return str(os.path.basename(drive.dictionary.path))

    def get_encoded_image_from_dictionary(self, servo: str = DEFAULT_SERVO) -> Optional[str]:
        """Get the encoded product image from a drive dictionary.

        This function reads a dictionary of a drive, and it parses whether the dictionary file has a
        DriveImage tag and its content.

        Args:
            servo: Alias of the drive.

        Returns:
            The encoded image or NoneType object.
        """
        drive = self.mc._get_drive(servo)
        return drive.dictionary.image

    def is_comkit(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if drive is connected via a COM-KIT.

        Args:
            servo: Alias of the drive.

        Returns:
            True if using COM-KIT, False otherwise.

        """
        drive = self.mc._get_drive(servo)
        return drive.dictionary.coco_product_code == self.PRODUCT_CODE_COMKIT
