from typing import TYPE_CHECKING, Dict, List, Optional, Union

import numpy as np
from numpy.typing import NDArray

from ingenialink.dictionary import SubnodeType
from ingenialink.exceptions import ILIOError
from ingenialink.poller import Poller
from ingeniamotion.disturbance import Disturbance
from ingeniamotion.enums import (
    MonitoringProcessStage,
    MonitoringSoCConfig,
    MonitoringSoCType,
    MonitoringVersion,
)
from ingeniamotion.exceptions import (
    IMMonitoringError,
    IMRegisterNotExist,
    IMStatusWordError,
)
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass
from ingeniamotion.monitoring.base_monitoring import Monitoring
from ingeniamotion.monitoring.monitoring_v1 import MonitoringV1
from ingeniamotion.monitoring.monitoring_v3 import MonitoringV3
from ingeniamotion.pdo import PDONetworkManager

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class Capture(metaclass=MCMetaClass):
    """Capture."""

    DISTURBANCE_STATUS_REGISTER = "DIST_STATUS"
    DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER = "DIST_MAX_SIZE"
    MONITORING_STATUS_REGISTER = "MON_DIST_STATUS"
    MONITORING_CURRENT_NUMBER_BYTES_REGISTER = "MON_CFG_BYTES_VALUE"
    MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER = "MON_MAX_SIZE"
    MONITORING_FREQUENCY_DIVIDER_REGISTER = "MON_DIST_FREQ_DIV"

    MINIMUM_BUFFER_SIZE = 8192

    MONITORING_VERSION_REGISTER = "MON_DIST_VERSION"

    MONITORING_STATUS_ENABLED_BIT = 0x1
    DISTURBANCE_STATUS_ENABLED_BIT = 0x1

    MONITORING_STATUS_PROCESS_STAGE_BITS = {
        MonitoringVersion.MONITORING_V1: 0x6,
        MonitoringVersion.MONITORING_V2: 0x6,
        MonitoringVersion.MONITORING_V3: 0xE,
    }
    MONITORING_AVAILABLE_FRAME_BIT = {
        MonitoringVersion.MONITORING_V1: 0x800,
        MonitoringVersion.MONITORING_V2: 0x800,
        MonitoringVersion.MONITORING_V3: 0x10,
    }

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.pdo = PDONetworkManager(self.mc)

    def create_poller(
        self,
        registers: List[Dict[str, Union[int, str]]],
        servo: str = DEFAULT_SERVO,
        sampling_time: float = 0.125,
        buffer_size: int = 100,
        start: bool = True,
    ) -> Poller:
        """Returns a Poller instance with target registers.

        Args:
            registers : list of registers to add to the Poller.
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

            servo: servo alias to reference it. ``default`` by default.
            sampling_time: period of the sampling in seconds.
                By default ``0.125`` seconds.
            buffer_size: number maximum of sample for each data read.
                ``100`` by default.
            start: if ``True``, function starts poller, if ``False``
                poller should be started after. ``True`` by default.

        Returns:
            Poller object with chosen registers.

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
            TypeError: If some parameter has a wrong type.

        """
        poller = Poller(self.mc.servos[servo], len(registers))
        poller.configure(sampling_time, buffer_size)
        for index, register in enumerate(registers):
            axis = register.get("axis", DEFAULT_AXIS)
            name = register.get("name")
            if not isinstance(axis, int):
                raise TypeError("Wrong axis type, it should be an int")
            if not isinstance(name, str):
                raise TypeError("Name type is a string")
            register_obj = self.mc.info.register_info(name, axis, servo=servo)
            poller.ch_configure(index, register_obj)
        if start:
            poller.start()
        return poller

    def create_empty_monitoring(self, servo: str = DEFAULT_SERVO) -> Monitoring:
        """Returns a Monitoring instance not configured.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Not configured instance of monitoring.

        Raises:
            NotImplementedError: If an wrong monitoring version is requested.

        """
        version = self._check_version(servo)
        if version == MonitoringVersion.MONITORING_V3:
            return MonitoringV3(self.mc, servo)
        elif version == MonitoringVersion.MONITORING_V1:
            return MonitoringV1(self.mc, servo)
        else:
            raise NotImplementedError(f"This version {version} is not implemented yet")

    def create_monitoring(
        self,
        registers: List[Dict[str, Union[int, str]]],
        prescaler: int,
        sample_time: float,
        trigger_delay: float = 0,
        trigger_mode: MonitoringSoCType = MonitoringSoCType.TRIGGER_EVENT_AUTO,
        trigger_config: Optional[MonitoringSoCConfig] = None,
        trigger_signal: Optional[Dict[str, Union[int, str]]] = None,
        trigger_value: Union[float, int, None] = None,
        servo: str = DEFAULT_SERVO,
        start: bool = False,
    ) -> Monitoring:
        """Returns a Monitoring instance configured with target registers.

        Args:
            registers: list of registers to add to Monitoring.
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

            prescaler : determines monitoring frequency. Frequency will be
                ``Position & velocity loop rate frequency / prescaler``, see
                :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
                to know about this frequency. It must be ``1`` or higher.
            sample_time : sample time in seconds.
            trigger_delay : trigger delay in seconds. Value should be between
                ``-sample_time/2`` and ``sample_time/2`` . ``0`` by default.
            trigger_mode : monitoring start of condition type.
                ``TRIGGER_EVENT_NONE`` by default.
            trigger_config : monitoring edge condition.
                ``None`` by default.
            trigger_signal : dict with name and axis of trigger signal
                for rising or falling edge trigger.
            trigger_value : value for rising or falling edge trigger.
            servo : servo alias to reference it. ``default`` by default.
            start : if ``True``, function starts monitoring, if ``False``
                monitoring should be started after. ``False`` by default.

        Returns:
            Instance of monitoring configured.

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
        monitoring.set_trigger(
            trigger_mode,
            edge_condition=trigger_config,
            trigger_signal=trigger_signal,
            trigger_value=trigger_value,
        )
        monitoring.configure_sample_time(sample_time, trigger_delay)
        if start:
            self.enable_monitoring(servo=servo)
        return monitoring

    def create_disturbance(
        self,
        register: str,
        data: Union[List[Union[float, int]], NDArray[np.int_], NDArray[np.float_]],
        freq_divider: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        start: bool = False,
    ) -> Disturbance:
        """Returns a Disturbance instance configured with target registers.

        Args:
            register : target register UID.
            data : data to write in disturbance.
            freq_divider : determines disturbance frequency divider. Frequency will
                be ``Position & velocity loop rate frequency / freq_divider``, see
                :func:`ingeniamotion.configuration.Configuration.get_position_and_velocity_loop_rate`
                to know about this frequency. It must be ``1`` or higher.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            start : if ``True``, function starts disturbance,
                if ``False`` disturbance should be started after.
                ``False`` by default.

        Returns:
            Instance of disturbance configured.

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

    def _check_version(self, servo: str) -> MonitoringVersion:
        """Checks the version of the monitoring based on a given servo.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            NotImplementedError: If the drive does not support monitoring
            and disturbance.

        """
        try:
            self.mc.communication.get_register(
                self.MONITORING_VERSION_REGISTER, servo=servo, axis=0
            )
            return MonitoringVersion.MONITORING_V3
        except (IMRegisterNotExist, ILIOError):
            # The Monitoring V3 is NOT available
            pass
        try:
            self.mc.communication.get_register(
                self.MONITORING_CURRENT_NUMBER_BYTES_REGISTER, servo=servo, axis=0
            )
            return MonitoringVersion.MONITORING_V2
        except (IMRegisterNotExist, ILIOError):
            # The Monitoring V2 is NOT available
            pass
        try:
            self.mc.communication.get_register(self.MONITORING_STATUS_REGISTER, servo=servo, axis=0)
            return MonitoringVersion.MONITORING_V1
        except (IMRegisterNotExist, ILIOError):
            # Monitoring/disturbance are not available
            raise NotImplementedError(
                "The monitoring and disturbance features are not available for this drive"
            )

    def enable_monitoring_disturbance(self, servo: str = DEFAULT_SERVO) -> None:
        """Enable monitoring and disturbance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            IMMonitoringError: If monitoring can't be enabled.

        """
        self.enable_monitoring(servo=servo)
        self.enable_disturbance(servo=servo)

    def enable_monitoring(self, servo: str = DEFAULT_SERVO) -> None:
        """Enable monitoring.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            IMMonitoringError: If monitoring can't be enabled.

        """
        drive = self.mc.servos[servo]
        drive.monitoring_enable()
        # Check monitoring status
        if not self.is_monitoring_enabled(servo=servo):
            raise IMMonitoringError("Error enabling monitoring.")

    def enable_disturbance(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> None:
        """Enable disturbance.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
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

    def disable_monitoring_disturbance(self, servo: str = DEFAULT_SERVO) -> None:
        """Disable monitoring and disturbance.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        self.disable_monitoring(servo=servo)
        self.disable_disturbance(servo=servo)

    def disable_monitoring(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> None:
        """Disable monitoring.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        """
        if version is None:
            version = self._check_version(servo)
        if not self.is_monitoring_enabled(servo=servo):
            return
        drive = self.mc.servos[servo]
        drive.monitoring_disable()
        if version >= MonitoringVersion.MONITORING_V3:
            drive.monitoring_remove_data()

    def disable_disturbance(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> None:
        """Disable disturbance.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
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
        drive.disturbance_remove_data()

    def get_monitoring_disturbance_status(self, servo: str = DEFAULT_SERVO) -> int:
        """Get Monitoring Status.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Monitoring/Disturbance Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
            TypeError: If some read value has a wrong type.

        """
        monitoring_disturbance_status = self.mc.communication.get_register(
            self.MONITORING_STATUS_REGISTER, servo=servo, axis=0
        )
        if not isinstance(monitoring_disturbance_status, int):
            raise TypeError("Monitoring and disturbance status value has to be an integer")
        return monitoring_disturbance_status

    def get_monitoring_status(self, servo: str = DEFAULT_SERVO) -> int:
        """Get Monitoring Status.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Monitoring Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
            TypeError: If some read value has a wrong type.

        """
        monitoring_status = self.mc.communication.get_register(
            self.MONITORING_STATUS_REGISTER, servo=servo, axis=0
        )
        if not isinstance(monitoring_status, int):
            raise TypeError("Monitoring status value has to be an integer")
        return monitoring_status

    def get_disturbance_status(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> int:
        """Get Disturbance Status.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            Disturbance Status.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.
            TypeError: If some read value has a wrong type.

        """
        if version is None:
            version = self._check_version(servo)
        if version < MonitoringVersion.MONITORING_V3:
            disturbance_status = self.mc.communication.get_register(
                self.MONITORING_STATUS_REGISTER, servo=servo, axis=0
            )
        else:
            disturbance_status = self.mc.communication.get_register(
                self.DISTURBANCE_STATUS_REGISTER, servo=servo, axis=0
            )
        if not isinstance(disturbance_status, int):
            raise TypeError("Disturbance status value has to be an integer")
        return disturbance_status

    def is_monitoring_enabled(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if monitoring is enabled.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            True if monitoring is enabled, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.

        """
        monitor_status = self.get_monitoring_status(servo)
        return (monitor_status & self.MONITORING_STATUS_ENABLED_BIT) == 1

    def is_disturbance_enabled(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> bool:
        """Check if disturbance is enabled.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            True if disturbance is enabled, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.

        """
        monitor_status = self.get_disturbance_status(servo, version=version)
        return (monitor_status & self.DISTURBANCE_STATUS_ENABLED_BIT) == 1

    def get_monitoring_process_stage(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> MonitoringProcessStage:
        """
        Return monitoring process stage.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            Current monitoring process stage.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.

        """
        if version is None:
            version = self._check_version(servo=servo)
        monitor_status = self.mc.capture.get_monitoring_status(servo=servo)
        mask = self.MONITORING_STATUS_PROCESS_STAGE_BITS[version]
        masked_value = monitor_status & mask
        return MonitoringProcessStage(masked_value)

    def is_frame_available(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> bool:
        """
        Check if monitoring has an available frame.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if ``None`` reads from drive. ``None`` by default.

        Returns:
            True if monitoring has an available frame, else False.

        Raises:
            IMRegisterNotExist: If the register doesn't exist.

        """
        if version is None:
            version = self._check_version(servo=servo)
        monitor_status = self.mc.capture.get_monitoring_status(servo=servo)
        mask = self.MONITORING_AVAILABLE_FRAME_BIT[version]
        return (monitor_status & mask) != 0

    def clean_monitoring(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> None:
        """Disable monitoring/disturbance and remove monitoring mapped registers.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if None reads from drive. ``None`` by default.

        """
        self.disable_monitoring(servo=servo, version=version)
        drive = self.mc.servos[servo]
        drive.monitoring_remove_all_mapped_registers()

    def clean_disturbance(
        self, servo: str = DEFAULT_SERVO, version: Optional[MonitoringVersion] = None
    ) -> None:
        """Disable monitoring/disturbance and remove disturbance mapped registers.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            version : Monitoring/Disturbance version,
                if None reads from drive. ``None`` by default.

        """
        self.disable_disturbance(servo=servo, version=version)
        drive = self.mc.servos[servo]
        drive.disturbance_remove_all_mapped_registers()

    def clean_monitoring_disturbance(self, servo: str = DEFAULT_SERVO) -> None:
        """Disable monitoring/disturbance, remove disturbance and monitoring
        mapped registers.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        self.clean_monitoring(servo=servo)
        self.clean_disturbance(servo=servo)

    def mcb_synchronization(self, servo: str = DEFAULT_SERVO) -> None:
        """Synchronize MCB, necessary to monitoring and disturbance.
        Motor must be disabled.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.

        """
        for subnode in [
            subnode
            for subnode, subnode_type in self.mc.info.get_subnodes(servo).items()
            if subnode_type == SubnodeType.MOTION
        ]:
            if self.mc.configuration.is_motor_enabled(servo=servo, axis=subnode):
                raise IMStatusWordError("Motor is enabled")
        self.enable_monitoring(servo=servo)
        self.disable_monitoring(servo=servo)

    def disturbance_max_sample_size(self, servo: str = DEFAULT_SERVO) -> int:
        """Return disturbance max size, in bytes.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Max buffer size in bytes.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        try:
            max_sample_size = self.mc.communication.get_register(
                self.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER, servo=servo, axis=0
            )
            if not isinstance(max_sample_size, int):
                raise TypeError("Maximum sample size has to be an integer")
            return max_sample_size
        except IMRegisterNotExist:
            return self.MINIMUM_BUFFER_SIZE

    def monitoring_max_sample_size(self, servo: str = DEFAULT_SERVO) -> int:
        """Return monitoring max size, in bytes.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        Returns:
            Max buffer size in bytes.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        try:
            max_sample_size = self.mc.communication.get_register(
                self.MONITORING_MAXIMUM_SAMPLE_SIZE_REGISTER, servo=servo, axis=0
            )
            if not isinstance(max_sample_size, int):
                raise TypeError("Maximum sample size has to be an integer")
            return max_sample_size
        except IMRegisterNotExist:
            return self.MINIMUM_BUFFER_SIZE

    def get_frequency(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Returns the monitoring frequency.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Sampling rate in Hz.

        Raises:
            TypeError: If some read value has a wrong type.

        """

        position_velocity_loop_rate = self.mc.configuration.get_position_and_velocity_loop_rate(
            servo=servo, axis=axis
        )
        prescaler = self.mc.communication.get_register(
            self.MONITORING_FREQUENCY_DIVIDER_REGISTER, servo=servo, axis=0
        )
        if not isinstance(prescaler, int):
            raise TypeError("Monitoring loop frequency divider has to be an integer")
        sampling_freq = round(position_velocity_loop_rate / prescaler, 2)
        return sampling_freq
