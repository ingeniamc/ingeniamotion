from enum import IntEnum
from typing import Optional

from ingenialink.network import Network
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


class MotionController:
    """Motion Controller."""

    def __init__(self) -> None:
        self.__servos: dict[str, Servo] = {}
        self.__net: dict[str, Network] = {}
        self.__servo_net: dict[str, str] = {}
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

        """
        if servo not in self.servos:
            msg = f"Servo {servo} is not connected"
            raise KeyError(msg)
        return self.servos[servo]

    # Properties
    @property
    def servos(self) -> dict[str, Servo]:
        """Dict of ``ingenialink.Servo`` connected indexed by alias."""
        return self.__servos

    @servos.setter
    def servos(self, value: dict[str, Servo]) -> None:
        self.__servos = value

    @property
    def net(self) -> dict[str, Network]:
        """Dict of ``ingenialink.Network`` connected indexed by alias."""
        return self.__net

    @net.setter
    def net(self, value: dict[str, Network]) -> None:
        self.__net = value

    @property
    def servo_net(self) -> dict[str, str]:
        """Get the servo network dictionary.

        Returns:
            The servo network dictionary.

        """
        return self.__servo_net

    @servo_net.setter
    def servo_net(self, value: dict[str, str]) -> None:
        self.__servo_net = value

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
