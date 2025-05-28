from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, Union

import ingenialogger
import numpy as np
from ingenialink.enums.register import RegDtype
from ingenialink.exceptions import ILValueError
from numpy import ndarray
from numpy.typing import NDArray

from ingeniamotion.enums import MonitoringVersion
from ingeniamotion.exceptions import IMDisturbanceError, IMStatusWordError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

# Constants for typing
TYPE_MAPPED_REGISTERS_ALL = dict[str, Union[str, int, list[float]]]
TYPE_MAPPED_REGISTERS_NAME_AXIS = dict[str, Union[str, int, RegDtype]]
TYPE_MAPPED_REGISTERS_DATA = dict[str, list[Union[int, float]]]
TYPE_MAPPED_REGISTERS_DATA_NO_KEY = list[Union[int, float]]


def check_disturbance_disabled(
    func: Callable[..., Union[int, float, None]],
) -> Callable[..., Union[int, float, None]]:
    """Decorator that checks if disturbance is disabled before calling a function.

    Args:
        func: The function to called.

    Returns:
        The decorated function.

    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def]
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

    MONITORING_STATUS_ENABLED_BIT = 0x1
    REGISTER_MAP_OFFSET = 0x800

    __data_type_size = {
        RegDtype.U8: 1,
        RegDtype.S8: 1,
        RegDtype.U16: 2,
        RegDtype.S16: 2,
        RegDtype.U32: 4,
        RegDtype.S32: 4,
        RegDtype.U64: 8,
        RegDtype.S64: 8,
        RegDtype.FLOAT: 4,
    }

    def __init__(self, mc: "MotionController", servo: str = DEFAULT_SERVO) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers: list[TYPE_MAPPED_REGISTERS_NAME_AXIS] = []
        self.sampling_freq: Optional[float] = None
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
        """Function to define disturbance frequency with a prescaler.

        Frequency will be
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
    def map_registers(
        self,
        registers: Union[TYPE_MAPPED_REGISTERS_NAME_AXIS, list[TYPE_MAPPED_REGISTERS_NAME_AXIS]],
    ) -> float:
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
            IMDisturbanceError: If the registers is an empty list.
            IMDisturbanceError: If the register is not allowed to be mapped as
                a disturbance register.
            TypeError: If some parameter has a wrong type.
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
            if not isinstance(subnode, int):
                raise TypeError("Subnode value has to be an integer")
            register = channel["name"]
            if not isinstance(register, str):
                raise TypeError("Register key has to be a string")
            register_obj = self.mc.info.register_info(register, subnode, servo=self.servo)
            dtype = register_obj.dtype
            if register_obj.monitoring is None:
                drive.disturbance_remove_all_mapped_registers()
                raise IMDisturbanceError(f"{register} can not be mapped as a disturbance register")
            channel["dtype"] = dtype
            drive.disturbance_set_mapped_register(
                channel=ch_idx, uid=register, size=self.__data_type_size[dtype], axis=subnode
            )
            self.mapped_registers.append(channel)
            total_sample_size += self.__data_type_size[dtype]
        return self.max_sample_number / total_sample_size

    @staticmethod
    def __registers_data_adapter(
        registers_data: Union[
            list[
                Union[
                    int,
                    float,
                    NDArray[np.int32],
                    NDArray[np.float32],
                    TYPE_MAPPED_REGISTERS_DATA_NO_KEY,
                ]
            ],
            NDArray[np.int32],
            NDArray[np.float32],
        ],
    ) -> list[TYPE_MAPPED_REGISTERS_DATA_NO_KEY]:
        if isinstance(registers_data, ndarray):
            registers_data = registers_data.tolist()
            return [registers_data]  # type: ignore [list-item]
        elif isinstance(registers_data, list) and all(
            isinstance(data, list) for data in registers_data
        ):
            return registers_data  # type: ignore [return-value]
        elif isinstance(registers_data, list) and all(
            isinstance(data, (int, float)) for data in registers_data
        ):
            return [registers_data]  # type: ignore [list-item]
        elif isinstance(registers_data, list) and all(
            isinstance(data, ndarray) for data in registers_data
        ):
            for i, x in enumerate(registers_data):
                if isinstance(x, ndarray):
                    registers_data[i] = x.tolist()
            return registers_data  # type: ignore [return-value]
        else:
            raise TypeError(
                "Registers data adapter doesn't have the correct type for its input argument"
            )

    @check_disturbance_disabled
    def write_disturbance_data(
        self,
        registers_data: Union[
            list[
                Union[
                    int,
                    float,
                    NDArray[np.int32],
                    NDArray[np.float32],
                    TYPE_MAPPED_REGISTERS_DATA_NO_KEY,
                ]
            ],
            NDArray[np.int32],
            NDArray[np.float32],
        ],
    ) -> None:
        """Write data in mapped registers. Disturbance must be disabled.

        Args:
            registers_data :
                data to write in disturbance. Registers should have same order
                as in :func:`map_registers`.

        Raises:
            IMDisturbanceError: If there are no mapped registers or the sampling frequency is not
                set yet.
            IMDisturbanceError: If buffer size is not enough for all the
                registers and samples.
        """
        if len(self.mapped_registers) == 0 or self.sampling_freq is None:
            raise IMDisturbanceError("Disturbance is not correctly configured yet")
        adapted_registers_data = self.__registers_data_adapter(registers_data)
        drive = self.mc.servos[self.servo]
        self.__check_buffer_size_is_enough(adapted_registers_data)
        idx_list = list(range(len(adapted_registers_data)))
        dtype_list = [RegDtype(x["dtype"]) for x in self.mapped_registers]
        if self._version >= MonitoringVersion.MONITORING_V3:
            drive.disturbance_remove_data()
        try:
            drive.disturbance_write_data(idx_list, dtype_list, adapted_registers_data)
        except ILValueError as e:
            raise IMDisturbanceError(e)

    def map_registers_and_write_data(
        self, registers: Union[TYPE_MAPPED_REGISTERS_ALL, list[TYPE_MAPPED_REGISTERS_ALL]]
    ) -> None:
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

    def __check_buffer_size_is_enough(
        self, registers: list[TYPE_MAPPED_REGISTERS_DATA_NO_KEY]
    ) -> None:
        total_buffer_size = 0
        for ch_idx, data in enumerate(registers):
            dtype = self.mapped_registers[ch_idx]["dtype"]
            if not isinstance(dtype, RegDtype):
                continue
            total_buffer_size += self.__data_type_size[dtype] * len(data)
        if total_buffer_size > self.max_sample_number:
            raise IMDisturbanceError(
                "Number of samples is too high. "
                f"Demanded size: {total_buffer_size} bytes, "
                f"buffer max size: {self.max_sample_number} bytes."
            )
        self.logger.debug(
            "Demanded size: %d bytes, buffer max size: %d bytes.",
            total_buffer_size,
            self.max_sample_number,
        )
