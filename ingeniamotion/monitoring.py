import time
import struct
import numpy as np
import ingenialogger
from enum import IntEnum
from functools import wraps
from ingenialink import REG_DTYPE
from ingenialink.exceptions import ILError

from .metaclass import DEFAULT_SERVO, DEFAULT_AXIS
from .exceptions import IMMonitoringError, IMStatusWordError
from ingeniamotion.enums import MonitoringVersion, MonitoringProcessStage


def check_monitoring_disabled(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        monitoring_enabled = self.mc.capture.is_monitoring_enabled(
            servo=self.servo)
        if monitoring_enabled:
            raise IMMonitoringError("Monitoring is enabled")
        return func(self, *args, **kwargs)

    return wrapper


class MonitoringSoCType(IntEnum):
    """Monitoring start of condition type"""
    TRIGGER_EVENT_NONE = 0
    """No trigger"""
    TRIGGER_EVENT_FORCED = 1
    """Forced trigger"""
    TRIGGER_CYCLIC_RISING_EDGE = 2
    """Rising edge trigger"""
    TRIGGER_NUMBER_SAMPLES = 3
    TRIGGER_CYCLIC_FALLING_EDGE = 4
    """Falling edge trigger"""


class Monitoring:
    """Class to configure a monitoring in a servo.

    Args:
        mc (MotionController): MotionController instance.
        servo (str): servo alias to reference it. ``default`` by default.
    
    """

    EOC_TRIGGER_NUMBER_SAMPLES = 3

    EDGE_CONDITION_REGISTER = {
        MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE: "MON_CFG_RISING_CONDITION",
        MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE: "MON_CFG_FALLING_CONDITION"
    }

    REGISTER_MAP_OFFSET = 0x800

    MINIMUM_BUFFER_SIZE = 8192

    ESTIMATED_MAX_TIME_FOR_SAMPLE = 0.0015

    __data_type_size = {
        REG_DTYPE.U8: 1,
        REG_DTYPE.S8: 1,
        REG_DTYPE.U16: 2,
        REG_DTYPE.S16: 2,
        REG_DTYPE.U32: 4,
        REG_DTYPE.S32: 4,
        REG_DTYPE.U64: 8,
        REG_DTYPE.S64: 8,
        REG_DTYPE.FLOAT: 4
    }

    MONITORING_FREQUENCY_DIVIDER_REGISTER = "MON_DIST_FREQ_DIV"
    MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER = "MON_CFG_TOTAL_MAP"
    MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER = "MON_CFG_TRIGGER_REPETITIONS"
    MONITOR_START_CONDITION_TYPE_REGISTER = "MON_CFG_SOC_TYPE"
    MONITOR_END_CONDITION_TYPE_REGISTER = "MON_CFG_EOC_TYPE"
    MONITORING_INDEX_CHECKER_REGISTER = "MON_IDX_CHECK"
    MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER = "MON_CFG_TRIGGER_DELAY"
    MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER = "MON_CFG_WINDOW_SAMP"
    MONITORING_ACTUAL_NUMBER_SAMPLES_REGISTER = "MON_CFG_CYCLES_VALUE"
    MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER = "MON_MAX_SIZE"
    MONITORING_FORCE_TRIGGER_REGISTER = "MON_CMD_FORCE_TRIGGER"

    def __init__(self, mc, servo=DEFAULT_SERVO):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers = {}
        self.monitoring_data = []
        self.sampling_freq = None
        self.__version = mc.capture._check_version(servo)
        self.__read_process_finished = False
        self.samples_number = 0
        self.trigger_delay_samples = 0
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.max_sample_number = self.get_max_sample_size()
        self.data = None
        if self.__version < MonitoringVersion.MONITORING_V3:
            try:
                self.mc.capture.mcb_synchronization(servo=servo)
            except IMStatusWordError:
                self.logger.warning("MCB could not be synchronized. Motor is enabled.",
                                    drive=mc.servo_name(servo))

    @check_monitoring_disabled
    def set_frequency(self, prescaler):
        """Function to define monitoring frequency with a prescaler. Frequency will be
        ``Position & velocity loop rate frequency / prescaler``, see
        :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
        to know about this frequency. Monitoring must be disabled.

        Args:
            prescaler (int): determines monitoring frequency.
                It must be ``1`` or higher.

        Raises:
            ValueError: If prescaler is less than ``1``.

        """
        if prescaler < 1:
            raise ValueError("prescaler must be 1 or higher")
        position_velocity_loop_rate = \
            self.mc.configuration.get_position_and_velocity_loop_rate(
                servo=self.servo,
                axis=DEFAULT_AXIS
            )
        self.sampling_freq = round(position_velocity_loop_rate / prescaler, 2)
        self.mc.communication.set_register(
            self.MONITORING_FREQUENCY_DIVIDER_REGISTER,
            prescaler,
            servo=self.servo,
            axis=0
        )

    @check_monitoring_disabled
    def map_registers(self, registers):
        """Map registers to monitoring. Monitoring must be disabled.

        Args:
            registers (list of dict): List of registers to map.
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

        """
        drive = self.mc.servos[self.servo]
        drive.monitoring_remove_all_mapped_registers()

        for channel in registers:
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            register_obj = self.mc.info.register_info(
                register, subnode, servo=self.servo)
            dtype = register_obj.dtype
            channel["dtype"] = dtype

        self.__check_buffer_size_is_enough(self.samples_number,
                                           self.trigger_delay_samples, registers)

        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            dtype = channel["dtype"]
            address_offset = self.REGISTER_MAP_OFFSET * (subnode - 1)
            register_obj = self.mc.info.register_info(
                register, subnode, servo=self.servo)
            mapped_reg = register_obj.address + address_offset
            drive.monitoring_set_mapped_register(ch_idx, mapped_reg,
                                                 subnode, dtype.value,
                                                 self.__data_type_size[dtype])

        num_mon_reg = self.mc.communication.get_register(
            self.MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER,
            servo=self.servo,
            axis=0
        )
        if num_mon_reg < 1:
            raise IMMonitoringError("Map Monitoring registers fails")
        self.mapped_registers = registers

    @check_monitoring_disabled
    def set_trigger(self, trigger_mode, trigger_signal=None, trigger_value=None):
        """Configure monitoring trigger. Monitoring must be disabled.

        Args:
            trigger_mode (MonitoringSoCType): monitoring start of condition type.
            trigger_signal (dict): dict with name and axis of trigger signal
                for rising or falling edge trigger.
            trigger_value (int or float): value for rising or falling edge trigger.

        Raises:
            TypeError: If trigger_mode is rising or falling edge trigger and
                trigger_signal or trigger_value are None.
            IMMonitoringError: If trigger signal is not mapped.

        """
        self.reset_trigger_repetitions()
        self.mc.communication.set_register(
            self.MONITOR_START_CONDITION_TYPE_REGISTER,
            trigger_mode,
            servo=self.servo,
            axis=0
        )
        if trigger_mode in \
                [MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE,
                 MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE]:
            if trigger_signal is None or trigger_value is None:
                raise TypeError("trigger_signal or trigger_value are None")
            self.__rising_or_falling_edge_trigger(trigger_mode, trigger_signal,
                                                  trigger_value)

    def __rising_or_falling_edge_trigger(self, trigger_mode, trigger_signal,
                                         trigger_value):
        index_reg = -1
        for index, item in enumerate(self.mapped_registers):
            if (trigger_signal["name"] == item["name"] and
                    trigger_signal.get("axis", DEFAULT_AXIS) == item["axis"]):
                index_reg = index
        if index_reg < 0:
            raise IMMonitoringError("Trigger signal is not mapped in Monitoring")
        dtype = self.mapped_registers[index_reg]["dtype"]
        level_edge = self.__unpack_trigger_value(trigger_value, dtype)
        self.mc.communication.set_register(
            self.EDGE_CONDITION_REGISTER[trigger_mode],
            level_edge,
            servo=self.servo,
            axis=0
        )
        self.mc.communication.set_register(
            self.MONITORING_INDEX_CHECKER_REGISTER,
            index_reg,
            servo=self.servo,
            axis=0
        )

    @staticmethod
    def __unpack_trigger_value(value, dtype):
        """Converts any value from its dtype to an UINT32"""
        if dtype == REG_DTYPE.U16:
            return int(np.array([int(value)], dtype='int64').astype('uint16')[0])
        if dtype == REG_DTYPE.U32:
            return int(struct.unpack('L', struct.pack('I', int(value)))[0])
        if dtype == REG_DTYPE.S32:
            if value < 0:
                return int(value + (1 << 32))
            return int(np.array([int(value)], dtype='int64').astype('int32')[0])
        return int(struct.unpack('L', struct.pack('f', value))[0])

    @check_monitoring_disabled
    def configure_number_samples(self, total_num_samples, trigger_delay_samples):
        """Configure monitoring number of samples. Monitoring must be disabled.

        Args:
            total_num_samples (int): monitoring total number of samples.
            trigger_delay_samples (int): monitoring number of samples before trigger.
                It should be less than total_num_samples. Minimum ``1``.

        Raises:
            ValueError: If trigger_delay_samples is less than ``1``
                or higher than total_num_samples.
            IMMonitoringError: If buffer size is not enough for all the samples.

        """
        if trigger_delay_samples >= total_num_samples:
            raise ValueError("trigger_delay_samples should be less"
                             " than total_num_samples")
        if trigger_delay_samples < 1:
            raise ValueError("trigger_delay_samples should be minimum 1")
        self.__check_buffer_size_is_enough(total_num_samples, trigger_delay_samples,
                                           self.mapped_registers)

        self.samples_number = total_num_samples
        self.trigger_delay_samples = trigger_delay_samples

        if self.__version == MonitoringVersion.MONITORING_V3:
            window_samples = total_num_samples
        else:
            window_samples = total_num_samples - trigger_delay_samples
            self.mc.communication.set_register(
                self.MONITOR_END_CONDITION_TYPE_REGISTER,
                self.EOC_TRIGGER_NUMBER_SAMPLES,
                servo=self.servo,
                axis=0
            )

        self.mc.communication.set_register(
            self.MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER,
            trigger_delay_samples,
            servo=self.servo,
            axis=0
        )
        self.mc.communication.set_register(
            self.MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER,
            window_samples,
            servo=self.servo,
            axis=0
        )

    @check_monitoring_disabled
    def configure_sample_time(self, total_time, trigger_delay):
        """Configure monitoring number of samples defines by sample and trigger
        delay time. Monitoring must be disabled.

        Args:
            total_time (float): monitoring sample total time, in seconds.
            trigger_delay (float): trigger delay in seconds. Value should be
                between ``-total_time/2`` and  ``total_time/2``.

        Raises:
            ValueError: If trigger_delay is not between ``-total_time/2`` and
                ``total_time/2``.
            IMMonitoringError: If buffer size is not enough for all the samples.

        """
        if total_time / 2 < abs(trigger_delay):
            raise ValueError("trigger_delay value should be between"
                             " -total_time/2 and total_time/2")
        total_num_samples = int(self.sampling_freq * total_time)
        trigger_delay_samples = int(((total_time / 2) - trigger_delay)
                                    * self.sampling_freq)
        trigger_delay_samples = trigger_delay_samples if trigger_delay_samples > 0 else 1
        self.configure_number_samples(total_num_samples, trigger_delay_samples)

    def __update_read_process_finished(self, init_read_time, data_length,
                                       init_time, timeout):
        time_now = time.time()
        if data_length >= self.samples_number:
            self.__read_process_finished = True
        total_num_samples = len(self.mapped_registers) * self.samples_number
        max_timeout = self.ESTIMATED_MAX_TIME_FOR_SAMPLE * total_num_samples
        exist_read_time = init_read_time is not None
        if exist_read_time and init_read_time + max_timeout < time_now:
            self.logger.warning("Timeout. Drive take too match time reading data")
            self.__read_process_finished = True
        if not exist_read_time and timeout is not None and init_time+timeout < time_now:
            self.logger.warning("Timeout. No trigger was reached.")
            self.__read_process_finished = True

    def __show_current_process(self, current_len, progress_callback):
        current_progress = current_len / self.samples_number
        self.logger.debug("Read %.2f%% of monitoring data",
                          current_progress * 100)
        if progress_callback is not None:
            progress_callback(current_progress)

    def __check_monitoring_is_ready(self):
        is_enabled = self.mc.capture.is_monitoring_enabled(self.servo)
        result_text = ""
        if self.__version < MonitoringVersion.MONITORING_V3:
            trigger_repetitions = self.mc.communication.get_register(
                self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER,
                servo=self.servo,
                axis=0
            )
            is_ready = is_enabled and trigger_repetitions != 0
            not_ready_text = "MON_CFG_TRIGGER_REPETITIONS is {}".format(
                trigger_repetitions)
        else:
            monitoring_stage = self.mc.capture.get_monitoring_process_stage(
                self.servo, self.__version)
            is_ready = (is_enabled and
                        monitoring_stage != MonitoringProcessStage.INIT_STAGE)
            not_ready_text = "Monitoring stage is {}".format(monitoring_stage.name)

        if not is_ready:
            text_is_enabled = "enabled" if is_enabled else "disabled"
            result_text = ("Can't read monitoring data because monitoring is not ready."
                           " {}. Monitoring is {}."
                           .format(not_ready_text, text_is_enabled))
        return is_ready, result_text

    # TODO Study remove progress_callback
    def read_monitoring_data(self, timeout=None, progress_callback=None):
        """Blocking function that read the monitoring data.

        Args:
            timeout (float): maximum time trigger is waited, in seconds.
                ``None`` by default.

        Returns:
            list of list: data of monitoring. Each element of the list is a
            different register data.

        """
        drive = self.mc.servos[self.servo]
        self.__read_process_finished = False
        is_ready, result_text = self.__check_monitoring_is_ready()
        data_array = [[] for _ in self.mapped_registers]
        self.logger.debug("Waiting for data")
        init_read_time, init_time = None, time.time()
        current_len = 0
        while not self.__read_process_finished:
            if self.__check_data_is_ready():
                drive.monitoring_read_data()
                self.__fill_data(data_array)
                if init_read_time is None:
                    init_read_time = time.time()
                current_len = len(data_array[0])
                self.__show_current_process(current_len, progress_callback)
            elif not is_ready:
                self.logger.warning(result_text)
                self.__read_process_finished = True
            self.__update_read_process_finished(init_read_time, current_len,
                                                init_time, timeout)
        if self.__version >= MonitoringVersion.MONITORING_V3:
            drive.monitoring_remove_data()
        return data_array

    def __fill_data(self, data_array):
        drive = self.mc.servos[self.servo]
        for ch_idx, channel in enumerate(self.mapped_registers):
            dtype = channel["dtype"]
            tmp_monitor_data = drive.monitoring_channel_data(ch_idx, REG_DTYPE(dtype))
            data_array[ch_idx] += tmp_monitor_data

    def __check_data_is_ready(self):
        monit_nmb_blocks = self.mc.communication.get_register(
            self.MONITORING_ACTUAL_NUMBER_SAMPLES_REGISTER,
            servo=self.servo,
            axis=0
        )
        data_is_ready = monit_nmb_blocks > 0
        if self.__version >= MonitoringVersion.MONITORING_V2:
            data_is_ready &= self.mc.capture.is_frame_available(
                self.servo, version=self.__version)
        return data_is_ready

    def get_monitoring_process_stage(self):
        """(Deprecated) Return monitoring process stage.

        Returns:
            MonitoringProcessStage: Current monitoring process stage.

        """
        return self.mc.capture.get_monitoring_process_stage(self.servo, self.__version)

    def is_frame_available(self):
        """(Deprecated) Check if monitoring has an available frame.

        Returns:
            bool: True if monitoring has an available frame, else False.

        """
        return self.mc.capture.is_frame_available(self.servo, self.__version)

    def stop_reading_data(self):
        """Stops read_monitoring_data function."""
        self.__read_process_finished = True

    def reset_trigger_repetitions(self):
        """Reset trigger repetitions to target value."""
        self.mc.communication.set_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER,
            1,
            servo=self.servo,
            axis=0
        )

    def get_max_sample_size(self):
        """Return monitoring max size, in bytes.

        Returns:
            int: Max buffer size in bytes.

        """
        try:
            return self.mc.communication.get_register(
                self.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER,
                servo=self.servo,
                axis=0
            )
        except ILError:
            return self.MINIMUM_BUFFER_SIZE

    def __check_buffer_size_is_enough(self, total_samples, trigger_delay_samples,
                                      registers):
        if self.__version < MonitoringVersion.MONITORING_V3:
            n_sample = max(total_samples - trigger_delay_samples, trigger_delay_samples)
            max_size = self.max_sample_number // 2
        else:
            n_sample = total_samples
            max_size = self.max_sample_number

        size_demand = sum(
            self.__data_type_size[register["dtype"]] * n_sample
            for register in registers
        )
        if max_size < size_demand:
            raise IMMonitoringError(
                "Number of samples is too high or mapped registers are too big. "
                "Demanded size: {} bytes, buffer max size: {} bytes."
                .format(size_demand, max_size))
        self.logger.debug("Demanded size: %d bytes, buffer max size: %d bytes.",
                          size_demand, max_size)

    def get_trigger_type(self):
        """Get monitoring trigger type.

        Returns:
            MonitoringSoCType: trigger type

        """
        register_value = self.mc.communication.get_register(
            self.MONITOR_START_CONDITION_TYPE_REGISTER,
            servo=self.servo,
            axis=0
        )
        try:
            return MonitoringSoCType(register_value)
        except ValueError:
            return register_value

    def raise_forced_trigger(self, blocking=False, timeout=5):
        """Raise trigger for Forced Trigger type.

        Args:
            blocking (bool): if ``True``, functions wait until trigger is forced
                (or until the timeout) If ``False``, function try to raise the
                trigger only once.
            timeout (float): blocking timeout in seconds. ``5`` by default.

        Returns:
            bool: Return ``True`` if trigger is raised, else ``False``.

        """
        trigger_mode = self.get_trigger_type()
        if trigger_mode != MonitoringSoCType.TRIGGER_EVENT_FORCED:
            raise IMMonitoringError("Monitoring trigger type "
                                    "is not Forced Trigger")
        mon_process_stage = None
        final_time = time.time() + timeout
        while mon_process_stage is None or (
                blocking and final_time > time.time() and
                mon_process_stage != MonitoringProcessStage.WAITING_FOR_TRIGGER):
            mon_process_stage = self.mc.capture.get_monitoring_process_stage(
                servo=self.servo, version=self.__version)
            self.mc.communication.set_register(
                self.MONITORING_FORCE_TRIGGER_REGISTER,
                1, servo=self.servo, axis=0)
        return mon_process_stage == MonitoringProcessStage.WAITING_FOR_TRIGGER

    def read_monitoring_data_forced_trigger(self, trigger_timeout=5):
        """Trigger and read Forced Trigger monitoring.

        Args:
            trigger_timeout (float): maximum time function wait to raise the trigger,
                in seconds. ``5`` by default.

        Returns:
            list of list: data of monitoring. Each element of the list is a
            different register data.

        """
        is_triggered = self.raise_forced_trigger(blocking=True, timeout=trigger_timeout)
        if not is_triggered:
            self.logger.warning("Timeout. Forced trigger is not raised.")
            return [[] for _ in self.mapped_registers]
        return self.read_monitoring_data()
