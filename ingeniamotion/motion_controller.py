from enum import IntEnum
from typing import Dict

from ingenialink.network import Network
from ingenialink.servo import Servo

from ingeniamotion.capture import Capture
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.errors import Errors
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEMaster
from ingeniamotion.information import Information
from ingeniamotion.io import InputsOutputs
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.motion import Motion


class MotionController:
    """Motion Controller."""

    def __init__(self) -> None:
        self.__servos: Dict[str, Servo] = {}
        self.__net: Dict[str, Network] = {}
        self.__servo_net: Dict[str, str] = {}
        self.__config: Configuration = Configuration(self)
        self.__motion: Motion = Motion(self)
        self.__capture: Capture = Capture(self)
        self.__comm: Communication = Communication(self)
        self.__tests: DriveTests = DriveTests(self)
        self.__errors: Errors = Errors(self)
        self.__info: Information = Information(self)
        self.__io = InputsOutputs(self)
        if FSOE_MASTER_INSTALLED:
            self.__fsoe: FSoEMaster = FSoEMaster(self)

    def servo_name(self, servo: str = DEFAULT_SERVO) -> str:
        return "{} ({})".format(self.servos[servo].info["product_code"], servo)

    def get_register_enum(
        self, register: str, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> IntEnum:
        drive = self.servos[servo]
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

    def _get_drive(self, servo: str) -> Servo:
        """Return servo drive instance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Servo instance.

        """
        return self.servos[servo]

    # Properties
    @property
    def servos(self) -> Dict[str, Servo]:
        """Dict of ``ingenialink.Servo`` connected indexed by alias"""
        return self.__servos

    @servos.setter
    def servos(self, value: Dict[str, Servo]) -> None:
        self.__servos = value

    @property
    def net(self) -> Dict[str, Network]:
        """Dict of ``ingenialink.Network`` connected indexed by alias"""
        return self.__net

    @net.setter
    def net(self, value: Dict[str, Network]) -> None:
        self.__net = value

    @property
    def servo_net(self) -> Dict[str, str]:
        return self.__servo_net

    @servo_net.setter
    def servo_net(self, value: Dict[str, str]) -> None:
        self.__servo_net = value

    @property
    def configuration(self) -> Configuration:
        """Instance of  :class:`~ingeniamotion.configuration.Configuration` class"""
        return self.__config

    @property
    def motion(self) -> Motion:
        """Instance of  :class:`~ingeniamotion.motion.Motion` class"""
        return self.__motion

    @property
    def capture(self) -> Capture:
        """Instance of  :class:`~ingeniamotion.capture.Capture` class"""
        return self.__capture

    @property
    def communication(self) -> Communication:
        """Instance of  :class:`~ingeniamotion.communication.Communication` class"""
        return self.__comm

    @property
    def tests(self) -> DriveTests:
        """Instance of  :class:`~ingeniamotion.drive_tests.DriveTests` class"""
        return self.__tests

    @property
    def errors(self) -> Errors:
        """Instance of :class:`~ingeniamotion.errors.Errors` class"""
        return self.__errors

    @property
    def info(self) -> Information:
        """Instance of :class:`~ingeniamotion.errors.Information` class"""
        return self.__info

    @property
    def fsoe(self) -> "FSoEMaster":
        """Instance of :class:`~ingeniamotion.fsoe.FSoEMaster` class"""
        if not FSOE_MASTER_INSTALLED:
            raise NotImplementedError(
                "The FSoE module is not available. "
                "Install ingeniamotion with FSoE feature: "
                "pip install ingeniamotion[FSoE]"
            )
        return self.__fsoe

    @property
    def io(self) -> InputsOutputs:
        """Instance of :class:`~ingeniamotion.io.InputsOutputs` class"""
        return self.__io
