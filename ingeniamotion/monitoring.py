import struct
import numpy as np
import ingenialogger
import ingenialink as il
from functools import wraps
from ingenialink.exceptions import ILError

from enum import IntEnum

from .metaclass import DEFAULT_SERVO, DEFAULT_AXIS


def check_monitoring_disabled(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        monitoring_enabled = self.is_monitoring_enabled()
        if monitoring_enabled:
            raise MonitoringError("Monitoring is enabled")
        return func(self, *args, **kwargs)

    return wrapper


class MonitoringSoCType(IntEnum):
    """
    Monitoring start of condition type
    """
    TRIGGER_EVENT_NONE = 0
    """ No trigger """
    TRIGGER_EVENT_FORCED = 1
    """ Forced trigger """
    TRIGGER_CYCLIC_RISING_EDGE = 2
    """ Rising edge trigger """
    TRIGGER_NUMBER_SAMPLES = 3
    TRIGGER_CYCLIC_FALLING_EDGE = 4
    """ Falling edge trigger """


class MonitoringProcessStage(IntEnum):
    """
    Monitoring process stage
    """
    INIT_STAGE = 0x0
    """ Init stage """
    FILLING_DELAY_DATA = 0x2
    """ Filling delay data """
    WAITING_FOR_TRIGGER = 0x4
    """ Waiting for trigger """
    DATA_ACQUISITION = 0x6
    """ Data acquisition """


class Monitoring:
    """
    Class to configure a monitoring in a servo.

    Args:
        mc (MotionController): MotionController instance.
        servo (str): servo alias to reference it. ``default`` by default.
    """

    EOC_TRIGGER_NUMBER_SAMPLES = 3

    EDGE_CONDITION_REGISTER = {
        MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE: "MON_CFG_RISING_CONDITION",
        MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE: "MON_CFG_FALLING_CONDITION"
    }

    MONITORING_STATUS_ENABLED_BIT = 0x1
    MONITORING_STATUS_PROCESS_STAGE_BITS = 0x6
    MONITORING_AVAILABLE_FRAME_BIT = 0x800
    REGISTER_MAP_OFFSET = 0x800

    MINIMUM_BUFFER_SIZE = 8192

    class MonitoringVersion(IntEnum):
        """
        Monitoring version
        """
        # Monitoring V1 used for Everest 1.7.1 and older.
        MONITORING_V1 = 0,
        # Monitoring V2 used for Capitan and some custom low-power drivers.
        MONITORING_V2 = 1

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

    MONITORING_FREQUENCY_DIVIDER_REGISTER = "MON_DIST_FREQ_DIV"
    MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER = "MON_CFG_TOTAL_MAP"
    MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER = "MON_CFG_TRIGGER_REPETITIONS"
    MONITOR_START_CONDITION_TYPE_REGISTER = "MON_CFG_SOC_TYPE"
    MONITOR_END_CONDITION_TYPE_REGISTER = "MON_CFG_EOC_TYPE"
    MONITORING_INDEX_CHECKER_REGISTER = "MON_IDX_CHECK"
    MONITORING_DISTURBANCE_STATUS_REGISTER = "MON_DIST_STATUS"
    MONITORING_TRIGGER_DELAY_SAMPLES_REGISTER = "MON_CFG_TRIGGER_DELAY"
    MONITORING_WINDOW_NUMBER_SAMPLES_REGISTER = "MON_CFG_WINDOW_SAMP"
    MONITORING_NUMBER_CYCLES_REGISTER = "MON_CFG_CYCLES_VALUE"
    MONITORING_CURRENT_NUMBER_BYTES_REGISTER = "MON_CFG_BYTES_VALUE"
    MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER = "MON_MAX_SIZE"

    def __init__(self, mc, servo=DEFAULT_SERVO):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers = {}
        self.monitoring_data = []
        self.sampling_freq = None
        self.__version_flag = self.MonitoringVersion.MONITORING_V1
        self.__read_process_finished = False
        self.samples_number = 0
        self.trigger_delay_samples = 0
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.__check_version()
        self.max_sample_number = self.get_max_sample_size()
        self.data = None

    @check_monitoring_disabled
    def set_frequency(self, prescaler):
        """
        Function to define monitoring frequency with a prescaler. Frequency will be
        ``Position & velocity loop rate frequency / prescaler``,
        see :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate` to know about this
        frequency. Monitoring must be disabled.

        Args:
            prescaler (int): determines monitoring frequency. It must be ``1`` or higher.

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
        """
        Map registers to monitoring. Monitoring must be disabled.

        Args:
            registers (list of dict): List of registers to map.
                Each register must be a dict with two keys:

                .. code-block:: python

                    {
                        "name": "CL_POS_FBK_VALUE",  # Register name.
                        "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                    }

        Raises:
            MonitoringError: If register maps fails in the servo.
            MonitoringError: If buffer size is not enough for all the registers.
        """
        drive = self.mc.servos[self.servo]
        network = self.mc.net[self.servo]
        network.monitoring_remove_all_mapped_registers()

        for channel in registers:
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            register_obj = drive.dict.get_regs(subnode)[register]
            dtype = register_obj.dtype
            channel["dtype"] = dtype

        self.__check_buffer_size_is_enough(self.samples_number,
                                           self.trigger_delay_samples, registers)

        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", DEFAULT_AXIS)
            register = channel["name"]
            dtype = channel["dtype"]
            address_offset = self.REGISTER_MAP_OFFSET * (subnode - 1)
            register_obj = drive.dict.get_regs(subnode)[register]
            mapped_reg = register_obj.address + address_offset
            network.monitoring_set_mapped_register(ch_idx, mapped_reg, dtype.value)

        num_mon_reg = self.mc.communication.get_register(
            self.MONITORING_NUMBER_MAPPED_REGISTERS_REGISTER,
            servo=self.servo,
            axis=0
        )
        if num_mon_reg < 1:
            raise MonitoringError("Map Monitoring registers fails")
        self.mapped_registers = registers

    @check_monitoring_disabled
    def set_trigger(self, trigger_mode, trigger_signal=None, trigger_value=None,
                    trigger_repetitions=1):
        """
        Configure monitoring trigger. Monitoring must be disabled.

        Args:
            trigger_mode (MonitoringSoCType): monitoring start of condition type.
            trigger_signal (dict): dict with name and axis of trigger signal
                for rising or falling edge trigger.
            trigger_value (int or float): value for rising or falling edge trigger.
            trigger_repetitions (int): number of time trigger will be pull.

        Raises:
            TypeError: If trigger_mode is rising or falling edge trigger and
                trigger_signal or trigger_value are None.
            MonitoringError: If trigger signal is not mapped.
        """
        self.mc.communication.set_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER,
            trigger_repetitions,
            servo=self.servo,
            axis=0
        )
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
            raise MonitoringError("Trigger signal is not mapped in Monitoring")
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
        if dtype == il.REG_DTYPE.U16:
            output = np.array([int(value)], dtype="int64").astype("uint16")[0]
        elif dtype == il.REG_DTYPE.U32:
            output = struct.unpack('L', struct.pack('I', int(value)))[0]
        elif dtype == il.REG_DTYPE.S32:
            output = np.array([int(value)], dtype="int64").astype("int32")[0]
        else:
            output = struct.unpack('L', struct.pack('f', value))[0]
        return int(output)

    @check_monitoring_disabled
    def configure_number_samples(self, total_num_samples, trigger_delay_samples):
        """
        Configure monitoring number of samples. Monitoring must be disabled.

        Args:
            total_num_samples (int): monitoring total number of samples.
            trigger_delay_samples (int): monitoring number of samples before trigger.
                It should be less than total_num_samples. Minimum ``1``.

        Raises:
            ValueError: If trigger_delay_samples is less than ``1``
                or higher than total_num_samples.
            MonitoringError: If buffer size is not enough for all the samples.
        """
        if not total_num_samples > trigger_delay_samples:
            raise ValueError("trigger_delay_samples should be less"
                             " than total_num_samples")
        if trigger_delay_samples < 1:
            raise ValueError("trigger_delay_samples should be minimum 1")
        self.__check_buffer_size_is_enough(total_num_samples, trigger_delay_samples,
                                           self.mapped_registers)

        self.samples_number = total_num_samples
        self.trigger_delay_samples = trigger_delay_samples
        # Configure number of samples
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
        """
        Configure monitoring number of samples defines by sample and trigger
        delay time. Monitoring must be disabled.

        Args:
            total_time (float): monitoring sample total time, in seconds.
            trigger_delay (float): trigger delay in seconds. Value should be
                between ``-total_time/2`` and  ``total_time/2``.

        Raises:
            ValueError: If trigger_delay is not between ``-total_time/2`` and
                ``total_time/2``.
            MonitoringError: If buffer size is not enough for all the samples.
        """
        if total_time / 2 < abs(trigger_delay):
            raise ValueError("trigger_delay value should be between"
                             " -total_time/2 and total_time/2")
        total_num_samples = int(self.sampling_freq * total_time)
        trigger_delay_samples = int(((total_time / 2) - trigger_delay)
                                    * self.sampling_freq)
        trigger_delay_samples = trigger_delay_samples if trigger_delay_samples > 0 else 1
        self.configure_number_samples(total_num_samples, trigger_delay_samples)

    def enable_monitoring(self):
        """
        Enable monitoring

        Raises:
            MonitoringError: If monitoring can't be enabled.
        """
        network = self.mc.net[self.servo]
        network.monitoring_enable()
        # Check monitoring status
        if not self.is_monitoring_enabled():
            raise MonitoringError("Error enabling monitoring.")

    def disable_monitoring(self):
        """
        Disable monitoring
        """
        network = self.mc.net[self.servo]
        network.monitoring_disable()

    # TODO Study remove progress_callback
    def read_monitoring_data(self, progress_callback=None):
        """
        Blocking function that read the monitoring data.

        Returns:
            list of list: data of monitoring. Each element of the list is a
            different register data.
        """
        network = self.mc.net[self.servo]
        trigger_repetitions = self.mc.communication.get_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER,
            servo=self.servo,
            axis=0
        )
        is_enabled = self.is_monitoring_enabled()
        self.__read_process_finished = False
        data_array = [[] for _ in self.mapped_registers]
        self.logger.debug("Waiting for data")
        while not self.__read_process_finished:
            if not self.__check_data_is_ready():
                if not is_enabled or trigger_repetitions == 0:
                    text_is_enabled = "enabled" if is_enabled else "disabled"
                    self.logger.warning(
                        "Can't read monitoring data because monitoring is not ready."
                        " MON_CFG_TRIGGER_REPETITIONS is {}. Monitoring is {}."
                        .format(trigger_repetitions, text_is_enabled))
                    self.__read_process_finished = True
                continue
            network.monitoring_read_data()
            self.__fill_data(data_array)
            current_progress = len(data_array[0]) / self.samples_number
            self.logger.debug("Read %.2f%% of monitoring data", current_progress * 100)
            if progress_callback is not None:
                progress_callback(current_progress)
            if len(data_array[0]) >= self.samples_number:
                self.__read_process_finished = True
        return data_array

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

    def is_monitoring_enabled(self):
        """
        Check if monitoring is enabled.

        Returns:
            bool: True if monitoring is enabled, else False.
        """
        monitor_status = self.get_monitoring_disturbance_status()
        return (monitor_status & self.MONITORING_STATUS_ENABLED_BIT) == 1

    def get_monitoring_process_stage(self):
        """
        Return monitoring process stage.

        Returns:
            MonitoringProcessStage: Current monitoring process stage.
        """
        monitor_status = self.get_monitoring_disturbance_status()
        masked_value = monitor_status & self.MONITORING_STATUS_PROCESS_STAGE_BITS
        return MonitoringProcessStage(masked_value)

    def is_frame_available(self):
        """
        Check if monitoring has an available frame.

        Returns:
            bool: True if monitoring has an available frame, else False.
        """
        monitor_status = self.get_monitoring_disturbance_status()
        return (monitor_status & self.MONITORING_AVAILABLE_FRAME_BIT) != 0

    def __fill_data(self, data_array):
        network = self.mc.net[self.servo]
        for ch_idx, channel in enumerate(self.mapped_registers):
            dtype = channel["dtype"]
            tmp_monitor_data = network.monitoring_channel_data(ch_idx, dtype)
            data_array[ch_idx] += tmp_monitor_data

    def __check_version(self):
        self.__version_flag = self.MonitoringVersion.MONITORING_V2
        try:
            self.mc.servos[self.servo].dict.get_regs(0)[
                self.MONITORING_CURRENT_NUMBER_BYTES_REGISTER]
        except ILError:
            # The Monitoring V2 is NOT available
            self.__version_flag = self.MonitoringVersion.MONITORING_V1

    def __check_data_is_ready(self):
        monit_nmb_blocks = self.mc.communication.get_register(
            self.MONITORING_NUMBER_CYCLES_REGISTER,
            servo=self.servo,
            axis=0
        )
        data_is_ready = monit_nmb_blocks > 0
        if self.__version_flag == self.MonitoringVersion.MONITORING_V2:
            data_is_ready &= self.is_frame_available()
        return data_is_ready

    def stop_reading_data(self):
        """
        Stops read_monitoring_data function.
        """
        self.__read_process_finished = True

    def reset_trigger_repetitions(self, trigger_repetitions=1):
        """
        Reset trigger repetitions to target value.

        Args:
            trigger_repetitions (int): number of time trigger will be pull.
        """
        self.mc.communication.set_register(
            self.MONITORING_NUMBER_TRIGGER_REPETITIONS_REGISTER,
            trigger_repetitions,
            servo=self.servo,
            axis=0
        )

    def get_max_sample_size(self):
        """
        Return monitoring max size, in bytes.

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
        size_demand = 0
        n_sample = max(total_samples - trigger_delay_samples, trigger_delay_samples)
        for register in registers:
            size_demand += self.__data_type_size[register["dtype"]] * n_sample
        if not self.max_sample_number / 2 >= size_demand:
            raise MonitoringError(
                "Number of samples is too high or mapped registers are too big. "
                "Demanded size: {} bytes, buffer max size: {} bytes."
                .format(size_demand, self.max_sample_number // 2))
        self.logger.debug("Demanded size: %d bytes, buffer max size: %d bytes.",
                          size_demand, self.max_sample_number // 2)


class MonitoringError(Exception):
    pass
