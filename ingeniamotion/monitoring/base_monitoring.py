import struct
import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple, Union

import ingenialogger
import numpy as np
from ingenialink.enums.register import REG_DTYPE, RegCyclicType

from ingeniamotion.enums import (
    MonitoringProcessStage,
    MonitoringSoCConfig,
    MonitoringSoCType,
    MonitoringVersion,
)
from ingeniamotion.exceptions import IMMonitoringError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


def check_monitoring_disabled(func: Callable[..., None]) -> Callable[..., None]:
    @wraps(func)
    def wrapper(self, *args, **kwargs):  # type: ignore
        monitoring_enabled = self.mc.capture.is_monitoring_enabled(servo=self.servo)
        if monitoring_enabled:
            raise IMMonitoringError("Monitoring is enabled")
        return func(self, *args, **kwargs)

    return wrapper


class Monitoring(ABC):
    """Class to configure a monitoring in a servo.

    Args:
        mc (MotionController): MotionController instance.
        servo (str): servo alias to reference it. ``default`` by default.

    """

    REGISTER_MAP_OFFSET = 0x800
    ESTIMATED_MAX_TIME_FOR_SAMPLE = 0.003

    _data_type_size = {
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

    MONITORING_FREQUENCY_DIVIDER_REGISTER = "MON_DIST_FREQ_DIV"
    MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER = "MON_CFG_TOTAL_MAP"
    MONITOR_START_CONDITION_TYPE_REGISTER = "MON_CFG_SOC_TYPE"
    MONITORING_INDEX_CHECKER_REGISTER = "MON_IDX_CHECK"
    MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER = "MON_CFG_TRIGGER_DELAY"
    MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER = "MON_CFG_WINDOW_SAMP"
    MONITORING_ACTUAL_NUMBER_SAMPLES_REGISTER = "MON_CFG_CYCLES_VALUE"
    MONITORING_FORCE_TRIGGER_REGISTER = "MON_CMD_FORCE_TRIGGER"

    def __init__(self, mc: "MotionController", servo: str = DEFAULT_SERVO) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers: List[Dict[str, Union[int, str, REG_DTYPE]]] = []
        self.sampling_freq: Optional[float] = None
        self._read_process_finished = False
        self.samples_number = 0
        self.trigger_delay_samples = 0
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.max_sample_number = mc.capture.monitoring_max_sample_size(servo)
        self.data = None
        self._version: Optional[MonitoringVersion] = None

    @check_monitoring_disabled
    def set_frequency(self, prescaler: int) -> None:
        """Function to define monitoring frequency with a prescaler. Frequency will be
        ``Position & velocity loop rate frequency / prescaler``, see
        :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
        to know about this frequency. Monitoring must be disabled.

        Args:
            prescaler : determines monitoring frequency.
                It must be ``1`` or higher.

        Raises:
            ValueError: If prescaler is less than ``1``.

        """
        if prescaler < 1:
            raise ValueError("prescaler must be 1 or higher")
        position_velocity_loop_rate = self.mc.configuration.get_position_and_velocity_loop_rate(
            servo=self.servo, axis=DEFAULT_AXIS
        )
        self.sampling_freq = round(position_velocity_loop_rate / prescaler, 2)
        self.mc.communication.set_register(
            self.MONITORING_FREQUENCY_DIVIDER_REGISTER, prescaler, servo=self.servo, axis=0
        )

    @check_monitoring_disabled
    def map_registers(self, registers: List[Dict[str, Union[int, str, REG_DTYPE]]]) -> None:
        """Map registers to monitoring. Monitoring must be disabled.

        Args:
            registers : List of registers to map.
                Each register must be a dict with two keys:

                .. code-block:: python

                    {
                        "name": "CL_POS_FBK_VALUE",  # Register name.
                        "axis": 1  # Register axis.
                        # If it has no axis field, by default axis 1.
                    }

        Raises:
            IMMonitoringError: If register maps fails in the servo.
            IMMonitoringError: If buffer size is not enough for all the registers.
            IMMonitoringError: If any register is not CYCLIC_TX.
            TypeError: If some parameter has a wrong type.

        """
        drive = self.mc.servos[self.servo]
        drive.monitoring_remove_all_mapped_registers()

        for channel in registers:
            subnode = channel.get("axis", DEFAULT_AXIS)
            if not isinstance(subnode, int):
                raise TypeError("Subnode has to be an integer")
            register = channel["name"]
            if not isinstance(register, str):
                raise TypeError("Register has to be a string")
            register_obj = self.mc.info.register_info(register, subnode, servo=self.servo)
            if register_obj.cyclic not in [RegCyclicType.TX, RegCyclicType.TXRX]:
                raise IMMonitoringError(
                    f"{register} can not be mapped as a monitoring register (wrong cyclic)"
                )
            dtype = register_obj.dtype
            channel["dtype"] = dtype

        self._check_buffer_size_is_enough(
            self.samples_number, self.trigger_delay_samples, registers
        )

        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", DEFAULT_AXIS)
            if not isinstance(subnode, int):
                raise TypeError("Subnode has to be an integer")
            register = channel["name"]
            if not isinstance(register, str):
                raise TypeError("Register has to be a string")
            if not isinstance(channel["dtype"], REG_DTYPE):
                raise TypeError("dtype has to be of type REG_DTYPE")
            dtype = channel["dtype"]
            register_obj = self.mc.info.register_info(register, subnode, servo=self.servo)
            drive.monitoring_set_mapped_register(
                ch_idx,
                register_obj.mapped_address,
                subnode,
                dtype.value,
                self._data_type_size[dtype],
            )

        num_mon_reg = self.mc.communication.get_register(
            self.MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER, servo=self.servo, axis=0
        )
        if not isinstance(num_mon_reg, int):
            raise TypeError("Number of mapped registers value has to be an integer")
        if num_mon_reg < 1:
            raise IMMonitoringError("Map Monitoring registers fails")
        self.mapped_registers = registers

    @abstractmethod
    @check_monitoring_disabled
    def set_trigger(
        self,
        trigger_mode: MonitoringSoCType,
        edge_condition: Optional[MonitoringSoCConfig] = None,
        trigger_signal: Optional[Dict[str, Union[int, str]]] = None,
        trigger_value: Union[None, int, float] = None,
    ) -> None:
        """Configure monitoring trigger. Monitoring must be disabled.

        Args:
            trigger_mode : monitoring start of condition type.
            edge_condition : edge event type. ``None`` by default.
            trigger_signal : dict with name and axis of trigger signal
                for rising or falling edge trigger. ``None`` by default.
            trigger_value : value for rising or falling edge trigger.
                ``None`` by default.

        Raises:
            TypeError: If trigger_mode is trigger event edge and
                edge_condition, trigger_signal or trigger_value are None.
            IMMonitoringError: If trigger signal is not mapped.

        """
        pass

    def _get_reg_index_and_edge_condition_value(
        self, trigger_signal: Dict[str, str], trigger_value: Union[int, float]
    ) -> Tuple[int, int]:
        index_reg = -1
        for index, item in enumerate(self.mapped_registers):
            if (
                trigger_signal["name"] == item["name"]
                and trigger_signal.get("axis", DEFAULT_AXIS) == item["axis"]
            ):
                index_reg = index
        if index_reg < 0:
            raise IMMonitoringError("Trigger signal is not mapped in Monitoring")
        dtype = self.mapped_registers[index_reg]["dtype"]
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError("dtype has to be of type REG_DTYPE")
        level_edge = self._unpack_trigger_value(trigger_value, dtype)
        return index_reg, level_edge

    @staticmethod
    def _unpack_trigger_value(value: Union[int, float], dtype: REG_DTYPE) -> int:
        """Converts any value from its dtype to an UINT32"""
        if dtype == REG_DTYPE.U16:
            return int(np.array([int(value)], dtype="int64").astype("uint16")[0])
        if dtype == REG_DTYPE.U32:
            return int(struct.unpack("L", struct.pack("I", int(value)))[0])
        if dtype == REG_DTYPE.S32:
            if value < 0:
                return int(value + (1 << 32))
            return int(np.array([int(value)], dtype="int64").astype("int32")[0])
        return int(struct.unpack("L", struct.pack("f", value))[0])

    @abstractmethod
    @check_monitoring_disabled
    def configure_number_samples(self, total_num_samples: int, trigger_delay_samples: int) -> None:
        """Configure monitoring number of samples. Monitoring must be disabled.

        Args:
            total_num_samples : monitoring total number of samples.
            trigger_delay_samples : monitoring number of samples before trigger.
                It should be less than total_num_samples. Minimum ``0``.

        Raises:
            ValueError: If trigger_delay_samples is less than ``0``
                or higher than total_num_samples.
            IMMonitoringError: If buffer size is not enough for all the samples.

        """
        pass

    @check_monitoring_disabled
    def configure_sample_time(self, total_time: float, trigger_delay: float) -> None:
        """Configure monitoring number of samples defines by sample and trigger
        delay time. Monitoring must be disabled.

        Args:
            total_time : monitoring sample total time, in seconds.
            trigger_delay : trigger delay in seconds. Value should be
                between ``-total_time/2`` and  ``total_time/2``.

        Raises:
            ValueError: If trigger_delay is not between ``-total_time/2`` and
                ``total_time/2``.
            IMMonitoringError: If buffer size is not enough for all the samples.
            TypeError: If some parameter has a wrong type.

        """
        if total_time / 2 < abs(trigger_delay):
            raise ValueError("trigger_delay value should be between -total_time/2 and total_time/2")
        if not isinstance(self.sampling_freq, float):
            raise TypeError("Sampling frequency has to be set before configuring the sample time")
        total_num_samples = int(self.sampling_freq * total_time)
        trigger_delay_samples = int(((total_time / 2) - trigger_delay) * self.sampling_freq)
        self.configure_number_samples(total_num_samples, trigger_delay_samples)

    def _check_trigger_timeout(self, init_time: float, timeout: Optional[float]) -> None:
        if timeout is None:
            return
        time_now = time.time()
        if init_time + timeout < time_now:
            self.logger.warning("Timeout. No trigger was reached.")
            self._read_process_finished = True

    def _check_read_data_timeout(self, init_read_time: float) -> None:
        time_now = time.time()
        total_num_samples = len(self.mapped_registers) * self.samples_number
        max_timeout = self.ESTIMATED_MAX_TIME_FOR_SAMPLE * total_num_samples
        if init_read_time + max_timeout < time_now:
            self.logger.warning("Timeout. Drive take too much time reading data")
            self._read_process_finished = True

    def _check_read_data_ends(self, data_length: int) -> None:
        if data_length >= self.samples_number:
            self._read_process_finished = True

    def _update_read_process_finished(
        self,
        init_read_time: Optional[float],
        current_len: int,
        init_time: float,
        timeout: Optional[float],
    ) -> None:
        self._check_read_data_ends(current_len)
        if self._read_process_finished:
            return
        if init_read_time is None:
            self._check_trigger_timeout(init_time, timeout)
        else:
            self._check_read_data_timeout(init_read_time)

    def _show_current_process(
        self,
        current_len: int,
        progress_callback: Optional[Callable[[MonitoringProcessStage, float], None]],
    ) -> None:
        process_stage = self.mc.capture.get_monitoring_process_stage(
            servo=self.servo, version=self._version
        )
        current_progress = current_len / self.samples_number
        if process_stage in [
            MonitoringProcessStage.DATA_ACQUISITION,
            MonitoringProcessStage.END_STAGE,
        ]:
            self.logger.debug("Read %.2f%% of monitoring data", current_progress * 100)
        if progress_callback is not None:
            progress_callback(process_stage, current_progress)

    @abstractmethod
    def _check_monitoring_is_ready(self) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def _check_data_is_ready(self) -> bool:
        pass

    # TODO Study remove progress_callback
    def read_monitoring_data(
        self,
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[MonitoringProcessStage, float], None]] = None,
    ) -> List[List[Union[int, float]]]:
        """Blocking function that read the monitoring data.

        Args:
            timeout : maximum time trigger is waited, in seconds.
                ``None`` by default.

        Returns:
            Data of monitoring. Each element of the list is a different register data.

        """
        drive = self.mc.servos[self.servo]
        self._read_process_finished = False
        is_ready, result_text = self._check_monitoring_is_ready()
        data_array: List[List[Union[int, float]]] = [[] for _ in self.mapped_registers]
        self.logger.debug("Waiting for data")
        init_read_time, init_time = None, time.time()
        current_len = 0
        while not self._read_process_finished:
            if self._check_data_is_ready():
                init_read_time = init_read_time or time.time()
                drive.monitoring_read_data()
                self._fill_data(data_array)
                current_len = len(data_array[0])
            elif not is_ready:
                self.logger.warning(result_text)
                self._read_process_finished = True
            self._update_read_process_finished(init_read_time, current_len, init_time, timeout)
            self._show_current_process(current_len, progress_callback)
        return data_array

    def _fill_data(self, data_array: List[List[Union[int, float]]]) -> None:
        drive = self.mc.servos[self.servo]
        for ch_idx, channel in enumerate(self.mapped_registers):
            dtype = channel["dtype"]
            tmp_monitor_data = drive.monitoring_channel_data(ch_idx, REG_DTYPE(dtype))
            data_array[ch_idx] += tmp_monitor_data

    def stop_reading_data(self) -> None:
        """Stops read_monitoring_data function."""
        self._read_process_finished = True

    @abstractmethod
    def rearm_monitoring(self) -> None:
        """Rearm monitoring."""
        pass

    @abstractmethod
    def _check_buffer_size_is_enough(
        self,
        total_samples: int,
        trigger_delay_samples: int,
        registers: List[Dict[str, Union[int, str, REG_DTYPE]]],
    ) -> None:
        pass

    def _check_samples_and_max_size(
        self, n_sample: int, max_size: int, registers: List[Dict[str, Union[int, str, REG_DTYPE]]]
    ) -> None:
        size_demand = sum(
            self._data_type_size[register["dtype"]] * n_sample
            for register in registers
            if isinstance(register["dtype"], REG_DTYPE)
        )
        if max_size < size_demand:
            raise IMMonitoringError(
                "Number of samples is too high or mapped registers are too big. "
                "Demanded size: {} bytes, buffer max size: {} bytes.".format(size_demand, max_size)
            )
        self.logger.debug(
            "Demanded size: %d bytes, buffer max size: %d bytes.", size_demand, max_size
        )

    def get_trigger_type(self) -> Union[MonitoringSoCType, int]:
        """Get monitoring trigger type.

        Returns:
            Trigger type

        Raises:
            TypeError: If some read value has a wrong type.

        """
        register_value = self.mc.communication.get_register(
            self.MONITOR_START_CONDITION_TYPE_REGISTER, servo=self.servo, axis=0
        )
        if not isinstance(register_value, int):
            raise TypeError("Monitoring trigger type register value has to be an integer")
        try:
            return MonitoringSoCType(register_value)
        except ValueError:
            return register_value

    def raise_forced_trigger(self, blocking: bool = False, timeout: float = 5) -> bool:
        """Raise trigger for Forced Trigger type.

        Args:
            blocking : if ``True``, functions wait until trigger is forced
                (or until the timeout) If ``False``, function try to raise the
                trigger only once.
            timeout : blocking timeout in seconds. ``5`` by default.

        Returns:
            Return ``True`` if trigger is raised, else ``False``.

        """
        trigger_mode = self.get_trigger_type()
        if trigger_mode != MonitoringSoCType.TRIGGER_EVENT_FORCED:
            raise IMMonitoringError("Monitoring trigger type is not Forced Trigger")
        mon_process_stage = None
        final_time = time.time() + timeout
        while mon_process_stage is None or (
            blocking
            and final_time > time.time()
            and mon_process_stage != MonitoringProcessStage.WAITING_FOR_TRIGGER
        ):
            mon_process_stage = self.mc.capture.get_monitoring_process_stage(
                servo=self.servo, version=self._version
            )
            self.mc.communication.set_register(
                self.MONITORING_FORCE_TRIGGER_REGISTER, 1, servo=self.servo, axis=0
            )
        return mon_process_stage >= MonitoringProcessStage.WAITING_FOR_TRIGGER

    def read_monitoring_data_forced_trigger(
        self, trigger_timeout: float = 5
    ) -> List[List[Union[int, float]]]:
        """Trigger and read Forced Trigger monitoring.

        Args:
            trigger_timeout : maximum time function wait to raise the trigger,
                in seconds. ``5`` by default.

        Returns:
            Data of monitoring. Each element of the list is a different register data.

        """
        is_triggered = self.raise_forced_trigger(blocking=True, timeout=trigger_timeout)
        if not is_triggered:
            self.logger.warning("Timeout. Forced trigger is not raised.")
            return [[] for _ in self.mapped_registers]
        return self.read_monitoring_data()
