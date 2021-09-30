from .exceptions import IMRegisterNotExist
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Information(metaclass=MCMetaClass):
    """Information."""

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def register_info(self, register, axis=DEFAULT_AXIS, servo=DEFAULT_SERVO):
        """Return register object.

        Args:
            register (str): register UID.
            axis (int): servo axis. ``1`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            ingenialink.registers.Register: Register object.
        """
        drive = self.mc.servos[servo]
        try:
            return drive.dictionary.registers(axis)[register]
        except KeyError:
            raise IMRegisterNotExist("Register: {} axis: {} not exist in dictionary"
                                     .format(register, axis))

    def register_type(self, register, axis=DEFAULT_AXIS, servo=DEFAULT_SERVO):
        """Return register dtype.

        Args:
            register (str): register UID.
            axis (int): servo axis. ``1`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            ingenialink.registers.REG_DTYPE: Register dtype.
        """
        register = self.register_info(register, axis=axis, servo=servo)
        return register.dtype

    def register_access(self, register, axis=DEFAULT_AXIS, servo=DEFAULT_SERVO):
        """Return register access.

        Args:
            register (str): register UID.
            axis (int): servo axis. ``1`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            ingenialink.registers.REG_ACCESS: Register access.
        """
        register = self.register_info(register, axis=axis, servo=servo)
        return register.access

    def register_range(self, register, axis=DEFAULT_AXIS, servo=DEFAULT_SERVO):
        """Return register range.

        Args:
            register (str): register UID.
            axis (int): servo axis. ``1`` by default.
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int, int: Register range, minimum and maximum.
        """
        register = self.register_info(register, axis=axis, servo=servo)
        return register.range
