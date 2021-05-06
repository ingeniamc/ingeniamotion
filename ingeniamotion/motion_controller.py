from enum import IntEnum

from .configuration import Configuration
from .motion import Motion
from .capture import Capture
from .communication import Communication
from .drive_tests import DriveTests


class MotionController:
    """Motion Controller.
    """

    def __init__(self):
        self.__servos = {}
        self.__net = {}
        self.__config = Configuration(self)
        self.__motion = Motion(self)
        self.__capture = Capture(self)
        self.__comm = Communication(self)
        self.__tests = DriveTests(self)

    def check_servo(self, servo):
        if servo not in self.servos:
            raise Exception("Servo '{}' does not exist".format(servo))

    def servo_name(self, servo):
        return "{} ({})".format(self.servos[servo].info["prod_code"], servo)

    def get_register_enum(self, register, servo, axis):
        drive = self.servos[servo]
        enum_list = drive.dict.get_regs(axis)[register].enums
        enum_dict = {x["label"]: x["value"] for x in enum_list}
        return IntEnum(register, enum_dict)

    # Properties
    @property
    def servos(self):
        """
        Dict of ``ingenialink.Servo`` connected indexed by alias
        """
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def net(self):
        """
        Dict of ``ingenialink.Network`` connected indexed by alias
        """
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def configuration(self):
        """
        Instance of  :class:`~ingeniamotion.configuration.Configuration` class
        """
        return self.__config

    @property
    def motion(self):
        """
        Instance of  :class:`~ingeniamotion.motion.Motion` class
        """
        return self.__motion

    @property
    def capture(self):
        """
        Instance of  :class:`~ingeniamotion.capture.Capture` class
        """
        return self.__capture

    @property
    def communication(self):
        """
        Instance of  :class:`~ingeniamotion.communication.Communication` class
        """
        return self.__comm

    @property
    def tests(self):
        """
        Instance of  :class:`~ingeniamotion.drive_tests.DriveTests` class
        """
        return self.__tests
