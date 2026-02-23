from __future__ import annotations

from enum import IntEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Optional

from ingenialink.servo import Servo

from ingeniamotion.capture import Capture
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.errors import Errors
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEMaster
from ingeniamotion.information import Information
from ingeniamotion.input_output import InputsOutputs
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.motion import Motion
from ingeniamotion.motion_node import MotionNode

if TYPE_CHECKING:
    from ingenialink.network import Network


class MotionController:
    """Motion Controller."""

    def __init__(self) -> None:
        # Motion Node alias -> Motion Node instance
        self.__motion_nodes: dict[str, MotionNode] = {}
        # Network Alias -> Network
        self.__net: dict[str, Network] = {}

        # Motion Controller Modules
        self.__config: Configuration = Configuration(self)
        self.__motion: Motion = Motion(self)
        self.__capture: Capture = Capture(self)
        self.__comm: Communication = Communication(self)
        self.__tests: DriveTests = DriveTests(self)
        self.__errors: Errors = Errors(self)
        self.__info: Information = Information(self)
        self.__io = InputsOutputs(self)
        self.__fsoe: Optional[FSoEMaster] = None
        if FSOE_MASTER_INSTALLED:
            self.__fsoe = FSoEMaster(self)

    def servo_name(self, servo: str = DEFAULT_SERVO) -> str:
        """Get the servo name.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            The servo name.

        """
        drive = self._get_drive(servo)
        return "{} ({})".format(drive.info["product_code"], servo)

    def get_register_enum(
        self, register: str, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> IntEnum:
        """Get a register enum.

        Args:
            register: The register UID.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            The register enum as an IntEnum.

        """
        drive = self._get_drive(servo)
        enum_dict = drive.dictionary.registers(axis)[register].enums
        return IntEnum(register, enum_dict)

    def is_alive(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the servo is alive.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            ``True`` if the servo is alive, ``False`` otherwise.

        """
        drive = self._get_drive(servo)
        return drive.is_alive()

    def _get_network(self, servo: str) -> Network:
        """Return servo network instance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Network instance of the servo.

        """
        net_key = self.servo_net[servo]
        return self.net[net_key]

    def _get_drive(self, servo: str = DEFAULT_SERVO) -> Servo:
        """Return servo drive instance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Servo instance.

        Raises:
            KeyError: If the servo is not connected.

        """
        if servo not in self.servos:
            msg = f"Servo {servo} is not connected"
            raise KeyError(msg)
        return self.servos[servo]

    @property
    def motion_nodes(self) -> MappingProxyType[str, MotionNode]:
        """Read only dict of motion nodes indexed by alias."""
        return MappingProxyType(self.__motion_nodes)

    def create_motion_node(self, alias: str, servo: Servo, network: Network) -> MotionNode:
        node = MotionNode(servo=servo, network=network)

        # register motion node instance
        self.__motion_nodes[alias] = node

        # https://novantamotion.atlassian.net/browse/INGK-1247
        servo._disconnect_callback = (
            self.communication._Communication__disconnect_callback
        )  # [attr-defined]

        return node

    def remove_motion_node(self, alias: str) -> None:
        """Helper to unregister a servo and cleanup its network.

        This will remove the servo from the internal registry, remove the
        servo->network mapping, delete the FSoE master handler for the
        servo if present, and delete the network entry when no more servos
        use it.

        Args:
            alias: alias used to reference the servo to remove.
        """
        if alias not in self.__motion_nodes:
            return

        # Remove FSoE handler if installed
        if self.__fsoe is not None:
            self.__fsoe._delete_master_handler(alias)

        # If no servos remain on this network, remove the network entry
        network = self.__motion_nodes[alias].network
        if network is not None:
            # Network of a node might not be registered
            nodes_on_net = [
                node for node in self.__motion_nodes.values() if node.network == network
            ]

            if len(nodes_on_net) == 0:
                self.remove_network(network)

        # Remove motion node entry
        del self.__motion_nodes[alias]

    # Properties
    @property
    def servos(self) -> MappingProxyType[str, Servo]:
        """Mapping of ``ingenialink.Servo`` connected indexed by alias.

        Returns:
            A mapping of connected servos indexed by alias.
        """
        return MappingProxyType({alias: node.servo for alias, node in self.motion_nodes.items()})

    @property
    def net(self) -> MappingProxyType[str, Network]:
        """Dict of ``ingenialink.Network`` connected indexed by alias."""
        return MappingProxyType(self.__net)

    def register_network(self, alias: str, network: Network) -> None:
        """Register a network instance with an alias.

        Args:
            alias: alias to reference the network.
            network: network instance to register.

        """
        self.__net[alias] = network

    def remove_network(self, network: Network) -> None:
        """Remote a network instance from the registry."""
        for alias in [alias for alias, net in self.__net.items() if net == network]:
            del self.__net[alias]

    @property
    def servo_net(self) -> dict[str, str]:
        """Get the servo network dictionary.

        Returns:
            The servo network dictionary.

        """
        # Inverse mapping of self.__net to find aliases for network instances
        net_to_alias = {net: alias for alias, net in self.__net.items()}

        result = {}
        for alias, node in self.__motion_nodes.items():
            # Only include nodes that have a network associated that is also registered
            if node.network in net_to_alias:
                result[alias] = net_to_alias[node.network]
        return result

    @property
    def configuration(self) -> Configuration:
        """Instance of  :class:`~ingeniamotion.configuration.Configuration` class."""
        return self.__config

    @property
    def motion(self) -> Motion:
        """Instance of  :class:`~ingeniamotion.motion.Motion` class."""
        return self.__motion

    @property
    def capture(self) -> Capture:
        """Instance of  :class:`~ingeniamotion.capture.Capture` class."""
        return self.__capture

    @property
    def communication(self) -> Communication:
        """Instance of  :class:`~ingeniamotion.communication.Communication` class."""
        return self.__comm

    @property
    def tests(self) -> DriveTests:
        """Instance of  :class:`~ingeniamotion.drive_tests.DriveTests` class."""
        return self.__tests

    @property
    def errors(self) -> Errors:
        """Instance of :class:`~ingeniamotion.errors.Errors` class."""
        return self.__errors

    @property
    def info(self) -> Information:
        """Instance of :class:`~ingeniamotion.errors.Information` class."""
        return self.__info

    @property
    def fsoe(self) -> "FSoEMaster":
        """Instance of :class:`~ingeniamotion.fsoe.FSoEMaster` class."""
        if self.__fsoe is None:
            raise NotImplementedError(
                "The FSoE module is not available. "
                "Install ingeniamotion with FSoE feature: "
                "pip install ingeniamotion[FSoE]"
            )
        return self.__fsoe

    @property
    def fsoe_is_installed(self) -> bool:
        """Indicates if the FSoE Module is available."""
        return self.__fsoe is not None

    @property
    def io(self) -> InputsOutputs:
        """Instance of :class:`~ingeniamotion.input_output.InputsOutputs` class."""
        return self.__io
