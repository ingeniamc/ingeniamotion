import re
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Callable, Deque, Dict, List, Optional, Tuple, Type, Union

import ingenialogger
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError, ILWrongWorkingCountError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem

from ingeniamotion.enums import COMMUNICATION_TYPE
from ingeniamotion.exceptions import IMException
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class PDOPoller:
    """Poll register values using PDOs"""

    def __init__(
        self,
        mc: "MotionController",
        servo: str,
        refresh_time: float,
        watchdog_timeout: Optional[float],
        buffer_size: int,
    ) -> None:
        """Constructor.

        Args:
            mc: MotionController instance
            servo: drive alias.
            refresh_time: PDO values refresh time.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.
            buffer_size: Maximum number of register readings to store.

        """
        super().__init__()
        self.__mc = mc
        self.__servo = servo
        self.__refresh_time = refresh_time
        self.__watchdog_timeout = watchdog_timeout
        self.__buffer_size = buffer_size
        self.__buffer: Deque[tuple[float, List[Union[int, float, bytes]]]] = deque(
            maxlen=self.__buffer_size
        )
        self.__start_time: Optional[float] = None
        self.__tpdo_map: TPDOMap = self.__mc.capture.pdo.create_empty_tpdo_map()
        self.__rpdo_map: RPDOMap = self.__mc.capture.pdo.create_empty_rpdo_map()
        self.__fill_rpdo_map()
        self.__exception_callbacks: List[Callable[[IMException], None]] = []

    def start(self) -> None:
        """Start the poller"""
        self.__mc.capture.pdo.set_pdo_maps_to_slave(
            self.__rpdo_map, self.__tpdo_map, servo=self.__servo
        )
        self.__mc.capture.pdo.subscribe_to_receive_process_data(self._new_data_available)
        for callback in self.__exception_callbacks:
            self.__mc.capture.pdo.subscribe_to_exceptions(callback)
        self.__start_time = time.time()
        self.__mc.capture.pdo.start_pdos(
            refresh_rate=self.__refresh_time, watchdog_timeout=self.__watchdog_timeout
        )

    def stop(self) -> None:
        """Stop the poller"""
        self.__mc.capture.pdo.stop_pdos()
        self.__mc.capture.pdo.unsubscribe_to_receive_process_data(self._new_data_available)
        for callback in self.__exception_callbacks:
            self.__mc.capture.pdo.unsubscribe_to_exceptions(callback)
        self.__mc.capture.pdo.remove_rpdo_map(self.__servo, self.__rpdo_map)
        self.__mc.capture.pdo.remove_tpdo_map(self.__servo, self.__tpdo_map)

    @property
    def data(self) -> Tuple[List[float], List[List[Union[int, float, bytes]]]]:
        """
        Get the poller data. After the data is retrieved, the data buffers are cleared.

        Returns:
            A tuple with a list of the readings timestamps and a list of lists with
            the readings values.

        """
        time_stamps = []
        data: List[List[Union[int, float, bytes]]] = [[] for _ in range(len(self.__tpdo_map.items))]
        for _ in range(len(self.__buffer)):
            time_stamp, data_sample = self.__buffer.popleft()
            time_stamps.append(time_stamp)
            for item_index in range(len(self.__tpdo_map.items)):
                data[item_index].append(data_sample[item_index])

        return time_stamps, data

    def add_channels(self, registers: List[Dict[str, Union[int, str]]]) -> None:
        """
        Configure the PDOs with the registers to be read.

        Args:
            registers : list of registers to add to the Poller.

        """
        self.__fill_tpdo_map(registers)

    def subscribe_to_exceptions(self, callback: Callable[[IMException], None]) -> None:
        """Get notified when an exception occurs on the PDO thread.

        Args:
            callback: Function to be called when an exception occurs.

        """
        self.__exception_callbacks.append(callback)

    def _new_data_available(self) -> None:
        """Add readings to the buffers.

        Raises:
            ValueError: If the poller has not been started yet.

        """
        if self.__start_time is None:
            raise ValueError("The poller has not been started yet.")
        time_stamp = round(time.time() - self.__start_time, 6)
        data_sample = []
        for tpdo_map_item in self.__tpdo_map.items:
            data_sample.append(tpdo_map_item.value)
        self.__buffer.append((time_stamp, data_sample))

    def __fill_rpdo_map(self) -> None:
        """Fill the RPDO Map with padding"""
        padding_rpdo_item = RPDOMapItem(size_bits=8)
        padding_rpdo_item.raw_data_bytes = int.to_bytes(0, 1, "little")
        self.__mc.capture.pdo.add_pdo_item_to_map(padding_rpdo_item, self.__rpdo_map)

    def __fill_tpdo_map(self, registers: List[Dict[str, Union[int, str]]]) -> None:
        """Fill the TPDO Map with the registers to be polled.

        Raises:
            ValueError: If there is a type mismatch when retrieving the register UID.
            ValueError: If there is a type mismatch when retrieving the register axis.

        """
        for register in registers:
            name = register.get("name", DEFAULT_SERVO)
            if not isinstance(name, str):
                raise ValueError(
                    f"Wrong type for the 'name' field. Expected 'str', got: {type(name)}"
                )
            axis = register.get("axis", DEFAULT_AXIS)
            if not isinstance(axis, int):
                raise ValueError(
                    f"Wrong type for the 'axis' field. Expected 'int', got: {type(axis)}"
                )
            tpdo_map_item = self.__mc.capture.pdo.create_pdo_item(
                name, axis=axis, servo=self.__servo
            )
            self.__mc.capture.pdo.add_pdo_item_to_map(tpdo_map_item, self.__tpdo_map)

    @property
    def available_samples(self) -> int:
        """Number of samples in the buffer."""
        return len(self.__buffer)


class PDONetworkManager:
    """Manage all the PDO functionalities.

    Args:
        mc: The MotionController.

    """

    class ProcessDataThread(threading.Thread):
        """Manage the PDO exchange.

        Args:
            net: The EthercatNetwork instance where the PDOs will be active.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.
            notify_send_process_data: Callback to notify when process data is about to be sent.
            notify_receive_process_data: Callback to notify when process data is received.
            notify_exceptions: Callback to notify when an exception is raised.

        Raises:
            ValueError: If the provided refresh rate is unfeasible.

        """

        DEFAULT_PDO_REFRESH_TIME = 0.01
        MINIMUM_PDO_REFRESH_TIME = 0.001
        DEFAULT_WATCHDOG_TIMEOUT = 0.1
        PDO_WATCHDOG_INCREMENT_FACTOR = 2
        # The time.sleep precision is 13 ms for Windows OS
        # https://stackoverflow.com/questions/1133857/how-accurate-is-pythons-time-sleep
        WINDOWS_TIME_SLEEP_PRECISION = 0.013

        def __init__(
            self,
            net: EthercatNetwork,
            refresh_rate: Optional[float],
            watchdog_timeout: Optional[float],
            notify_send_process_data: Optional[Callable[[], None]] = None,
            notify_receive_process_data: Optional[Callable[[], None]] = None,
            notify_exceptions: Optional[Callable[[IMException], None]] = None,
        ) -> None:
            super().__init__()
            self._net = net
            if refresh_rate is None:
                refresh_rate = self.DEFAULT_PDO_REFRESH_TIME
            elif refresh_rate < self.MINIMUM_PDO_REFRESH_TIME:
                raise ValueError(
                    f"The minimum PDO refresh rate is {self.MINIMUM_PDO_REFRESH_TIME} seconds."
                )
            self._refresh_rate = refresh_rate
            self._watchdog_timeout = watchdog_timeout
            self._notify_send_process_data = notify_send_process_data
            self._notify_receive_process_data = notify_receive_process_data
            self._notify_exceptions = notify_exceptions
            self._pd_thread_stop_event = threading.Event()

        def run(self) -> None:
            """Start the PDO exchange"""
            try:
                self.__set_watchdog_timeout()
            except IMException as e:
                if self._notify_exceptions is not None:
                    self._notify_exceptions(e)
                return
            first_iteration = True
            iteration_duration: float = -1
            while not self._pd_thread_stop_event.is_set():
                time_start = time.perf_counter()
                if self._notify_send_process_data is not None:
                    self._notify_send_process_data()
                try:
                    if first_iteration:
                        self._net.start_pdos()
                        first_iteration = False
                    else:
                        self._net.send_receive_processdata(self._refresh_rate)
                except ILWrongWorkingCountError as il_error:
                    self._pd_thread_stop_event.set()
                    self._net.stop_pdos()
                    duration_error = ""
                    if iteration_duration > self._watchdog_timeout:
                        duration_error = (
                            f"Last iteration took {iteration_duration * 1000:0.1f} ms which is "
                            f"higher than the watchdog timeout "
                            f"({self._watchdog_timeout * 1000:0.1f} ms). Please optimize the"
                            f" callbacks and/or increase the refresh rate/watchdog timeout."
                        )
                    if self._notify_exceptions is not None:
                        im_exception = IMException(
                            "Stopping the PDO thread due to the following exception:"
                            f" {il_error} {duration_error}"
                        )
                        self._notify_exceptions(im_exception)
                except ILError as il_error:
                    self._pd_thread_stop_event.set()
                    if self._notify_exceptions is not None:
                        im_exception = IMException(
                            f"Could not start the PDOs due to the following exception: {il_error}"
                        )
                        self._notify_exceptions(im_exception)
                else:
                    if self._notify_receive_process_data is not None:
                        self._notify_receive_process_data()
                    while (
                        remaining_loop_time := self._refresh_rate
                        - (time.perf_counter() - time_start)
                    ) > 0:
                        if remaining_loop_time > self.WINDOWS_TIME_SLEEP_PRECISION:
                            time.sleep(self.WINDOWS_TIME_SLEEP_PRECISION)
                        else:
                            self.high_precision_sleep(remaining_loop_time)
                    iteration_duration = time.perf_counter() - time_start

        def stop(self) -> None:
            """Stop the PDO exchange"""
            self._pd_thread_stop_event.set()
            self._net.stop_pdos()
            self.join()

        @staticmethod
        def high_precision_sleep(duration: float) -> None:
            """Replaces the time.sleep() method in order to obtain
            more precise sleeping times."""
            start_time = time.perf_counter()
            while duration - (time.perf_counter() - start_time) > 0:
                pass

        def __set_watchdog_timeout(self):
            is_watchdog_timeout_manually_set = self._watchdog_timeout is not None
            if not is_watchdog_timeout_manually_set:
                self._watchdog_timeout = max(
                    self.DEFAULT_WATCHDOG_TIMEOUT,
                    self._refresh_rate * self.PDO_WATCHDOG_INCREMENT_FACTOR,
                )
            try:
                for servo in self._net.servos:
                    servo.set_pdo_watchdog_time(self._watchdog_timeout)
            except AttributeError as e:
                max_pdo_watchdog = re.findall(r"\d+\.\d+|\d+", e.__str__())
                max_pdo_watchdog_ms = None
                if max_pdo_watchdog is not None and "." in max_pdo_watchdog[0]:
                    max_pdo_watchdog_ms = float(max_pdo_watchdog[0])
                if is_watchdog_timeout_manually_set:
                    error_msg = "The watchdog timeout is too high."
                    if max_pdo_watchdog_ms is not None:
                        error_msg += f" The max watchdog timeout is {max_pdo_watchdog_ms} ms."
                else:
                    error_msg = "The sampling time is too high."
                    if max_pdo_watchdog_ms is not None:
                        max_sampling_time = max_pdo_watchdog_ms / self.PDO_WATCHDOG_INCREMENT_FACTOR
                        error_msg += f" The max sampling time is {max_sampling_time} ms."
                raise IMException(error_msg) from e

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)
        self._pdo_thread: Optional[PDONetworkManager.ProcessDataThread] = None
        self._pdo_send_observers: List[Callable[[], None]] = []
        self._pdo_receive_observers: List[Callable[[], None]] = []
        self._pdo_exceptions_observers: List[Callable[[IMException], None]] = []

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
        pdo_map_item_dict: Dict[RegCyclicType, Type[Union[RPDOMapItem, TPDOMapItem]]] = {
            RegCyclicType.RX: RPDOMapItem,
            RegCyclicType.TX: TPDOMapItem,
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
            ValueError: If not all elements of the RPDO map list are instances of a RPDO map.
            ValueError: If not all elements of the TPDO map list are instances of a TPDO map.

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

    def remove_rpdo_map(
        self,
        servo: str = DEFAULT_SERVO,
        rpdo_map: Optional[RPDOMap] = None,
        rpdo_map_index: Optional[int] = None,
    ) -> None:
        """Remove a RPDOMap from the RPDOMap list. The RPDOMap instance or
        the index of the map in the RPDOMap list should be provided.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            rpdo_map: The RPDOMap instance to be removed.
            rpdo_map_index: The index of the RPDOMap list to be removed.

        Raises:
            ValueError: If the RPDOMap instance is not in the RPDOMap list.
            IndexError: If the index is out of range.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        drive.remove_rpdo_map(rpdo_map, rpdo_map_index)

    def remove_tpdo_map(
        self,
        servo: str = DEFAULT_SERVO,
        tpdo_map: Optional[TPDOMap] = None,
        tpdo_map_index: Optional[int] = None,
    ) -> None:
        """Remove a TPDOMap from the TPDOMap list. The TPDOMap instance or
        the index of the map in the TPDOMap list should be provided.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            tpdo_map: The TPDOMap instance to be removed.
            tpdo_map_index: The index of the TPDOMap list to be removed.

        Raises:
            ValueError: If the TPDOMap instance is not in the TPDOMap list.
            IndexError: If the index is out of range.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        drive.remove_tpdo_map(tpdo_map, tpdo_map_index)

    def start_pdos(
        self,
        network_type: Optional[COMMUNICATION_TYPE] = None,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
    ) -> None:
        """
        Start the PDO exchange process.

        Args:
            network_type: Network type (EtherCAT or CANopen) on which to start the PDO exchange.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.

        Raises:
            ValueError: If the refresh rate is too high.
            ValueError: If the MotionController is connected to more than one Network.
            ValueError: If network_type argument is invalid.
            IMException: If the MotionController is connected to more than one Network.
            ValueError: If there is a type mismatch retrieving the network object.
            IMException: If the PDOs are already active.

        """
        if network_type is None:
            if len(self.mc.net) > 1:
                raise ValueError(
                    "There is more than one network created. The network_type argument must be"
                    " provided."
                )
            net = next(iter(self.mc.net.values()))
        elif not isinstance(network_type, COMMUNICATION_TYPE):
            raise ValueError(
                f"Wrong value for the network_type argument. Must be of type {COMMUNICATION_TYPE}"
            )
        elif network_type == COMMUNICATION_TYPE.Canopen:
            raise NotImplementedError
        else:
            ethercat_networks = [
                network for network in self.mc.net.values() if isinstance(network, EthercatNetwork)
            ]
            canopen_networks = [
                network for network in self.mc.net.values() if isinstance(network, CanopenNetwork)
            ]
            if len(ethercat_networks) > 1 or len(canopen_networks) > 1:
                raise IMException(
                    "When using PDOs only one instance per network type is allowed. "
                    f"Got {len(ethercat_networks)} instances of EthercatNetwork "
                    f"and {len(canopen_networks)} of CanopenNetwork."
                )
            net = (
                ethercat_networks[0]
                if network_type == COMMUNICATION_TYPE.Ethercat
                else canopen_networks[0]
            )
        if self._pdo_thread is not None:
            self.stop_pdos()
            raise IMException("PDOs are already active.")
        if not isinstance(net, EthercatNetwork):
            raise ValueError(f"Expected EthercatNetwork. Got {type(net)}")
        self._pdo_thread = self.ProcessDataThread(
            net,
            refresh_rate,
            watchdog_timeout,
            self._notify_send_process_data,
            self._notify_receive_process_data,
            self._notify_exceptions,
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
        self._pdo_thread = None

    @property
    def is_active(self) -> bool:
        """Check if the PDO thread is active.

        Returns:
            True if the PDO thread is active. False otherwise.

        """
        if self._pdo_thread is None:
            return False
        return self._pdo_thread.is_alive()

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

    def subscribe_to_exceptions(self, callback: Callable[[IMException], None]) -> None:
        """Subscribe be notified when there is an exception in the PDO process data thread.

        If a callback is subscribed, the PDO exchange process is paused when an exception is raised.
        It can be resumed using the `resume_pdos` method.

        Args:
            callback: Callback function.

        """
        if callback in self._pdo_exceptions_observers:
            return
        self._pdo_exceptions_observers.append(callback)

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

    def create_poller(
        self,
        registers: List[Dict[str, Union[int, str]]],
        servo: str = DEFAULT_SERVO,
        sampling_time: float = 0.125,
        buffer_size: int = 100,
        watchdog_timeout: Optional[float] = None,
        start: bool = True,
    ) -> PDOPoller:
        """
        Create a register Poller using PDOs.

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
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.
            buffer_size: number maximum of sample for each data read.
                ``100`` by default.
            start: if ``True``, function starts poller, if ``False``
                poller should be started after. ``True`` by default.

        Returns:
            The poller instance.

        """
        poller = PDOPoller(self.mc, servo, sampling_time, watchdog_timeout, buffer_size)
        poller.add_channels(registers)
        if start:
            poller.start()
        return poller

    def unsubscribe_to_exceptions(self, callback: Callable[[IMException], None]) -> None:
        """Unsubscribe from the exceptions in the process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._pdo_exceptions_observers:
            return
        self._pdo_exceptions_observers.remove(callback)

    def _notify_send_process_data(self) -> None:
        """Notify subscribers that the RPDO values will be sent."""
        for callback in self._pdo_send_observers:
            callback()

    def _notify_receive_process_data(self) -> None:
        """Notify subscribers that the TPDO values were received."""
        for callback in self._pdo_receive_observers:
            callback()

    def _notify_exceptions(self, exc: IMException) -> None:
        """Notify subscribers that there were an exception.

        Args:
            exc: Exception that was raised in the PDO process data thread.
        """
        self.logger.error(exc)
        for callback in self._pdo_exceptions_observers:
            callback(exc)
