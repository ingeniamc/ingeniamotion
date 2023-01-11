import ingenialogger
from numpy import ndarray
from functools import wraps
from collections.abc import Iterable
from typing import Union, TYPE_CHECKING, List

from ingenialink.ipb.register import IPBRegister
from ingenialink.ethernet.register import EthernetRegister

from ingeniamotion.enums import MonitoringVersion, REG_DTYPE
from .metaclass import DEFAULT_SERVO, DEFAULT_AXIS
from .exceptions import IMDisturbanceError, IMStatusWordError


if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


def check_disturbance_disabled(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        disturbance_enabled = self.mc.capture.is_disturbance_enabled(
            servo=self.servo, version=self._version
        )
        if disturbance_enabled:
            raise IMDisturbanceError("Disturbance is enabled")
        return func(self, *args, **kwargs)

    return wrapper


class Disturbance:
    """Class to configure a disturbance in a servo.

    Args:
        mc : MotionController instance.
        servo : servo alias to reference it. ``default`` by default.
    """

    DISTURBANCE_FREQUENCY_DIVIDER_REGISTER = "DIST_FREQ_DIV"
    DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER = "DIST_MAX_SIZE"
    MONITORING_DISTURBANCE_STATUS_REGISTER = "MON_DIST_STATUS"

    CYCLIC_RX = "CYCLIC_RX"

    DISTURBANCE_STATUS_ENABLED_BIT = 0x1000  # TODO: Not implemented yet
    MONITORING_STATUS_ENABLED_BIT = 0x1
    REGISTER_MAP_OFFSET = 0x800

    __data_type_size = {
        REG_DTYPE.U8: 1,
        REG_DTYPE.S8: 1,
        REG_DTYPE.U16: 2,
        REG_DTYPE.S16: 2,
        REG_DTYPE.U32: 4,
        REG_DTYPE.S32: 4,
        REG_DTYPE.U64: 8,
        REG_DTYPE.S64: 8,
        REG_DTYPE.FLOAT: 4,
    }

    def __init__(self, mc: "MotionController", servo: str = DEFAULT_SERVO):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers = []
        self.sampling_freq = None
        self._version = mc.capture._check_version(servo)
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.max_sample_number = mc.capture.disturbance_max_sample_size(servo)
        if self._version < MonitoringVersion.MONITORING_V3:
            try:
                self.mc.capture.mcb_synchronization(servo=servo)
            except IMStatusWordError:
                self.logger.warning(
                    "MCB could not be synchronized. Motor is enabled.", drive=mc.servo_name(servo)
                )

    @check_disturbance_disabled
    def set_frequency_divider(self, divider: int) -> float:
        """Function to define disturbance frequency with a prescaler. Frequency will be
        ``Position & velocity loop rate frequency / prescaler``,  see
        :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
        to know about this frequency. Monitoring/Disturbance must be disabled.

        Args:
            divider : determines disturbance frequency. It must be ``1`` or higher.

        Return:
            Sample period in seconds.

        Raises:
            ValueError: If divider is less than ``1``.
        """
        if divider < 1:
            raise ValueError("divider must be 1 or higher")
        position_velocity_loop_rate = self.mc.configuration.get_position_and_velocity_loop_rate(
            servo=self.servo
        )
        self.sampling_freq = round(position_velocity_loop_rate / divider, 2)
        self.mc.communication.set_register(
            self.DISTURBANCE_FREQUENCY_DIVIDER_REGISTER, divider, servo=self.servo, axis=0
        )
        return 1 / self.sampling_freq

    @check_disturbance_disabled
    def map_registers(self, registers: Union[dict, List[dict]]) -> int:
        """Map registers to Disturbance. Disturbance must be disabled.

        Args:
            registers : registers to map.
                Each register must be a dict with two keys.

                .. code-block:: python

                    {
                        "name": "CL_POS_SET_POINT_VALUE",  # Register name.
                        "axis": 1  # Register axis.
                        # If it has no axis field, by default axis 1.
                    }

        Returns:
            Max number of samples

        Raises:
            IMDisturbanceError: If the register is not allowed to be mapped as
                a disturbance register.
        """
        if len(registers) == 0:
            raise IMDisturbanceError("No registers to be mapped.")
        if not isinstance(registers, list):
            registers = [registers]
        drive = self.mc.servos[self.servo]
        drive.disturbance_remove_all_mapped_registers()
        total_sample_size = 0
        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            register_obj = self.mc.info.register_info(register, subnode, servo=self.servo)
            dtype = register_obj.dtype
            cyclic = register_obj.cyclic
            if cyclic != self.CYCLIC_RX:
                drive.disturbance_remove_all_mapped_registers()
                raise IMDisturbanceError(
                    "{} can not be mapped as a disturbance register".format(register)
                )
            channel["dtype"] = dtype
            address_offset = self.REGISTER_MAP_OFFSET * (subnode - 1)
            if isinstance(register_obj, (IPBRegister, EthernetRegister)):
                mapped_reg = register_obj.address + address_offset
            else:
                mapped_reg = register_obj.idx
            drive.disturbance_set_mapped_register(
                ch_idx, mapped_reg, subnode, dtype.value, self.__data_type_size[dtype]
            )
            self.mapped_registers.append(channel)
            total_sample_size += self.__data_type_size[dtype]
        return self.max_sample_number / total_sample_size

    @staticmethod
    def __registers_data_adapter(registers_data):
        if isinstance(registers_data, ndarray):
            registers_data = registers_data.tolist()
        if isinstance(registers_data, Iterable) and not isinstance(registers_data[0], Iterable):
            return [registers_data]
        if isinstance(registers_data, Iterable):
            for i, x in enumerate(registers_data):
                if isinstance(x, ndarray):
                    registers_data[i] = x.tolist()
        return registers_data

    @check_disturbance_disabled
    def write_disturbance_data(self, registers_data: List[Union[list, float, int]]) -> None:
        """Write data in mapped registers. Disturbance must be disabled.

        Args:
            registers_data :
                data to write in disturbance. Registers should have same order
                as in :func:`map_registers`.

        Raises:
            IMDisturbanceError: If buffer size is not enough for all the
                registers and samples.
        """
        if len(self.mapped_registers) == 0 or self.sampling_freq is None:
            raise IMDisturbanceError("Disturbance is not correctly configured yet")
        registers_data = self.__registers_data_adapter(registers_data)
        drive = self.mc.servos[self.servo]
        self.__check_buffer_size_is_enough(registers_data)
        idx_list = list(range(len(registers_data)))
        dtype_list = [REG_DTYPE(x["dtype"]) for x in self.mapped_registers]
        drive.disturbance_write_data(idx_list, dtype_list, registers_data)

    def map_registers_and_write_data(self, registers: Union[dict, List[dict]]) -> None:
        """Map registers to Disturbance and write data. Disturbance must be disabled.

        Args:
            registers : registers to map and write data.
                Each register must be a dict with three keys:

                .. code-block:: python

                    {
                        "name": "CL_POS_SET_POINT_VALUE",  # Register name.
                        "axis": 1,  # Register axis.
                        # If it has no axis field, by default axis 1.
                        "data": [0.0, 0.1, 0.2, ...]  # Data for load in this register
                    }

        Raises:
            IMDisturbanceError: If the register is not allowed to be mapped as a
                disturbance register.
            IMDisturbanceError: If buffer size is not enough for all the
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

    def __check_buffer_size_is_enough(self, registers: List[Union[list, float, int]]) -> None:
        total_buffer_size = 0
        for ch_idx, data in enumerate(registers):
            dtype = self.mapped_registers[ch_idx]["dtype"]
            total_buffer_size += self.__data_type_size[dtype] * len(data)
        if total_buffer_size > self.max_sample_number:
            raise IMDisturbanceError(
                "Number of samples is too high. "
                "Demanded size: {} bytes, buffer max size: {} bytes.".format(
                    total_buffer_size, self.max_sample_number
                )
            )
        self.logger.debug(
            "Demanded size: %d bytes, buffer max size: %d bytes.",
            total_buffer_size,
            self.max_sample_number,
        )
