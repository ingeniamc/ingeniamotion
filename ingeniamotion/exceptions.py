import warnings
from typing import Any


class IMError(Exception):
    """Exceptions raised by IngeniaMotion."""


class IMMonitoringError(IMError):
    """Monitoring error raised by IngeniaMotion."""


class IMDisturbanceError(IMError):
    """Disturbance error raised by IngeniaMotion."""


class IMStatusWordError(IMError):
    """Status word error raised by IngeniaMotion."""


class IMRegisterNotExistError(IMError):
    """Error raised by IngeniaMotion when a register not exists."""


class IMRegisterWrongAccessError(IMError):
    """Error raised by IngeniaMotion when trying to write to a read-only register."""


class IMTimeoutError(IMError):
    """Error raised by IngeniaMotion when a timeout has occurred."""


class IMFirmwareLoadError(IMError):
    """Error raised by IngeniaMotion when a firmware file could not be loaded."""


# WARNING: Deprecated aliases
_DEPRECATED = {
    "IMException": "IMError",
    "IMRegisterNotExist": "IMRegisterNotExistError",
    "IMRegisterWrongAccess": "IMRegisterWrongAccessError",
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED:
        warnings.warn(
            f"{name} is deprecated, use {_DEPRECATED[name]} instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[_DEPRECATED[name]]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
