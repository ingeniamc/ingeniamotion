from ingenialink.exceptions import ILError
from ingenialink.ipb.poller import IPBPoller
from ingenialink.ipb.register import IPBRegister
from ingenialink.canopen.servo import CanopenServo
from ingenialink.canopen.poller import CanopenPoller

from ingeniamotion.disturbance import Disturbance
from ingeniamotion.monitoring.base_monitoring import Monitoring
from ingeniamotion.monitoring.monitoring_v1 import MonitoringV1
from ingeniamotion.monitoring.monitoring_v3 import MonitoringV3
from ingeniamotion.exceptions import IMRegisterNotExist, IMMonitoringError
from ingeniamotion.metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.enums import MonitoringVersion, MonitoringProcessStage,\
    MonitoringSoCType, MonitoringSoCConfig, REG_DTYPE, REG_ACCESS


class Capture(metaclass=MCMetaClass):
    """Capture."""

    DISTURBANCE_STATUS_REGISTER = "DIST_STATUS"
    DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER = "DIST_MAX_SIZE"
    MONITORING_STATUS_REGISTER = "MON_DIST_STATUS"
    MONITORING_CURRENT_NUMBER_BYTES_REGISTER = "MON_CFG_BYTES_VALUE"
    MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER = "MON_MAX_SIZE"

    MINIMUM_BUFFER_SIZE = 8192

    monitoring_version_register = IPBRegister(
        "MON_DIS_VERSION",
        "-",
        "CONFIG",
        REG_DTYPE.U32,
        REG_ACCESS.RO,
        0x00BA,
        subnode=0
    )

    MONITORING_STATUS_ENABLED_BIT = 0x1
    DISTURBANCE_STATUS_ENABLED_BIT = 0x1

    MONITORING_STATUS_PROCESS_STAGE_BITS = {
        MonitoringVersion.MONITORING_V1: 0x6,
        MonitoringVersion.MONITORING_V2: 0x6,
        MonitoringVersion.MONITORING_V3: 0xE
    }
    MONITORING_AVAILABLE_FRAME_BIT = {
        MonitoringVersion.MONITORING_V1: 0x800,
        MonitoringVersion.MONITORING_V2: 0x800,
        MonitoringVersion.MONITORING_V3: 0x10
    }

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def create_poller(self, registers, servo=DEFAULT_SERVO,
                      sampling_time=0.125, buffer_size=100, start=True):
        """Returns a Poller instance with target registers.

        Args:
            registers (list of dict): list of registers to add to the Poller.
                Dicts should have the follow format:

                .. code-block:: python

                    [
                        { # Poller register one
                            "name": "CL_POS_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis.
                            # If it has no axis field, by default axis 1.
                        },
                        { # Poller register two
                            "name": "CL_VEL_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis.
                            # If it has no axis field, by default axis 1.
                        }
                    ]

            servo (str): servo alias to reference it. ``default`` by default.
            sampling_time (float): period of the sampling in seconds.
                By default ``0.125`` seconds.
            buffer_size (int): number maximum of sample for each data read.
                ``100`` by default.
            start (bool): if ``True``, function starts poller, if ``False``
                poller should be started after. ``True`` by default.

        Returns:
            ingenialink.poller.Poller: Poller object with chosen registers.

            Poller.start()
                Poller starts reading the registers.

            Poller.stop()
                Poller stop reading the registers.

            Poller.data
                tuple with 3 items: a list of timestamp, list of lists of values
                (one list of values for each register), and a boolean that
                indicates if data was lost.

                When the poller starts, the lists are filled with the timestamp
                and the value of the registers reading. The maximum length of
                the list will be buffer_size value, when this size is reached,
                the older value will be removed and the newest will be added.

                When the property data is read list are reset to a empty list.

        Raises:
            IMRegisterNotExist: If register does not exist in dictionary.
        """
        if isinstance(self.mc.servos[servo], CanopenServo):
            poller = CanopenPoller(self.mc.servos[servo], len(registers))
        else:
            poller = IPBPoller(self.mc.servos[servo], len(registers))
        poller.configure(sampling_time, buffer_size)
        for index, register in enumerate(registers):
            axis = register.get("axis", DEFAULT_AXIS)
            name = register.get("name")
            register_obj = self.mc.info.register_info(name, axis, servo=servo)
            poller.ch_configure(index, register_obj)
        if start:
            poller.start()
        return poller

    def create_empty_monitoring(self, servo=DEFAULT_SERVO):
        """Returns a Monitoring instance not configured.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            Monitoring: Not configured instance of monitoring.

        """
        version = self._check_version(servo)
        if version == MonitoringVersion.MONITORING_V3:
            return MonitoringV3(self.mc, servo)
        if version < MonitoringVersion.MONITORING_V3:
            return MonitoringV1(self.mc, servo)

    def create_monitoring(self, registers, prescaler, sample_time, trigger_delay=0,
                          trigger_mode=MonitoringSoCType.TRIGGER_EVENT_AUTO,
                          trigger_config=None, trigger_signal=None, trigger_value=None,
                          servo=DEFAULT_SERVO, start=False):
        """Returns a Monitoring instance configured with target registers.

        Args:
            registers (list of dict): list of registers to add to Monitoring.
            Dicts should have the follow format:

                .. code-block:: python

                    [
                        { # Monitoring register one
                            "name": "CL_POS_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis.
                            # If it has no axis field, by default axis 1.
                        },
                        { # Monitoring register two
                            "name": "CL_VEL_FBK_VALUE",  # Register name.
                            "axis": 1  # Register axis.
                            # If it has no axis field, by default axis 1.
                        }
                    ]

            prescaler (int): determines monitoring frequency. Frequency will be
                ``Position & velocity loop rate frequency / prescaler``, see
                :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
                to know about this frequency. It must be ``1`` or higher.
            sample_time (float): sample time in seconds.
            trigger_delay (float): trigger delay in seconds. Value should be between
                ``-sample_time/2`` and ``sample_time/2`` . ``0`` by default.
            trigger_mode (MonitoringSoCType): monitoring start of condition type.
                ``TRIGGER_EVENT_NONE`` by default.
            trigger_config (MonitoringSoCConfig): monitoring edge condition.
                ``None`` by default.
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
        self.clean_monitoring(servo=servo)
        monitoring = self.create_empty_monitoring(servo)
        monitoring.set_frequency(prescaler)
        monitoring.map_registers(registers)
        monitoring.set_trigger(trigger_mode,
                               edge_condition=trigger_config,
                               trigger_signal=trigger_signal,
                               trigger_value=trigger_value)
        monitoring.configure_sample_time(sample_time, trigger_delay)
        if start:
            self.enable_monitoring(servo=servo)
        return monitoring

    def create_disturbance(self, register, data, freq_divider,
                           servo=DEFAULT_SERVO, axis=DEFAULT_AXIS, start=False):
        """Returns a Disturbance instance configured with target registers.

        Args:
            register (str): target register UID.
            data (list): data to write in disturbance.
            freq_divider (int): determines disturbance frequency divider. Frequency will
                be ``Position & velocity loop rate frequency / freq_divider``, see
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
            IMDisturbanceError: If buffer size is not enough for all the
                registers and samples.

        """
        self.clean_disturbance(servo=servo)
        disturbance = Disturbance(self.mc, servo)
        disturbance.set_frequency_divider(freq_divider)
        disturbance.map_registers({"name": register, "axis": axis})
        disturbance.write_disturbance_data(data)
        if start:
            self.enable_disturbance(servo=servo)
        return disturbance

    def _check_version(self, servo):
        """Checks the version of the monitoring based on a given servo.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        drive = self.mc._get_drive(servo)
        try:
            drive.read(self.monitoring_version_register)
            return MonitoringVersion.MONITORING_V3
        except ILError:
            # The Monitoring V3 is NOT available
            pass
        try:
            self.mc.info.register_info(
                self.MONITORING_CURRENT_NUMBER_BYTES_REGISTER, 0, servo=servo)
            return MonitoringVersion.MONITORING_V2
        except IMRegisterNotExist:
            # The Monitoring V2 is NOT available
            return MonitoringVersion.MONITORING_V1

    def enable_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """Enable monitoring and disturbance.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Raises:
            IMMonitoringError: If monitoring can't be enabled.

        """
        self.enable_monitoring(servo=servo)
        self.enable_disturbance(servo=servo)

    def enable_monitoring(self, servo=DEFAULT_SERVO):
        """Enable monitoring.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Raises:
            IMMonitoringError: If monitoring can't be enabled.

        """
        drive = self.mc.servos[servo]
        drive.monitoring_enable()
        # Check monitoring status
        if not self.is_monitoring_enabled(servo=servo):
            raise IMMonitoringError("Error enabling monitoring.")

    def enable_disturbance(self, servo=DEFAULT_SERVO, version=None):
        """Enable disturbance.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Raises:
            IMMonitoringError: If disturbance can't be enabled.

        """
        if version is None:
            version = self._check_version(servo)
        if version < MonitoringVersion.MONITORING_V3:
            return self.enable_monitoring(servo=servo)
        drive = self.mc.servos[servo]
        drive.disturbance_enable()
        # Check disturbance status
        if not self.is_disturbance_enabled(servo=servo):
            raise IMMonitoringError("Error enabling disturbance.")

    def disable_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """Disable monitoring and disturbance.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        """
        self.disable_monitoring(servo=servo)
        self.disable_disturbance(servo=servo)

    def disable_monitoring(self, servo=DEFAULT_SERVO, version=None):
        """Disable monitoring.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        """
        if version is None:
            version = self._check_version(servo)
        if not self.is_monitoring_enabled(servo=servo):
            return
        drive = self.mc.servos[servo]
        drive.monitoring_disable()
        if version >= MonitoringVersion.MONITORING_V3:
            return drive.monitoring_remove_data()

    def disable_disturbance(self, servo=DEFAULT_SERVO, version=None):
        """Disable disturbance.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        """
        if version is None:
            version = self._check_version(servo)
        if not self.is_disturbance_enabled(servo, version):
            return
        if version < MonitoringVersion.MONITORING_V3:
            return self.disable_monitoring(servo=servo, version=version)
        drive = self.mc.servos[servo]
        drive.disturbance_disable()
        if version < MonitoringVersion.MONITORING_V3:
            return drive.disturbance_remove_data()

    def get_monitoring_disturbance_status(self, servo=DEFAULT_SERVO):
        """Get Monitoring Status.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int: Monitoring/Disturbance Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        return self.mc.communication.get_register(
            self.MONITORING_STATUS_REGISTER,
            servo=servo,
            axis=0
        )

    def get_monitoring_status(self, servo=DEFAULT_SERVO):
        """Get Monitoring Status.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int: Monitoring Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        return self.mc.communication.get_register(
            self.MONITORING_STATUS_REGISTER,
            servo=servo,
            axis=0
        )

    def get_disturbance_status(self, servo=DEFAULT_SERVO, version=None):
        """Get Disturbance Status.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            int: Disturbance Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        if version is None:
            version = self._check_version(servo)
        if version < MonitoringVersion.MONITORING_V3:
            return self.mc.communication.get_register(
                self.MONITORING_STATUS_REGISTER,
                servo=servo,
                axis=0
            )
        else:
            return self.mc.communication.get_register(
                self.DISTURBANCE_STATUS_REGISTER,
                servo=servo,
                axis=0
            )

    def is_monitoring_enabled(self, servo=DEFAULT_SERVO):
        """Check if monitoring is enabled.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            bool: True if monitoring is enabled, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        monitor_status = self.get_monitoring_status(servo)
        return (monitor_status & self.MONITORING_STATUS_ENABLED_BIT) == 1

    def is_disturbance_enabled(self, servo=DEFAULT_SERVO, version=None):
        """Check if disturbance is enabled.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            bool: True if disturbance is enabled, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        monitor_status = self.get_disturbance_status(servo, version=version)
        return (monitor_status & self.DISTURBANCE_STATUS_ENABLED_BIT) == 1

    def get_monitoring_process_stage(self, servo=DEFAULT_SERVO, version=None):
        """
        Return monitoring process stage.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            MonitoringProcessStage: Current monitoring process stage.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        if version is None:
            version = self._check_version(servo=servo)
        monitor_status = self.mc.capture.get_monitoring_status(
            servo=servo)
        mask = self.MONITORING_STATUS_PROCESS_STAGE_BITS[version]
        masked_value = monitor_status & mask
        return MonitoringProcessStage(masked_value)

    def is_frame_available(self, servo=DEFAULT_SERVO, version=None):
        """
        Check if monitoring has an available frame.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            bool: True if monitoring has an available frame, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
        """
        if version is None:
            version = self._check_version(servo=servo)
        monitor_status = self.mc.capture.get_monitoring_status(
            servo=servo)
        mask = self.MONITORING_AVAILABLE_FRAME_BIT[version]
        return (monitor_status & mask) != 0

    def clean_monitoring(self, servo=DEFAULT_SERVO, version=None):
        """Disable monitoring/disturbance and remove monitoring mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if None reads from drive. ``None`` by default.

        """
        self.disable_monitoring(servo=servo, version=version)
        drive = self.mc.servos[servo]
        drive.monitoring_remove_all_mapped_registers()

    def clean_disturbance(self, servo=DEFAULT_SERVO, version=None):
        """Disable monitoring/disturbance and remove disturbance mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            version (MonitoringVersion): Monitoring/Disturbance version,
                if None reads from drive. ``None`` by default.

        """
        self.disable_disturbance(servo=servo, version=version)
        drive = self.mc.servos[servo]
        drive.disturbance_remove_all_mapped_registers()

    def clean_monitoring_disturbance(self, servo=DEFAULT_SERVO):
        """Disable monitoring/disturbance, remove disturbance and monitoring
        mapped registers.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
        """
        self.clean_monitoring(servo=servo)
        self.clean_disturbance(servo=servo)

    @MCMetaClass.check_motor_disabled
    def mcb_synchronization(self, servo=DEFAULT_SERVO):
        """Synchronize MCB, necessary to monitoring and disturbance.
        Motor must be disabled.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.

        """
        self.enable_monitoring(servo=servo)
        self.disable_monitoring(servo=servo)

    def disturbance_max_sample_size(self, servo=DEFAULT_SERVO):
        """Return disturbance max size, in bytes.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int: Max buffer size in bytes.
        """
        try:
            return self.mc.communication.get_register(
                self.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER,
                servo=servo,
                axis=0
            )
        except IMRegisterNotExist:
            return self.MINIMUM_BUFFER_SIZE

    def monitoring_max_sample_size(self, servo=DEFAULT_SERVO):
        """Return monitoring max size, in bytes.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.

        Returns:
            int: Max buffer size in bytes.
        """
        try:
            return self.mc.communication.get_register(
                self.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER,
                servo=servo,
                axis=0
            )
        except IMRegisterNotExist:
            return self.MINIMUM_BUFFER_SIZE
