import ingenialink as il

from .monitoring import Monitoring, MonitoringSoCType
from .disturbance import Disturbance
from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class Capture(metaclass=MCMetaClass):
    """Capture.
    """

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
            MonitoringError: If register maps fails in the servo.
            MonitoringError: If buffer size is not enough for all the registers
             and samples.
            MonitoringError: If trigger_mode is rising or falling edge trigger
             and trigger signal is not mapped.
            TypeError: If trigger_mode is rising or falling edge trigger and
             trigger_signal or trigger_value are None.
        """
        monitoring = Monitoring(self.mc, servo)
        monitoring.disable_monitoring()
        monitoring.set_frequency(prescaler)
        monitoring.map_registers(registers)
        monitoring.set_trigger(trigger_mode, trigger_signal=trigger_signal, trigger_value=trigger_value)
        monitoring.configure_sample_time(sample_time, trigger_delay)
        if start:
            monitoring.enable_monitoring()
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
            DisturbanceError: If buffer size is not enough for all the registers and samples.
        """
        disturbance = Disturbance(self.mc, servo)
        disturbance.disable_disturbance()
        disturbance.set_frequency_divider(freq_divider)
        disturbance.map_registers({"name": register, "axis": axis})
        disturbance.write_disturbance_data(data)
        if start:
            disturbance.enable_disturbance()
        return disturbance
