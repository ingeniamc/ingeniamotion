import ingenialink as il

from .disturbance import Disturbance
from .monitoring import Monitoring, MonitoringSoCType
from .exceptions import IMMonitoringError, IMDisturbanceError
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Capture(metaclass=MCMetaClass):
    """Capture.
    """

    MONITORING_DISTURBANCE_STATUS_REGISTER = "MON_DIST_STATUS"

    MONITORING_STATUS_ENABLED_BIT = 0x1

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def create_poller(self, registers, servo=DEFAULT_SERVO,
                      sampling_time=0.125, buffer_size=100, start=True):
        """
        Returns a Poller instance with target registers.

        Args:
            registers (list of dict): list of registers to add to the Poller. Dicts should have the follow format:

                .. code-block:: python

                    [
                        { # Poller register one
                            "name": "CL_POS_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        },
                        { # Poller register two
                            "name": "CL_VEL_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        }
                    ]

            servo (str): servo alias to reference it. ``default`` by default.
            sampling_time (float): period of the sampling in seconds. By default ``0.125`` seconds.
            buffer_size (int): number maximum of sample for each data read. ``100`` by default.
            start (bool): if ``True``, function starts poller, if ``False`` poller should be started after.
             ``True`` by default.

        Returns:
            Poller: Poller object with chosen registers.

            Poller.start()
                Poller starts reading the registers.

            Poller.stop()
                Poller stop reading the registers.

            Poller.data
                tuple with 3 items: a list of timestamp, list of lists of values (one list of values for each register),
                and a boolean that indicates if data was lost.

                When the poller starts, the lists are filled with the timestamp and the value of the registers reading.
                The maximum length of the list will be buffer_size value, when this size is reached,
                the older value will be removed and the newest will be added.

                When the property data is read list are reset to a empty list.
        """
        drive = self.mc.servos[servo]
        if self.mc.net[servo].prot == il.NET_PROT.CAN:
            poller = il.CANOpenPoller(self.mc.servos[servo], len(registers))
        else:
            poller = il.Poller(self.mc.servos[servo], len(registers))
        poller.configure(sampling_time, buffer_size)
        for index, register in enumerate(registers):
            axis = register.get("axis", DEFAULT_AXIS)
            name = register.get("name")
            register_obj = drive.dict.get_regs(axis)[name]
            poller.ch_configure(index, register_obj)
        if start:
            poller.start()
        return poller

    def create_monitoring(self, registers, prescaler, sample_time, trigger_delay=0,
                          trigger_mode=MonitoringSoCType.TRIGGER_EVENT_NONE,
                          trigger_signal=None, trigger_value=None,
                          servo=DEFAULT_SERVO, start=False):
        """
        Returns a Monitoring instance configured with target registers.

        Args:
            registers (list of dict): list of registers to add to Monitoring.
            Dicts should have the follow format:

                .. code-block:: python

                    [
                        { # Monitoring register one
                            "name": "CL_POS_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        },
                        { # Monitoring register two
                            "name": "CL_VEL_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis. If it has no axis field, by default axis 1.
                        }
                    ]

            prescaler (int): determines monitoring frequency. Frequency will be
                ``Position & velocity loop rate frequency / prescaler``, see
                :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate` to know about
                this frequency. It must be ``1`` or higher.
            sample_time (float): sample time in seconds.
            trigger_delay (float): trigger delay in seconds. Value should be between
                ``-sample_time/2`` and ``sample_time/2`` . ``0`` by default.
            trigger_mode (MonitoringSoCType): monitoring start of condition type.
                ``TRIGGER_EVENT_NONE`` by default.
            trigger_signal (dict): dict with name and axis of trigger signal
                for rising or falling edge trigger.
            trigger_value (int or float): value for rising or falling edge trigger.
            servo (str): servo alias to reference it. ``default`` by default.
            start (bool): if ``True``, function starts monitoring, if ``False``
                monitoring should be started after. ``False`` by default.

        Returns:
            Monitoring: Instance of monitoring configured.

        Raises:
            ValueError: If prescaler is less than ``1``.
            ValueError: If trigger_delay is not between ``-total_time/2`` and
             ``total_time/2``.
            IMMonitoringError: If register maps fails in the servo.
            IMMonitoringError: If buffer size is not enough for all the registers
             and samples.
            IMMonitoringError: If trigger_mode is rising or falling edge trigger
             and trigger signal is not mapped.
            TypeError: If trigger_mode is rising or falling edge trigger and
             trigger_signal or trigger_value are None.
        """
        self.disable_monitoring_disturbance(servo=servo)
        monitoring = Monitoring(self.mc, servo)
        monitoring.set_frequency(prescaler)
        monitoring.map_registers(registers)
        monitoring.set_trigger(trigger_mode, trigger_signal=trigger_signal, trigger_value=trigger_value)
        monitoring.configure_sample_time(sample_time, trigger_delay)
        if start:
            self.enable_monitoring_disturbance(servo=servo)
        return monitoring

    def create_disturbance(self, register, data, freq_divider,
                           servo=DEFAULT_SERVO, axis=DEFAULT_AXIS, start=False):
        """
        Returns a Disturbance instance configured with target registers.

        Args:
            register (str): target register UID.
            data (list): data to write in disturbance.
            freq_divider (int): determines disturbance frequency divider. Frequency will be
                ``Position & velocity loop rate frequency / freq_divider``, see
                :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
                to know about this frequency. It must be ``1`` or higher.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            start (bool): if ``True``, function starts disturbance,
                if ``False`` disturbance should be started after.
                ``False`` by default.

        Returns:
            Disturbance: Instance of disturbance configured.

        Raises:
            ValueError: If freq_divider is less than ``1``.
            IMDisturbanceError: If buffer size is not enough for all the registers and samples.
        """
        self.clean_monitoring(servo=servo)
        disturbance = Disturbance(self.mc, servo)
        disturbance.set_frequency_divider(freq_divider)
        disturbance.map_registers({"name": register, "axis": axis})
        disturbance.write_disturbance_data(data)
        if start:
            self.enable_monitoring_disturbance(servo=servo)
        return disturbance

    def enable_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """
        Enable monitoring.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Raises:
            IMMonitoringError: If monitoring can't be enabled.
        """
        network = self.mc.net[servo]
        network.monitoring_enable()
        # Check monitoring status
        if not self.is_monitoring_enabled(servo=servo):
            raise IMMonitoringError("Error enabling monitoring.")

    def disable_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """
        Disable monitoring.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        network = self.mc.net[servo]
        network.monitoring_disable()

    def get_monitoring_disturbance_status(self, servo=DEFAULT_SERVO):
        """
        Get Monitoring/Disturbance Status.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int: Monitoring/Disturbance Status.
        """
        return self.mc.communication.get_register(
            self.MONITORING_DISTURBANCE_STATUS_REGISTER,
            servo=servo,
            axis=0
        )

    def is_monitoring_enabled(self, servo=DEFAULT_SERVO):
        """
        Check if monitoring is enabled.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            bool: True if monitoring is enabled, else False.
        """
        monitor_status = self.get_monitoring_disturbance_status(servo)
        return (monitor_status & self.MONITORING_STATUS_ENABLED_BIT) == 1

    def is_disturbance_enabled(self, servo=DEFAULT_SERVO):
        """
        Check if disturbance is enabled.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            bool: True if disturbance is enabled, else False.
        """
        return self.is_monitoring_enabled(servo)

    def clean_monitoring(self, servo=DEFAULT_SERVO):
        """
        Disable monitoring/disturbance and remove monitoring mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        self.disable_monitoring_disturbance(servo=servo)
        network = self.mc.net[servo]
        network.monitoring_remove_all_mapped_registers()

    def clean_disturbance(self, servo=DEFAULT_SERVO):
        """
        Disable monitoring/disturbance and remove disturbance mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        self.disable_monitoring_disturbance(servo=servo)
        network = self.mc.net[servo]
        network.disturbance_remove_all_mapped_registers()

    def clean_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """
        Disable monitoring/disturbance, remove disturbance and monitoring
        mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        self.clean_monitoring(servo=servo)
        self.clean_disturbance(servo=servo)

    @MCMetaClass.check_motor_disabled
    def mcb_synchronization(self, servo=DEFAULT_SERVO):
        self.enable_monitoring_disturbance(servo=servo)
        self.disable_monitoring_disturbance(servo=servo)
