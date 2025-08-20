import time
from collections import deque
from typing import TYPE_CHECKING, Callable, Optional, Union, cast

from ingenialink.canopen.network import CanopenNetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError
from ingenialink.pdo import PDOMap, RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem

from ingeniamotion.enums import CommunicationType
from ingeniamotion.exceptions import IMError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class PDOPoller:
    """Poll register values using PDOs."""

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
        self.__servo = cast("EthercatServo", self.__mc._get_drive(servo=servo))
        self.__net = cast("EthercatNetwork", self.__mc._get_network(servo=servo))
        self.__refresh_time = refresh_time
        self.__watchdog_timeout = watchdog_timeout
        self.__buffer_size = buffer_size
        self.__buffer: deque[tuple[float, list[Union[int, float, bytes]]]] = deque(
            maxlen=self.__buffer_size
        )
        self.__start_time: Optional[float] = None
        self.__tpdo_map: TPDOMap = TPDOMap()
        self.__rpdo_map: RPDOMap = RPDOMap()
        self.__fill_rpdo_map()
        self.__exception_callbacks: list[Callable[[ILError], None]] = []

    def start(self) -> None:
        """Start the poller."""
        self.__servo.set_pdo_map_to_slave(rpdo_maps=self.__rpdo_map, tpdo_maps=self.__tpdo_map)
        self.__net.pdo_manager.subscribe_to_receive_process_data(self._new_data_available)
        for callback in self.__exception_callbacks:
            self.__net.pdo_manager.subscribe_to_exceptions(callback)
        self.__start_time = time.time()
        self.__net.activate_pdos(
            refresh_rate=self.__refresh_time, watchdog_timeout=self.__watchdog_timeout
        )

    def stop(self) -> None:
        """Stop the poller."""
        self.__net.deactivate_pdos()
        self.__net.pdo_manager.unsubscribe_to_receive_process_data(self._new_data_available)
        for callback in self.__exception_callbacks:
            self.__net.pdo_manager.unsubscribe_to_exceptions(callback)
        self.__servo.remove_rpdo_map(rpdo_map=self.__rpdo_map)
        self.__servo.remove_tpdo_map(tpdo_map=self.__tpdo_map)

    @classmethod
    def create_poller(
        cls,
        mc: "MotionController",
        registers: list[dict[str, Union[int, str]]],
        servo: str = DEFAULT_SERVO,
        sampling_time: float = 0.125,
        buffer_size: int = 100,
        watchdog_timeout: Optional[float] = None,
        start: bool = True,
    ) -> "PDOPoller":
        """Create a register Poller using PDOs.

        Args:
            mc: MotionController instance.
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
        poller = cls(
            mc=mc,
            servo=servo,
            refresh_time=sampling_time,
            watchdog_timeout=watchdog_timeout,
            buffer_size=buffer_size,
        )
        poller.add_channels(registers)
        if start:
            poller.start()
        return poller

    @property
    def data(self) -> tuple[list[float], list[list[Union[int, float, bytes]]]]:
        """Get the poller data. After the data is retrieved, the data buffers are cleared.

        Returns:
            A tuple with a list of the readings timestamps and a list of lists with
            the readings values.

        """
        time_stamps = []
        data: list[list[Union[int, float, bytes]]] = [[] for _ in range(len(self.__tpdo_map.items))]
        for _ in range(len(self.__buffer)):
            time_stamp, data_sample = self.__buffer.popleft()
            time_stamps.append(time_stamp)
            for item_index in range(len(self.__tpdo_map.items)):
                data[item_index].append(data_sample[item_index])

        return time_stamps, data

    def add_channels(self, registers: list[dict[str, Union[int, str]]]) -> None:
        """Configure the PDOs with the registers to be read.

        Args:
            registers : list of registers to add to the Poller.

        """
        self.__fill_tpdo_map(registers)

    def subscribe_to_exceptions(self, callback: Callable[[ILError], None]) -> None:
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
        data_sample = [tpdo_map_item.value for tpdo_map_item in self.__tpdo_map.items]
        self.__buffer.append((time_stamp, data_sample))

    def __fill_rpdo_map(self) -> None:
        """Fill the RPDO Map with padding."""
        padding_rpdo_item = RPDOMapItem(size_bits=8)
        padding_rpdo_item.raw_data_bytes = int.to_bytes(0, 1, "little")
        self.__rpdo_map.add_item(padding_rpdo_item)

    def __fill_tpdo_map(self, registers: list[dict[str, Union[int, str]]]) -> None:
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
            tpdo_map_item = PDOMap.create_item_from_register_uid(
                uid=name, axis=axis, dictionary=self.__servo.dictionary
            )
            self.__tpdo_map.add_item(tpdo_map_item)

    @property
    def available_samples(self) -> int:
        """Number of samples in the buffer."""
        return len(self.__buffer)


class PDONetworkManager:
    """Manage all the PDO functionalities.

    Args:
        mc: The MotionController.
    """

    def __init__(self, motion_controller: "MotionController") -> None:
        self.__mc = motion_controller
        self.__pdo_thread_status: bool = False

        # Reference to the network that has started the PDOs
        self.__net: Optional[EthercatNetwork] = None

        # Save the callbacks to add/remove, manage them when there is a reference to the network
        self.__send_process_data_add_callback: list[Callable[[], None]] = []
        self.__receive_process_data_add_callback: list[Callable[[], None]] = []
        self.__exception_add_callback: list[Callable[[ILError], None]] = []
        self.__send_process_data_remove_callback: list[Callable[[], None]] = []
        self.__receive_process_data_remove_callback: list[Callable[[], None]] = []
        self.__exception_remove_callback: list[Callable[[ILError], None]] = []

    def __evaluate_subscriptions(self, net: EthercatNetwork) -> None:
        for callback in self.__send_process_data_add_callback:
            net.pdo_manager.subscribe_to_send_process_data(callback)
        for callback in self.__receive_process_data_add_callback:
            net.pdo_manager.subscribe_to_receive_process_data(callback)
        for exception_callback in self.__exception_add_callback:
            net.pdo_manager.subscribe_to_exceptions(exception_callback)
        for callback in self.__send_process_data_remove_callback:
            net.pdo_manager.unsubscribe_to_send_process_data(callback)
        for callback in self.__receive_process_data_remove_callback:
            net.pdo_manager.unsubscribe_to_receive_process_data(callback)
        for exception_callback in self.__exception_remove_callback:
            net.pdo_manager.unsubscribe_to_exceptions(exception_callback)

    def __get_drive_and_network(self, servo: str) -> tuple[EthercatServo, EthercatNetwork]:
        drive = self.__mc._get_drive(servo)
        net = self.__mc._get_network(servo=servo)
        return cast("EthercatServo", drive), cast("EthercatNetwork", net)

    def create_pdo_item(
        self,
        register_uid: str,
        axis: int = DEFAULT_AXIS,
        servo: str = DEFAULT_SERVO,
        value: Optional[Union[int, float]] = None,
    ) -> Union[RPDOMapItem, TPDOMapItem]:
        """Create a PDOMapItem by specifying a register UID.

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
        drive = self.__mc._get_drive(servo=servo)
        return PDOMap.create_item_from_register_uid(
            uid=register_uid, axis=axis, dictionary=drive.dictionary, value=value
        )

    @staticmethod
    def create_pdo_maps(
        rpdo_map_items: Union[RPDOMapItem, list[RPDOMapItem]],
        tpdo_map_items: Union[TPDOMapItem, list[TPDOMapItem]],
    ) -> tuple[RPDOMap, TPDOMap]:
        """Create the RPDO and TPDO maps from PDOMapItems.

        Args:
            rpdo_map_items: The RPDOMapItems to be added to a RPDOMap.
            tpdo_map_items: The TDOMapItems to be added to a TPDOMap.

        Returns:
            RPDO and TPDO maps.

        """
        rpdo_map = RPDOMap.from_pdo_items(rpdo_map_items)
        tpdo_map = TPDOMap.from_pdo_items(tpdo_map_items)
        return rpdo_map, tpdo_map

    @staticmethod
    def create_empty_rpdo_map() -> RPDOMap:
        """Create an empty RPDOMap.

        Returns:
            The empty RPDOMap.

        """
        return RPDOMap()

    @staticmethod
    def create_empty_tpdo_map() -> TPDOMap:
        """Create an empty TPDOMap.

        Returns:
            The empty TPDOMap.

        """
        return TPDOMap()

    def set_pdo_maps_to_slave(
        self,
        rpdo_maps: Union[RPDOMap, list[RPDOMap]],
        tpdo_maps: Union[TPDOMap, list[TPDOMap]],
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Map the PDOMaps to the slave.

        Args:
            rpdo_maps: The RPDOMaps to be mapped.
            tpdo_maps: he TPDOMaps to be mapped.
            servo: servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.
            ValueError: If not all elements of the RPDO map list are instances of a RPDO map.
            ValueError: If not all elements of the TPDO map list are instances of a TPDO map.
        """
        drive = self.__mc._get_drive(servo=servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        if not all(isinstance(rpdo_map, RPDOMap) for rpdo_map in rpdo_maps):
            raise ValueError("Not all elements of the RPDO map list are instances of a RPDO map")
        if not all(isinstance(tpdo_map, TPDOMap) for tpdo_map in tpdo_maps):
            raise ValueError("Not all elements of the TPDO map list are instances of a TPDO map")
        drive.set_pdo_map_to_slave(rpdo_maps=rpdo_maps, tpdo_maps=tpdo_maps)

    def clear_pdo_mapping(self, servo: str = DEFAULT_SERVO) -> None:
        """Clear the PDO mapping within the servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.

        """
        drive, net = self.__get_drive_and_network(servo)
        net.pdo_manager.clear_pdo_mapping(servo=drive)

    def remove_rpdo_map(
        self,
        servo: str = DEFAULT_SERVO,
        rpdo_map: Optional[RPDOMap] = None,
        rpdo_map_index: Optional[int] = None,
    ) -> None:
        """Remove a RPDOMap from the RPDOMap list.

        The RPDOMap instance or the index of the map in the RPDOMap list
         should be provided.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            rpdo_map: The RPDOMap instance to be removed.
            rpdo_map_index: The index of the RPDOMap list to be removed.

        Raises:
            ValueError: If the RPDOMap instance is not in the RPDOMap list.
            IndexError: If the index is out of range.
        """
        drive, _ = self.__get_drive_and_network(servo)
        drive.remove_rpdo_map(rpdo_map=rpdo_map, rpdo_map_index=rpdo_map_index)

    def remove_tpdo_map(
        self,
        servo: str = DEFAULT_SERVO,
        tpdo_map: Optional[TPDOMap] = None,
        tpdo_map_index: Optional[int] = None,
    ) -> None:
        """Remove a TPDOMap from the TPDOMap list.

        The TPDOMap instance or the index of the map in the TPDOMap list
        should be provided.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            tpdo_map: The TPDOMap instance to be removed.
            tpdo_map_index: The index of the TPDOMap list to be removed.

        Raises:
            ValueError: If the TPDOMap instance is not in the TPDOMap list.
            IndexError: If the index is out of range.

        """
        drive, _ = self.__get_drive_and_network(servo)
        drive.remove_tpdo_map(tpdo_map=tpdo_map, tpdo_map_index=tpdo_map_index)

    def start_pdos(
        self,
        network_type: Optional[CommunicationType] = None,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
    ) -> None:
        """Start the PDO exchange process.

        Args:
            network_type: Network type (EtherCAT or CANopen) on which to start the PDO exchange.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.

        Raises:
            ValueError: If the refresh rate is too high.
            ValueError: If the MotionController is connected to more than one Network.
            ValueError: If network_type argument is invalid.
            IMError: If the MotionController is connected to more than one Network.
            ValueError: If there is a type mismatch retrieving the network object.
            IMError: If the PDOs are already active.
        """
        if network_type is None:
            if len(self.__mc.net) > 1:
                raise ValueError(
                    "There is more than one network created. The network_type argument must be"
                    " provided."
                )
            net = next(iter(self.__mc.net.values()))
        elif not isinstance(network_type, CommunicationType):
            raise ValueError(
                f"Wrong value for the network_type argument. Must be of type {CommunicationType}"
            )
        elif network_type == CommunicationType.Canopen:
            raise NotImplementedError
        else:
            ethercat_networks = [
                network
                for network in self.__mc.net.values()
                if isinstance(network, EthercatNetwork)
            ]
            canopen_networks = [
                network for network in self.__mc.net.values() if isinstance(network, CanopenNetwork)
            ]
            if len(ethercat_networks) > 1 or len(canopen_networks) > 1:
                raise IMError(
                    "When using PDOs only one instance per network type is allowed. "
                    f"Got {len(ethercat_networks)} instances of EthercatNetwork "
                    f"and {len(canopen_networks)} of CanopenNetwork."
                )
            net = (
                ethercat_networks[0]
                if network_type == CommunicationType.Ethercat
                else canopen_networks[0]
            )
        if not isinstance(net, EthercatNetwork):
            raise ValueError(f"Expected EthercatNetwork. Got {type(net)}")
        self.__evaluate_subscriptions(net=net)
        self.__net = net
        self.__net.subscribe_to_pdo_thread_status(callback=self.__pdo_thread_status_callback)
        self.__net.activate_pdos(refresh_rate=refresh_rate, watchdog_timeout=watchdog_timeout)

    def __pdo_thread_status_callback(self, status: bool) -> None:
        self.__pdo_thread_status = status

    def stop_pdos(self) -> None:
        """Stop the PDO exchange process.

        Raises:
            IMError: If the PDOs are not active yet.

        """
        if self.__net is None:
            raise IMError("PDOs are not active yet.")
        self.__net.deactivate_pdos()
        self.__net = None

    @property
    def is_active(self) -> bool:
        """Check if the PDO thread is active.

        Returns:
            True if the PDO thread is active. False otherwise.
        """
        return self.__pdo_thread_status

    def subscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the RPDO values will be sent.

        Args:
            callback: Callback function.
        """
        if self.__net is not None:
            self.__net.pdo_manager.subscribe_to_send_process_data(callback)
        else:
            self.__send_process_data_add_callback.append(callback)

    def subscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the TPDO values are received.

        Args:
            callback: Callback function.
        """
        if self.__net is not None:
            self.__net.pdo_manager.subscribe_to_receive_process_data(callback)
        else:
            self.__receive_process_data_add_callback.append(callback)

    def subscribe_to_exceptions(self, callback: Callable[[ILError], None]) -> None:
        """Subscribe be notified when there is an exception in the PDO process data thread.

        If a callback is subscribed, the PDO exchange process is paused when an exception is raised.
        It can be resumed using the `resume_pdos` method.

        Args:
            callback: Callback function.
        """
        if self.__net is not None:
            self.__net.pdo_manager.subscribe_to_exceptions(callback)
        else:
            self.__exception_add_callback.append(callback)

    def unsubscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the send process data notifications.

        Args:
            callback: Subscribed callback function.
        """
        if self.__net is not None:
            self.__net.pdo_manager.unsubscribe_to_send_process_data(callback)
        else:
            self.__send_process_data_remove_callback.append(callback)

    def unsubscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the receive process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if self.__net is not None:
            self.__net.pdo_manager.unsubscribe_to_receive_process_data(callback)
        else:
            self.__receive_process_data_remove_callback.append(callback)

    def create_poller(
        self,
        registers: list[dict[str, Union[int, str]]],
        servo: str = DEFAULT_SERVO,
        sampling_time: float = 0.125,
        buffer_size: int = 100,
        watchdog_timeout: Optional[float] = None,
        start: bool = True,
    ) -> PDOPoller:
        """Create a register Poller using PDOs.

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
        return PDOPoller.create_poller(
            mc=self.__mc,
            registers=registers,
            servo=servo,
            sampling_time=sampling_time,
            watchdog_timeout=watchdog_timeout,
            buffer_size=buffer_size,
            start=start,
        )

    def unsubscribe_to_exceptions(self, callback: Callable[[ILError], None]) -> None:
        """Unsubscribe from the exceptions in the process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if self.__net is not None:
            self.__net.pdo_manager.unsubscribe_to_exceptions(callback)
        else:
            self.__exception_remove_callback.append(callback)
