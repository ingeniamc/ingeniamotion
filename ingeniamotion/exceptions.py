class IMException(Exception):
    """Exceptions raised by IngeniaMotion"""

    pass


class IMMonitoringError(IMException):
    """Monitoring error raised by IngeniaMotion"""

    pass


class IMDisturbanceError(IMException):
    """Disturbance error raised by IngeniaMotion"""

    pass


class IMStatusWordError(IMException):
    """Status word error raised by IngeniaMotion"""

    pass


class IMRegisterNotExist(IMException):
    """Error raised by IngeniaMotion when a register not exists"""

    pass


class IMRegisterWrongAccess(IMException):
    """Error raised by IngeniaMotion when trying to write to a read-only register"""

    pass


class IMTimeoutError(IMException):
    """Error raised by IngeniaMotion when a timeout has occurred"""

    pass


class IMFirmwareLoadError(IMException):
    """Error raised by IngeniaMotion when a firmware file could not be loaded"""

    pass
