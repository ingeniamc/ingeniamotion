from .commissioning import Commissioning
from .motion import Motion
from .capture import Capture
from .launcher import Launcher

class MotionController():
    """Motion Controller.

    Parameters:
        
    Returns:
        
    """

    self.__servos = []
    self.__net = None


    def __init__(self):
        self.__commissioning = Commissioning(self)
        self.__motion = Motion(self)
        self.__capture = Capture(self)
        self.__launcher = Launcher(self)

    
    def MCConnectServo():
        pass

    
    def MCDisconnectServo():
        pass

    # Properties
    @property
    def servo(self):
        return self.__servo

    @servo.setter
    def servo(self, value):
        self.__servo = value

    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def commissioning(self):
        return self.__commissioning

    @commissioning.setter
    def commissioning(self, value):
        self.__commissioning = value

    @property
    def mot(self):
        return self.__motion

    @mot.setter
    def mot(self, value):
        self.__motion = value

    @property
    def cap(self):
        return self.__capture

    @cap.setter
    def cap(self, value):
        self.__capture = value

    @property
    def lan(self):
        return self.__launcher

    @lan.setter
    def lan(self, value):
        self.__launcher = value