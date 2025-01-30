class IMException(Exception):
    """Exceptions raised by IngeniaMotion"""



class IMMonitoringError(IMException):
    """Monitoring error raised by IngeniaMotion"""



class IMDisturbanceError(IMException):
    """Disturbance error raised by IngeniaMotion"""



class IMStatusWordError(IMException):
    """Status word error raised by IngeniaMotion"""



class IMRegisterNotExist(IMException):
    """Error raised by IngeniaMotion when a register not exists"""



class IMRegisterWrongAccess(IMException):
    """Error raised by IngeniaMotion when trying to write to a read-only register"""



class IMTimeoutError(IMException):
    """Error raised by IngeniaMotion when a timeout has occurred"""



class IMFirmwareLoadError(IMException):
    """Error raised by IngeniaMotion when a firmware file could not be loaded"""

