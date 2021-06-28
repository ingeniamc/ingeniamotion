import ingenialogger
import ingenialink as il
from functools import wraps
from ingenialink.exceptions import ILError

from .metaclass import DEFAULT_SERVO, DEFAULT_AXIS


def check_disturbance_disabled(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        disturbance_enabled = self.is_disturbance_enabled()
        if disturbance_enabled:
            raise DisturbanceError("Disturbance is enabled")
        return func(self, *args, **kwargs)

    return wrapper


class Disturbance:
    """
    Class to configure a disturbance in a servo.

    Args:
        mc (MotionController): MotionController instance.
        servo (str): servo alias to reference it. ``default`` by default.
    """

    DISTURBANCE_FREQUENCY_DIVIDER_REGISTER = "DIST_FREQ_DIV"
    DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER = "DIST_MAX_SIZE"
    MONITORING_DISTURBANCE_STATUS_REGISTER = "MON_DIST_STATUS"

    CYCLIC_RX = "CYCLIC_RX"

    DISTURBANCE_STATUS_ENABLED_BIT = 0x1000  # TODO: Not implemented yet
    MONITORING_STATUS_ENABLED_BIT = 0x1
    REGISTER_MAP_OFFSET = 0x800

    MINIMUM_BUFFER_SIZE = 8192

    __data_type_size = {
        il.REG_DTYPE.U8: 1,
        il.REG_DTYPE.S8: 1,
        il.REG_DTYPE.U16: 2,
        il.REG_DTYPE.S16: 2,
        il.REG_DTYPE.U32: 4,
        il.REG_DTYPE.S32: 4,
        il.REG_DTYPE.U64: 8,
        il.REG_DTYPE.S64: 8,
        il.REG_DTYPE.FLOAT: 4
    }

    def __init__(self, mc, servo=DEFAULT_SERVO):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers = []
        self.disturbance_data = []
        self.sampling_freq = None
        self.samples_number = 0
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.max_sample_number = self.get_max_sample_size()
        self.data = None

    @check_disturbance_disabled
    def set_frequency_divider(self, divider):
        """
        Function to define disturbance frequency with a prescaler. Frequency will be
        ``Position & velocity loop rate frequency / prescaler``,  see
        :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
        to know about this frequency. Monitoring/Disturbance must be disabled.

        Args:
            divider (int): determines disturbance frequency. It must be ``1`` or higher.

        Return:
            float: sample period in seconds.

        Raises:
            ValueError: If divider is less than ``1``.
        """
        if divider < 1:
            raise ValueError("divider must be 1 or higher")
        position_velocity_loop_rate = \
            self.mc.configuration.get_position_and_velocity_loop_rate(
                servo=self.servo
            )
        self.sampling_freq = round(position_velocity_loop_rate / divider, 2)
        self.mc.communication.set_register(
            self.DISTURBANCE_FREQUENCY_DIVIDER_REGISTER,
            divider,
            servo=self.servo,
            axis=0
        )
        return 1 / self.sampling_freq

    @check_disturbance_disabled
    def map_registers(self, registers):
        """
        Map registers to Disturbance. Disturbance must be disabled.

        Args:
            registers (dict or list of dict): registers to map.
                Each register must be a dict with two keys.

                .. code-block:: python

                    {
                        "name": "CL_POS_SET_POINT_VALUE",  # Register name.
                        "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                    }

        Returns:
            int: max number of samples

        Raises:
            DisturbanceError: If the register is not allowed to be mapped as
                a disturbance register.
        """
        if not isinstance(registers, list):
            registers = [registers]
        drive = self.mc.servos[self.servo]
        network = self.mc.net[self.servo]
        network.disturbance_remove_all_mapped_registers()
        total_sample_size = 0
        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            register_obj = drive.dict.get_regs(subnode)[register]
            dtype = register_obj.dtype
            cyclic = register_obj.cyclic
            if cyclic != self.CYCLIC_RX:
                network.disturbance_remove_all_mapped_registers()
                raise DisturbanceError("{} can not be mapped as a disturbance register"
                                       .format(register))
            channel["dtype"] = dtype
            address_offset = self.REGISTER_MAP_OFFSET * (subnode - 1)
            mapped_reg = register_obj.address + address_offset
            network.disturbance_set_mapped_register(ch_idx, mapped_reg, dtype.value)
            self.mapped_registers.append(channel)
            total_sample_size += self.__data_type_size[dtype]
        return self.max_sample_number / total_sample_size

    @check_disturbance_disabled
    def write_disturbance_data(self, registers_data):
        """
        Write data in mapped registers. Disturbance must be disabled.

        Args:
            registers_data (list of (list or float or int)):
                data to write in disturbance. Registers should have same order
                as in :func:`map_registers`.

        Raises:
            DisturbanceError: If buffer size is not enough for all the
                registers and samples.
        """
        if isinstance(registers_data, list) and not isinstance(registers_data[0], list):
            registers_data = [registers_data]
        drive = self.mc.servos[self.servo]
        self.__check_buffer_size_is_enough(registers_data)
        idx_list = list(range(len(registers_data)))
        dtype_list = [x["dtype"] for x in self.mapped_registers]
        drive.disturbance_write_data(idx_list, dtype_list, registers_data)

    def map_registers_and_write_data(self, registers):
        """
        Map registers to Disturbance and write data. Disturbance must be disabled.

        Args:
            registers (dict or list of dict): registers to map and write data.
                Each register must be a dict with three keys:

                .. code-block:: python

                    {
                        "name": "CL_POS_SET_POINT_VALUE",  # Register name.
                        "axis": 1,  # Register axis. If it has no axis field, by default axis 1.
                        "data": [0.0, 0.1, 0.2, ...]  # Data for load in this register
                    }

        Raises:
            DisturbanceError: If the register is not allowed to be mapped as a
                disturbance register.
            DisturbanceError: If buffer size is not enough for all the
                registers and samples.
        """
        if not isinstance(registers, list):
            registers = [registers]
        registers_keys = []
        registers_data = []
        for channel in registers:
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            registers_keys.append({"axis": subnode, "name": register})
            registers_data.append(channel["data"])
        self.map_registers(registers_keys)
        self.write_disturbance_data(registers_data)

    def __check_buffer_size_is_enough(self, registers):
        total_buffer_size = 0
        for ch_idx, data in enumerate(registers):
            dtype = self.mapped_registers[ch_idx]["dtype"]
            total_buffer_size += self.__data_type_size[dtype] * len(data)
        if total_buffer_size > self.max_sample_number:
            raise DisturbanceError(
                "Number of samples is too high. "
                "Demanded size: {} bytes, buffer max size: {} bytes."
                .format(total_buffer_size, self.max_sample_number)
            )
        self.logger.debug("Demanded size: %d bytes, buffer max size: %d bytes.",
                          total_buffer_size, self.max_sample_number)

    def enable_disturbance(self):
        """
        Enable disturbance

        Raises:
            DisturbanceError: If disturbance can't be enabled.
        """
        network = self.mc.net[self.servo]
        network.monitoring_enable()
        # Check monitoring status
        if not self.is_disturbance_enabled():
            raise DisturbanceError("Error enabling disturbance.")

    def disable_disturbance(self):
        """
        Disable disturbance
        """
        network = self.mc.net[self.servo]
        network.monitoring_disable()

    def get_monitoring_disturbance_status(self):
        """
        Get Monitoring/Disturbance Status.

        Returns:
            int: Monitoring/Disturbance Status.
        """
        return self.mc.communication.get_register(
            self.MONITORING_DISTURBANCE_STATUS_REGISTER,
            servo=self.servo,
            axis=0
        )

    def is_disturbance_enabled(self):
        """
        Check if disturbance is enabled.

        Returns:
            bool: True if disturbance is enabled, else False.
        """
        disturbance_status = self.get_monitoring_disturbance_status()
        return (disturbance_status & self.MONITORING_STATUS_ENABLED_BIT) == 1

    def get_max_sample_size(self):
        """
        Return disturbance max size, in bytes.

        Returns:
            int: Max buffer size in bytes.
        """
        try:
            return self.mc.communication.get_register(
                self.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER,
                servo=self.servo,
                axis=0
            )
        except ILError:
            return self.MINIMUM_BUFFER_SIZE


class DisturbanceError(Exception):
    pass
