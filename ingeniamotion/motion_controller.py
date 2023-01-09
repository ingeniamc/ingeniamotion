from enum import IntEnum

from ingenialink.network import Network
from ingenialink.servo import Servo

from .configuration import Configuration
from .motion import Motion
from .capture import Capture
from .communication import Communication
from .drive_tests import DriveTests
from .errors import Errors
from .information import Information
from .metaclass import DEFAULT_SERVO, DEFAULT_AXIS


class MotionController:
    """Motion Controller."""

    def __init__(self):
        self.__servos = {}
        self.__net = {}
        self.__servo_net = {}
        self.__config = Configuration(self)
        self.__motion = Motion(self)
        self.__capture = Capture(self)
        self.__comm = Communication(self)
        self.__tests = DriveTests(self)
        self.__errors = Errors(self)
        self.__info = Information(self)

    def servo_name(self, servo: str = DEFAULT_SERVO) -> str:
        return "{} ({})".format(self.servos[servo].info["product_code"], servo)

    def get_register_enum(
        self, register: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> IntEnum:
        drive = self.servos[servo]
        enum_list = drive.dictionary.registers(axis)[register].enums
        enum_dict = {x["label"]: x["value"] for x in enum_list}
        return IntEnum(register, enum_dict)

    def is_alive(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the servo is alive.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            ``True`` if the servo is alive, ``False`` otherwise.

        """
        drive = self.mc._get_drive(servo)
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
    def servos(self):
        """Dict of ``ingenialink.Servo`` connected indexed by alias"""
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def net(self):
        """Dict of ``ingenialink.Network`` connected indexed by alias"""
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def servo_net(self):
        return self.__servo_net

    @servo_net.setter
    def servo_net(self, value):
        self.__servo_net = value

    @property
    def configuration(self):
        """Instance of  :class:`~ingeniamotion.configuration.Configuration` class"""
        return self.__config

    @property
    def motion(self):
        """Instance of  :class:`~ingeniamotion.motion.Motion` class"""
        return self.__motion

    @property
    def capture(self):
        """Instance of  :class:`~ingeniamotion.capture.Capture` class"""
        return self.__capture

    @property
    def communication(self):
        """Instance of  :class:`~ingeniamotion.communication.Communication` class"""
        return self.__comm

    @property
    def tests(self):
        """Instance of  :class:`~ingeniamotion.drive_tests.DriveTests` class"""
        return self.__tests

    @property
    def errors(self):
        """Instance of :class:`~ingeniamotion.errors.Errors` class"""
        return self.__errors

    @property
    def info(self):
        """Instance of :class:`~ingeniamotion.errors.Information` class"""
        return self.__info
