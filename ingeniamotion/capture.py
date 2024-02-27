import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Union, Tuple, Type, Callable

import numpy as np
from numpy.typing import NDArray
from ingenialink.exceptions import ILIOError
from ingenialink.pdo import RPDOMap, TPDOMap, RPDOMapItem, TPDOMapItem
from ingenialink.poller import Poller
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.register import EthercatRegister

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
    IMException,
)
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass
from ingeniamotion.monitoring.base_monitoring import Monitoring
from ingeniamotion.monitoring.monitoring_v1 import MonitoringV1
from ingeniamotion.monitoring.monitoring_v3 import MonitoringV3

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class PDONetworkManager:
    """Manage all the PDO functionalities.

    Attributes:
        mc: The MotionController.

    """

    class ProcessDataThread(threading.Thread):
        """Manage the PDO exchange.

        Attributes:
            net: The EthercatNetwork instance where the PDOs will be active.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.

        """

        DEFAULT_PDO_REFRESH_RATE = 0.01
        MINIMUM_PDO_REFRESH_RATE = 4
        ETHERCAT_PDO_WATCHDOG = "processdata"

        def __init__(
            self,
            net: EthercatNetwork,
            refresh_rate: Optional[float],
            notify_send_process_data: Optional[Callable[[], None]] = None,
            notify_receive_process_data: Optional[Callable[[], None]] = None,
        ) -> None:
            super().__init__()
            self._net = net
            if refresh_rate is None:
                refresh_rate = self.DEFAULT_PDO_REFRESH_RATE
            elif refresh_rate > self.MINIMUM_PDO_REFRESH_RATE:
                raise ValueError(
                    f"The minimum PDO refresh rate is {self.MINIMUM_PDO_REFRESH_RATE} seconds."
                )
            self._refresh_rate = refresh_rate
            self._pd_thread_stop_event = threading.Event()
            for servo in self._net.servos:
                servo.slave.set_watchdog(self.ETHERCAT_PDO_WATCHDOG, self._refresh_rate * 1500)
            self._notify_send_process_data = notify_send_process_data
            self._notify_receive_process_data = notify_receive_process_data

        def run(self) -> None:
            """Start the PDO exchange"""
            self._net.start_pdos()
            while not self._pd_thread_stop_event.is_set():
                if self._notify_send_process_data is not None:
                    self._notify_send_process_data()
                self._net.send_receive_processdata()
                if self._notify_receive_process_data is not None:
                    self._notify_receive_process_data()
                time.sleep(self._refresh_rate)

        def stop(self) -> None:
            """Stop the PDO exchange"""
            self._pd_thread_stop_event.set()
            self.join()

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self._pdo_thread: Optional[PDONetworkManager.ProcessDataThread] = None
        self._pdo_send_observers: List[Callable[[], None]] = []
        self._pdo_receive_observers: List[Callable[[], None]] = []

    def create_pdo_item(
        self,
        register_uid: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
        value: Optional[Union[int, float]] = None,
    ) -> Union[RPDOMapItem, TPDOMapItem]:
        """
        Create a PDOMapItem by specifying a register UID.

        Args:
            register_uid: Register to be mapped.
            axis: servo axis. ``1`` by default.
            servo: servo alias to reference it. ``default`` by default.
            value: Initial value for an RPDO register.

        Returns:
            Mappable PDO item.

        Raises:
            ValueError: If there is a type mismatch retrieving the register object.
            AttributeError: If an initial value is not provided for an RPDO register.

        """
        pdo_map_item_dict: Dict[str, Type[Union[RPDOMapItem, TPDOMapItem]]] = {
            "CYCLIC_RX": RPDOMapItem,
            "CYCLIC_TX": TPDOMapItem,
        }
        drive = self.mc._get_drive(servo)
        register = drive.dictionary.registers(axis)[register_uid]
        if not isinstance(register, EthercatRegister):
            raise ValueError(f"Expected EthercatRegister. Got {type(register)}")
        pdo_map_item = pdo_map_item_dict[register.cyclic](register)
        if isinstance(pdo_map_item, RPDOMapItem):
            if value is None:
                raise AttributeError("A initial value is required for a RPDO.")
            pdo_map_item.value = value
        return pdo_map_item

    def create_pdo_maps(
        self,
        rpdo_map_items: Union[RPDOMapItem, List[RPDOMapItem]],
        tpdo_map_items: Union[TPDOMapItem, List[TPDOMapItem]],
    ) -> Tuple[RPDOMap, TPDOMap]:
        """
        Create the RPDO and TPDO maps from PDOMapItems.

        Args:
            rpdo_map_items: The RPDOMapItems to be added to a RPDOMap.
            tpdo_map_items: The TDOMapItems to be added to a TPDOMap.

        Returns:
            RPDO and TPDO maps.

        """
        rpdo_map = self.create_empty_rpdo_map()
        tpdo_map = self.create_empty_tpdo_map()
        if not isinstance(rpdo_map_items, list):
            rpdo_map_items = [rpdo_map_items]
        if not isinstance(tpdo_map_items, list):
            tpdo_map_items = [tpdo_map_items]
        for rpdo_map_item in rpdo_map_items:
            self.add_pdo_item_to_map(rpdo_map_item, rpdo_map)
        for tpdo_map_item in tpdo_map_items:
            self.add_pdo_item_to_map(tpdo_map_item, tpdo_map)
        return rpdo_map, tpdo_map

    @staticmethod
    def add_pdo_item_to_map(
        pdo_map_item: Union[RPDOMapItem, TPDOMapItem],
        pdo_map: Union[RPDOMap, TPDOMap],
    ) -> None:
        """
        Add a PDOMapItem to a PDOMap.

        Args:
            pdo_map_item: The PDOMapItem.
            pdo_map: The PDOMap to add the PDOMapItem.

        Raises:
            ValueError: If an RPDOItem is tried to be added to a TPDOMap.
            ValueError: If an TPDOItem is tried to be added to a RPDOMap.

        """
        if isinstance(pdo_map_item, RPDOMapItem) and not isinstance(pdo_map, RPDOMap):
            raise ValueError("Cannot add a RPDOItem to a TPDOMap")
        if isinstance(pdo_map_item, TPDOMapItem) and not isinstance(pdo_map, TPDOMap):
            raise ValueError("Cannot add a TPDOItem to a RPDOMap")
        pdo_map.add_item(pdo_map_item)

    @staticmethod
    def create_empty_rpdo_map() -> RPDOMap:
        """
        Create an empty RPDOMap.

        Returns:
            The empty RPDOMap.

        """
        return RPDOMap()

    @staticmethod
    def create_empty_tpdo_map() -> TPDOMap:
        """
        Create an empty TPDOMap.

        Returns:
            The empty TPDOMap.

        """
        return TPDOMap()

    def set_pdo_maps_to_slave(
        self,
        rpdo_maps: Union[RPDOMap, List[RPDOMap]],
        tpdo_maps: Union[TPDOMap, List[TPDOMap]],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """
        Map the PDOMaps to the slave.

        Args:
            rpdo_maps: The RPDOMaps to be mapped.
            tpdo_maps: he TPDOMaps to be mapped.
            servo: servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.
            ValueError: If not all instances of a RPDOMap are in the RPDOMaps to be mapped.
            ValueError: If not all instances of a TPDOMap are in the TPDOMaps to be mapped.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        if not isinstance(rpdo_maps, list):
            rpdo_maps = [rpdo_maps]
        if not isinstance(tpdo_maps, list):
            tpdo_maps = [tpdo_maps]
        if not all(isinstance(rpdo_map, RPDOMap) for rpdo_map in rpdo_maps):
            raise ValueError("Not all elements of the RPDO map list are instances of a RPDO map")
        if not all(isinstance(tpdo_map, TPDOMap) for tpdo_map in tpdo_maps):
            raise ValueError("Not all elements of the TPDO map list are instances of a TPDO map")
        drive.set_pdo_map_to_slave(rpdo_maps, tpdo_maps)

    def clear_pdo_mapping(self, servo: str = DEFAULT_SERVO) -> None:
        """
        Clear the PDO mapping within the servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        drive.reset_rpdo_mapping()
        drive.reset_tpdo_mapping()

    def start_pdos(
        self,
        interface_name: str,
        refresh_rate: Optional[float] = None,
    ) -> None:
        """
        Start the PDO exchange process.

        Args:
            interface_name: The interface name where the slaves are connected to.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.

        Raises:
            ValueError: If the refresh rate is too high.
            IMException: If the PDOs are already active.

        """
        net = self.mc.get_network_by_interface_name(interface_name)
        if self._pdo_thread is not None:
            self._pdo_thread.stop()
            raise IMException(f"PDOs are already active on interface: {interface_name}")
        self._pdo_thread = self.ProcessDataThread(
            net, refresh_rate, self._notify_send_process_data, self._notify_receive_process_data
        )
        self._pdo_thread.start()

    def stop_pdos(self) -> None:
        """
        Stop the PDO exchange process.

        Raises:
            IMException: If the PDOs are not active yet.

        """
        if self._pdo_thread is None:
            raise IMException("The PDO exchange has not started yet.")
        self._pdo_thread.stop()

    def subscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the RPDO values will be sent.

        Args:
            callback: Callback function.

        """
        if callback in self._pdo_send_observers:
            return
        self._pdo_send_observers.append(callback)

    def subscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the TPDO values are received.

        Args:
            callback: Callback function.

        """
        if callback in self._pdo_receive_observers:
            return
        self._pdo_receive_observers.append(callback)

    def unsubscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the send process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._pdo_send_observers:
            return
        self._pdo_send_observers.remove(callback)

    def unsubscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the receive process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._pdo_receive_observers:
            return
        self._pdo_receive_observers.remove(callback)

    def _notify_send_process_data(self) -> None:
        """Notify subscribers that the RPDO values will be sent."""
        for callback in self._pdo_send_observers:
            callback()

    def _notify_receive_process_data(self) -> None:
        """Notify subscribers that the TPDO values were received."""
        for callback in self._pdo_receive_observers:
            callback()


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
        drive = self.mc._get_drive(servo)
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
        subnodes = self.mc.info.get_subnodes(servo)
        for axis in range(1, subnodes):
            if self.mc.configuration.is_motor_enabled(servo=servo, axis=axis):
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
