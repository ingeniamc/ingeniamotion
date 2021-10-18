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
