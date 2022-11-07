from .exceptions import IMRegisterNotExist
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO
from ingenialink.register import Register, REG_ACCESS, REG_DTYPE


class Information(metaclass=MCMetaClass):
    """Information."""

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def register_info(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> Register:
        """Return register object.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register object.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        drive = self.mc.servos[servo]
        try:
            return drive.dictionary.registers(axis)[register]
        except KeyError:
            raise IMRegisterNotExist("Register: {} axis: {} not exist in dictionary"
                                     .format(register, axis))

    def register_type(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> REG_DTYPE:
        """Return register dtype.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register dtype.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.dtype

    def register_access(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> REG_ACCESS:
        """Return register access.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register access.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.access

    def register_range(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> tuple[int, int]:
        """Return register range.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Register range, minimum and maximum.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.

        """
        register_obj = self.register_info(register, axis=axis, servo=servo)
        return register_obj.range

    def register_exists(
        self,
        register: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
    ) -> bool:
        """Check if register exists in dictionary.

        Args:
            register : register UID.
            axis : servo axis. ``1`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            ``True`` if register exists, else ``False``.

        """
        drive = self.mc.servos[servo]
        return register in drive.dictionary.registers(axis)
