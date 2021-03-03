from .configuration import Configuration
from .motion import Motion
from .capture import Capture
from .communication import Communication
from .drive_tests import DriveTests


class MotionController:
    """Motion Controller.

    Parameters:
        
    Returns:
        
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

    # Properties
    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def configuration(self):
        return self.__config

    @property
    def motion(self):
        return self.__motion

    @property
    def capture(self):
        return self.__capture

    @property
    def communication(self):
        return self.__comm

    @property
    def tests(self):
        return self.__tests
