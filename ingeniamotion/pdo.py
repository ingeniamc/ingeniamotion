import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional, Union

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError
from ingenialink.pdo import PDOMap, RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialogger import get_logger

from ingeniamotion.enums import CommunicationType
from ingeniamotion.exceptions import IMError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

logger = get_logger(__name__)


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
        self.__servo = servo
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
        self.__mc.capture.pdo.set_pdo_maps_to_slave(
            rpdo_maps=self.__rpdo_map, tpdo_maps=self.__tpdo_map, servo=self.__servo
        )
        self.__tpdo_map.subscribe_to_process_data_event(self._new_data_available)
        for callback in self.__exception_callbacks:
            self.__mc.capture.pdo.subscribe_to_exceptions(callback, servo=self.__servo)
        self.__start_time = time.time()
        self.__mc.capture.pdo.start_pdos(
            refresh_rate=self.__refresh_time,
            watchdog_timeout=self.__watchdog_timeout,
            servo=self.__servo,
        )

    def stop(self) -> None:
        """Stop the poller."""
        self.__mc.capture.pdo.stop_pdos(servo=self.__servo)
        self.__tpdo_map.unsubscribe_to_process_data_event()
        for callback in self.__exception_callbacks:
            self.__mc.capture.pdo.unsubscribe_to_exceptions(callback, servo=self.__servo)
        self.__mc.capture.pdo.remove_rpdo_map(servo=self.__servo, rpdo_map=self.__rpdo_map)
        self.__mc.capture.pdo.remove_tpdo_map(servo=self.__servo, tpdo_map=self.__tpdo_map)

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
            tpdo_map_item = self.__mc.capture.pdo.create_pdo_item(
                register_uid=name, axis=axis, servo=self.__servo
            )
            self.__tpdo_map.add_item(tpdo_map_item)

    @property
    def available_samples(self) -> int:
        """Number of samples in the buffer."""
        return len(self.__buffer)


@dataclass
class PDONetwork:
    """Represents a PDO network."""

    alias: str
    network: EthercatNetwork
    refresh_rate: Optional[float]
    watchdog_timeout: Optional[float]

    __pdo_thread_status: bool = False

    def __pdo_thread_status_callback(self, status: bool) -> None:
        """Callback for PDO thread status changes.

        Args:
            status: The new status of the PDO thread.
        """
        self.__pdo_thread_status = status

    @property
    def is_active(self) -> bool:
        """Check if the PDO thread is active.

        Returns:
            True if the PDO thread is active. False otherwise.
        """
        return self.__pdo_thread_status

    def compare_configuration(
        self, refresh_rate: Optional[float], watchdog_timeout: Optional[float]
    ) -> bool:
        """Compares the current PDO thread configuration with another.

        Args:
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
                to the refresh rate.

        Returns:
            True if the configurations are equal, False otherwise.
        """
        return self.refresh_rate == refresh_rate and self.watchdog_timeout == watchdog_timeout

    @classmethod
    def create_and_subscribe(
        cls,
        alias: str,
        network: EthercatNetwork,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
    ) -> "PDONetwork":
        """Creates a new PDONetwork instance and subscribes to EtherCAT network PDO thread status.

        Args:
            alias: The network alias.
            network: The EthercatNetwork instance.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.

        Returns:
            A new PDONetwork instance.
        """
        net = cls(
            alias=alias,
            network=network,
            refresh_rate=refresh_rate,
            watchdog_timeout=watchdog_timeout,
        )
        net.network.subscribe_to_pdo_thread_status(callback=net.__pdo_thread_status_callback)
        return net

    def teardown(self) -> None:
        """Unsubscribes from network exceptions."""
        self.network.unsubscribe_from_pdo_thread_status(callback=self.__pdo_thread_status_callback)


class PDONetworksTracker:
    """Tracks the different networks that have been required to activate PDOs."""

    def __init__(self) -> None:
        self.__networks: dict[str, PDONetwork] = {}

    def is_network_tracked(self, alias: str) -> bool:
        """Checks if a network is being tracked.

        Args:
            alias: The network alias.

        Returns:
            True if the network is tracked, False otherwise.
        """
        return alias in self.__networks

    def add_network(
        self,
        alias: str,
        network: EthercatNetwork,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
    ) -> None:
        """Add a network to the tracker.

        Args:
            alias: The network alias.
            network: The EthercatNetwork instance.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.

        Raises:
            IMError: If the network is already tracked with a different configuration.
        """
        if not self.is_network_tracked(alias=alias):
            self.__networks[alias] = PDONetwork.create_and_subscribe(
                alias=alias,
                network=network,
                refresh_rate=refresh_rate,
                watchdog_timeout=watchdog_timeout,
            )
            network.activate_pdos(refresh_rate=refresh_rate, watchdog_timeout=watchdog_timeout)
            return
        if not self.__networks[alias].compare_configuration(
            refresh_rate=refresh_rate, watchdog_timeout=watchdog_timeout
        ):
            raise IMError("Inconsistent PDO thread configuration for already active network.")
        logger.warning("PDOs are already active for this network.")

    def remove_network(self, alias: str) -> None:
        """Remove a network from the tracker.

        Args:
            alias: The network alias.

        Raises:
            IMError: If the PDOs are not active for the network.
        """
        if not self.is_network_tracked(alias):
            raise IMError(f"PDOs are not active yet for network '{alias}'.")
        net = self.__networks[alias]
        # If the exception has happened when starting the PDOs, the PDOs are not active yet
        if not net.network.pdo_manager.is_active:
            logger.warning("PDOs are not active for this network.")
        else:
            net.network.deactivate_pdos()
        net.teardown()
        del self.__networks[alias]

    def get_il_network(self, alias: str) -> "EthercatNetwork":
        """Retrieves the Ethercat network for a specific alias.

        Args:
            alias: The network alias.

        Returns:
            The EthercatNetwork instance for the specified alias.

        Raises:
            IMError: If the PDOs are not active for the network.
        """
        if not self.is_network_tracked(alias):
            raise IMError(f"Cannot retrieve Ethercat network for '{alias}', it is not tracked.")
        return self.__networks[alias].network

    def is_active(self, alias: str) -> bool:
        """Checks if the PDO thread is active for a specific network.

        Args:
            alias: The network alias.

        Returns:
            bool: True if the PDO thread is active, False otherwise.
        """
        if self.is_network_tracked(alias):
            return self.__networks[alias].is_active
        return False


class PDONetworkManager:
    """Manage all the PDO functionalities.

    Args:
        mc: The MotionController.
    """

    def __init__(self, motion_controller: "MotionController") -> None:
        self.__mc = motion_controller

        self.__net_tracker = PDONetworksTracker()

        # Save the callbacks to add/remove, manage them when there is a reference to the network
        self.__send_process_data_add_callback: dict[str, list[Callable[[], None]]] = defaultdict(
            list
        )
        self.__receive_process_data_add_callback: dict[str, list[Callable[[], None]]] = defaultdict(
            list
        )
        self.__exception_add_callback: dict[str, list[Callable[[ILError], None]]] = defaultdict(
            list
        )
        self.__send_process_data_remove_callback: dict[str, list[Callable[[], None]]] = defaultdict(
            list
        )
        self.__receive_process_data_remove_callback: dict[str, list[Callable[[], None]]] = (
            defaultdict(list)
        )
        self.__exception_remove_callback: dict[str, list[Callable[[ILError], None]]] = defaultdict(
            list
        )

    def __evaluate_subscriptions(self, net: EthercatNetwork, alias: str) -> None:  # noqa: C901
        for servo, callbacks in self.__send_process_data_add_callback.items():
            if servo != alias:
                continue
            for callback in callbacks:
                net.pdo_manager.subscribe_to_send_process_data(callback)
        for servo, callbacks in self.__receive_process_data_add_callback.items():
            if servo != alias:
                continue
            for callback in callbacks:
                net.pdo_manager.subscribe_to_receive_process_data(callback)
        for servo, exception_callbacks in self.__exception_add_callback.items():
            if servo != alias:
                continue
            for exception_callback in exception_callbacks:
                net.pdo_manager.subscribe_to_exceptions(exception_callback)
        for servo, callbacks in self.__send_process_data_remove_callback.items():
            if servo != alias:
                continue
            for callback in callbacks:
                net.pdo_manager.unsubscribe_to_send_process_data(callback)
        for servo, callbacks in self.__receive_process_data_remove_callback.items():
            if servo != alias:
                continue
            for callback in callbacks:
                net.pdo_manager.unsubscribe_to_receive_process_data(callback)
        for servo, exception_callbacks in self.__exception_remove_callback.items():
            if servo != alias:
                continue
            for exception_callback in exception_callbacks:
                net.pdo_manager.unsubscribe_to_exceptions(exception_callback)

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

        _rpdo_maps = [rpdo_maps] if isinstance(rpdo_maps, RPDOMap) else rpdo_maps
        _tpdo_maps = [tpdo_maps] if isinstance(tpdo_maps, TPDOMap) else tpdo_maps
        if not all(isinstance(rpdo_map, RPDOMap) for rpdo_map in _rpdo_maps):
            raise ValueError("Not all elements of the RPDO map list are instances of a RPDO map")
        if not all(isinstance(tpdo_map, TPDOMap) for tpdo_map in _tpdo_maps):
            raise ValueError("Not all elements of the TPDO map list are instances of a TPDO map")
        drive.set_pdo_map_to_slave(rpdo_maps=_rpdo_maps, tpdo_maps=_tpdo_maps)

    def clear_pdo_mapping(self, servo: str = DEFAULT_SERVO) -> None:
        """Clear the PDO mapping within the servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.
        """
        drive = self.__mc._get_drive(servo=servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        drive.reset_pdo_mapping()

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
            ValueError: If there is a type mismatch retrieving the drive object.
        """
        drive = self.__mc._get_drive(servo=servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
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
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
            tpdo_map: The TPDOMap instance to be removed.
            tpdo_map_index: The index of the TPDOMap list to be removed.

        Raises:
            ValueError: If there is a type mismatch retrieving the drive object.
        """
        drive = self.__mc._get_drive(servo=servo)
        if not isinstance(drive, EthercatServo):
            raise ValueError(f"Expected an EthercatServo. Got {type(drive)}")
        drive.remove_tpdo_map(tpdo_map=tpdo_map, tpdo_map_index=tpdo_map_index)

    def start_pdos(
        self,
        network_type: Optional[CommunicationType] = None,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
        servo: str = DEFAULT_SERVO,
    ) -> None:
        """Start the PDO exchange process.

        Warning:
            Note that the PDO exchange will start for all servos connected to the same network.

        Args:
            network_type: Network type (EtherCAT or CANopen) on which to start the PDO exchange.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                If `network_type` is provided, `servo` must be connected to that network.

        Raises:
            ValueError: If the MotionController is not connected to any Network.
            ValueError: If there is a type mismatch retrieving the network object.
        """
        if network_type in [None, CommunicationType.Ethercat]:
            if len(self.__mc.net) == 0:
                raise ValueError(
                    "No network created. Please create a network before starting PDOs."
                )
            # Start PDOs for the network the specified servo
            net = self.__mc._get_network(servo=servo)
        else:
            raise NotImplementedError

        if not isinstance(net, EthercatNetwork):
            raise ValueError(f"Expected EthercatNetwork. Got {type(net)}")

        self.__evaluate_subscriptions(net=net, alias=servo)
        self.__net_tracker.add_network(
            alias=self.__mc.servo_net[servo],
            network=net,
            refresh_rate=refresh_rate,
            watchdog_timeout=watchdog_timeout,
        )

    def stop_pdos(self, servo: str = DEFAULT_SERVO) -> None:
        """Stop the PDO exchange process.

        Warning:
            Note that the PDO exchange will stop for all servos connected to the same network.

        Args:
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                PDOs will be stopped in the network to which the servo is connected.

        Raises:
            IMError: If the PDOs are not active yet.
        """
        self.__net_tracker.remove_network(alias=self.__mc.servo_net[servo])

    def is_active(
        self, servo: Optional[str] = DEFAULT_SERVO, net_alias: Optional[str] = None
    ) -> bool:
        """Check if the PDO thread is active for the network to which the servo is connected.

        Alternatively, it can be checked for a specific network.
        If the network alias is provided, the servo will be ignored.

        Args:
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
            net_alias: network alias to reference it. ``None`` by default.

        Returns:
            True if the PDO thread is active. False otherwise.

        Raises:
            ValueError: If neither servo nor net_alias is provided.
        """
        if net_alias is not None:
            return self.__net_tracker.is_active(alias=net_alias)
        elif servo is not None:
            return self.__net_tracker.is_active(alias=self.__mc.servo_net[servo])
        raise ValueError("Either servo or net_alias must be provided.")

    def subscribe_to_send_process_data(
        self, callback: Callable[[], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Subscribe be notified when the RPDO values will be sent.

        Args:
            callback: Callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The subscription will be added to the network to which the servo is connected.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.subscribe_to_send_process_data(callback)
        else:
            self.__send_process_data_add_callback[servo].append(callback)

    def subscribe_to_receive_process_data(
        self, callback: Callable[[], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Subscribe be notified when the TPDO values are received.

        Args:
            callback: Callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The subscription will be added to the network to which the servo is connected.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.subscribe_to_receive_process_data(callback)
        else:
            self.__receive_process_data_add_callback[servo].append(callback)

    def subscribe_to_exceptions(
        self, callback: Callable[[ILError], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Subscribe be notified when there is an exception in the PDO process data thread.

        If a callback is subscribed, the PDO exchange process is paused when an exception is raised.
        It can be resumed using the `resume_pdos` method.

        Args:
            callback: Callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The subscription will be added to the network to which the servo is connected.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.subscribe_to_exceptions(callback)
        else:
            self.__exception_add_callback[servo].append(callback)

    def unsubscribe_to_send_process_data(
        self, callback: Callable[[], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Unsubscribe from the send process data notifications.

        Args:
            callback: Subscribed callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The unsubscription will be removed from the network to which the servo is connected.

        Args:
            callback: Subscribed callback function.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.unsubscribe_to_send_process_data(callback)
        else:
            self.__send_process_data_remove_callback[servo].append(callback)

    def unsubscribe_to_receive_process_data(
        self, callback: Callable[[], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Unsubscribe from the receive process data notifications.

        Args:
            callback: Subscribed callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The unsubscription will be removed from the network to which the servo is connected.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.unsubscribe_to_receive_process_data(callback)
        else:
            self.__receive_process_data_remove_callback[servo].append(callback)

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
        poller = PDOPoller(
            mc=self.__mc,
            servo=servo,
            refresh_time=sampling_time,
            watchdog_timeout=watchdog_timeout,
            buffer_size=buffer_size,
        )
        poller.add_channels(registers)
        if start:
            poller.start()
        return poller

    def unsubscribe_to_exceptions(
        self, callback: Callable[[ILError], None], servo: str = DEFAULT_SERVO
    ) -> None:
        """Unsubscribe from the exceptions in the process data notifications.

        Args:
            callback: Subscribed callback function.
            servo: servo alias to reference it. ``DEFAULT_SERVO`` by default.
                The unsubscription will be removed from the network to which the servo is connected.
        """
        net_alias = self.__mc.servo_net[servo]
        if self.__net_tracker.is_network_tracked(net_alias):
            net = self.__net_tracker.get_il_network(alias=net_alias)
            net.pdo_manager.unsubscribe_to_exceptions(callback)
        else:
            self.__exception_remove_callback[servo].append(callback)
