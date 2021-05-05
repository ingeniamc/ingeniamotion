import struct
import numpy as np
import ingenialogger
import ingenialink as il
from functools import wraps
from ingenialink.exceptions import ILError

from enum import IntEnum

MONITORING_ENABLED_BIT = 0x1


def check_monitoring_disabled(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        monitor_status = self.mc.communication.get_register(
            "MON_DIST_STATUS",
            servo=self.servo,
            axis=0
        )
        if (monitor_status & MONITORING_ENABLED_BIT) == 1:
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

    REGISTER_MAP_OFFSET = 0x800
    MONITORING_AVAILABLE_FRAME_BIT = 0x800

    class MonitoringVersion(IntEnum):
        """
        Monitoring version
        """
        # Monitoring V1 used for Everest 1.7.1 and older.
        MONITORING_V1 = 0,
        # Monitoring V2 used for Capitan and some custom low-power drivers.
        MONITORING_V2 = 1

    def __init__(self, mc, servo="default"):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.mapped_registers = {}
        self.monitoring_data = []
        self.sampling_freq = None
        self.__version_flag = self.MonitoringVersion.MONITORING_V1
        self.__read_process_finished = False
        self.samples_number = 0
        self.logger = ingenialogger.get_logger(__name__, drive=mc.servo_name(servo))
        self.__check_version()
        self.data = None

    @check_monitoring_disabled
    def set_frequency(self, prescaler):
        """
        Function to define monitoring frequency with a prescaler. Monitoring must be disabled.

        Args:
            prescaler (int): determines monitoring frequency. Frequency will be ``Power stage frequency / prescaler``.
                It must be 1 or higher.

        Raises:
            ValueError: If prescaler is lowe than 1.
        """
        if prescaler < 1:
            raise ValueError("prescaler must be 1 or higher")
        position_velocity_loop_rate = self.mc.communication.get_register(
            'DRV_POS_VEL_RATE',
            servo=self.servo,
            axis=1
        )
        self.sampling_freq = round(position_velocity_loop_rate / prescaler, 2)
        self.mc.communication.set_register(
            'MON_DIST_FREQ_DIV',
            prescaler,
            servo=self.servo,
            axis=0
        )

    @check_monitoring_disabled
    def map_registers(self, registers):
        """
        Map registers to monitoring. Monitoring must be disabled.

        Args:
            registers (list of dict): List of registers to map. Each register must be a dict with two keys:
                - "axis": number of register axis
                - "name": register key in drive object

        Raises:
            MonitoringError: If register maps fails in the servo.
        """
        self.mapped_registers = registers
        drive = self.mc.servos[self.servo]
        network = self.mc.net[self.servo]
        network.monitoring_remove_all_mapped_registers()
        for ch_idx, channel in enumerate(registers):
            subnode = channel.get("axis", 1)
            register = channel["name"]
            address_offset = self.REGISTER_MAP_OFFSET * (subnode - 1)
            register_obj = drive.dict.get_regs(subnode)[register]
            mapped_reg = register_obj.address + address_offset
            dtype = register_obj.dtype
            channel["dtype"] = dtype
            network.monitoring_set_mapped_register(ch_idx, mapped_reg, dtype.value)

        num_mon_reg = self.mc.communication.get_register(
            'MON_CFG_TOTAL_MAP',
            servo=self.servo,
            axis=0
        )
        if num_mon_reg < 1:
            raise MonitoringError("Map Monitoring registers fails")

    @check_monitoring_disabled
    def set_trigger(self, trigger_mode, trigger_signal=None, trigger_value=None, trigger_repetitions=1):
        """
        Configure monitoring trigger. Monitoring must be disabled.

        Args:
            trigger_mode (MonitoringSoCType): monitoring start of condition type.
            trigger_signal (dict): dict with name and axis of trigger signal for rising or falling edge trigger.
            trigger_value (int or float): value for rising or falling edge trigger.
            trigger_repetitions (int): number of time trigger will be pull.

        Raises:
            TypeError: If trigger_mode is rising or falling edge trigger and trigger_signal or trigger_value are None.
        """
        self.mc.communication.set_register(
            'MON_CFG_TRIGGER_REPETITIONS',
            trigger_repetitions,
            servo=self.servo,
            axis=0
        )
        self.mc.communication.set_register(
            "MON_CFG_SOC_TYPE",
            trigger_mode,
            servo=self.servo,
            axis=0
        )
        if trigger_mode in \
                [MonitoringSoCType.TRIGGER_CYCLIC_RISING_EDGE,
                 MonitoringSoCType.TRIGGER_CYCLIC_FALLING_EDGE]:
            if trigger_signal is None or trigger_value is None:
                raise TypeError("trigger_signal or trigger_value are None")
            self.__rising_or_falling_edge_trigger(trigger_mode, trigger_signal, trigger_value)

    def __rising_or_falling_edge_trigger(self, trigger_mode, trigger_signal, trigger_value):
        index_reg = -1
        for index, item in enumerate(self.mapped_registers):
            if trigger_signal["name"] == item["name"] and trigger_signal.get("axis", 1) == item["axis"]:
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
            "MON_IDX_CHECK",
            index_reg,
            servo=self.servo,
            axis=0
        )

    @staticmethod
    def __unpack_trigger_value(value, dtype):
        if dtype == il.REG_DTYPE.U16:
            return np.array([int(value)], dtype='int64').astype('uint16')[0]
        if dtype == il.REG_DTYPE.U32:
            return struct.unpack('L', struct.pack('I', int(value)))[0]
        if dtype == il.REG_DTYPE.S32:
            return np.array([int(value)], dtype='int64').astype('int32')[0]
        return struct.unpack('L', struct.pack('f', value))[0]

    @check_monitoring_disabled
    def configure_number_samples(self, total_num_samples, trigger_delay_samples):
        """
        Configure monitoring number of samples. Monitoring must be disabled.

        Args:
            total_num_samples: monitoring total number of samples.
            trigger_delay_samples: monitoring number of samples before trigger.
        """
        # Configure number of samples
        window_samples = total_num_samples - trigger_delay_samples

        self.mc.communication.set_register(
            'MON_CFG_EOC_TYPE',
            self.EOC_TRIGGER_NUMBER_SAMPLES,
            servo=self.servo,
            axis=0
        )
        self.mc.communication.set_register(
            "MON_CFG_TRIGGER_DELAY",
            trigger_delay_samples,
            servo=self.servo,
            axis=0
        )
        self.mc.communication.set_register(
            "MON_CFG_WINDOW_SAMP",
            window_samples,
            servo=self.servo,
            axis=0
        )

    @check_monitoring_disabled
    def configure_sample_time(self, total_time, trigger_delay):
        """
        Configure monitoring number of samples defines by sample and trigger delay time. Monitoring must be disabled.

        Args:
            total_time (float): monitoring sample total time, in seconds.
            trigger_delay (float): trigger delay in seconds. Value should be between ``-total_time/2`` and
                ``total_time/2``.
        """
        total_num_samples = int(self.sampling_freq * total_time)
        self.samples_number = total_num_samples
        trigger_delay_samples = int(((total_time / 2) - trigger_delay) * self.sampling_freq)
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
        monitor_status = self.mc.communication.get_register(
            "MON_DIST_STATUS",
            servo=self.servo,
            axis=0
        )
        if (monitor_status & MONITORING_ENABLED_BIT) != 1:
            raise MonitoringError("ERROR MONITOR STATUS: {}".format(monitor_status))

    def disable_monitoring(self):
        network = self.mc.net[self.servo]
        network.monitoring_disable()

    # TODO Study remove progress_callback
    def read_monitoring_data(self, progress_callback=None):
        """
        Blocking function that read the monitoring data.

        Returns:
            list of list: data of monitoring. Each element of the list is a different register data.
        """
        network = self.mc.net[self.servo]
        trigger_repetitions = self.mc.communication.get_register(
            "MON_CFG_TRIGGER_REPETITIONS",
            servo=self.servo,
            axis=0
        )
        self.__read_process_finished = False
        data_array = [[] for _ in self.mapped_registers]
        while not self.__read_process_finished:
            if not self.__check_data_is_ready():
                if trigger_repetitions == 0:
                    self.logger.warning("Can't read monitoring data because monitoring is not ready."
                                        " MON_CFG_TRIGGER_REPETITIONS is 0.")
                    break
                continue
            network.monitoring_read_data()
            self.__fill_data(data_array)
            if progress_callback is not None:
                current_progress = len(data_array[0]) / self.samples_number
                progress_callback(current_progress)
            if len(data_array[0]) >= self.samples_number:
                self.__read_process_finished = True
        return data_array

    def __fill_data(self, data_array):
        network = self.mc.net[self.servo]
        for ch_idx, channel in enumerate(self.mapped_registers):
            dtype = channel["dtype"]
            tmp_monitor_data = network.monitoring_channel_data(ch_idx, dtype)
            data_array[ch_idx] += tmp_monitor_data

    def __check_version(self):
        self.__version_flag = self.MonitoringVersion.MONITORING_V2
        try:
            self.mc.servos[self.servo].dict.get_regs(0)["MON_CFG_BYTES_VALUE"]
        except ILError:
            # The Monitoring V2 is NOT available
            self.__version_flag = self.MonitoringVersion.MONITORING_V1

    def __check_data_is_ready(self):
        if self.__version_flag == self.MonitoringVersion.MONITORING_V2:
            monitor_status = self.mc.communication.get_register(
                "MON_DIST_STATUS",
                servo=self.servo,
                axis=0
            )
            data_is_ready = (monitor_status & self.MONITORING_AVAILABLE_FRAME_BIT) != 0
        else:
            monit_nmb_blocks = self.mc.communication.get_register(
                "MON_CFG_CYCLES_VALUE",
                servo=self.servo,
                axis=0
            )
            data_is_ready = monit_nmb_blocks > 0
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
            "MON_CFG_TRIGGER_REPETITIONS",
            trigger_repetitions,
            servo=self.servo,
            axis=0
        )


class MonitoringError(Exception):
    pass
