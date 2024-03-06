import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Union, Tuple, Type, Callable

from ingenialink.pdo import RPDOMap, TPDOMap, RPDOMapItem, TPDOMapItem
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.canopen.network import CanopenNetwork

from ingeniamotion.exceptions import (
    IMException,
)
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.enums import COMMUNICATION_TYPE

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class PDOPoller:
    """Poll register values using PDOs"""

    def __init__(
        self,
        mc: "MotionController",
        servo: str,
        refresh_time: float,
        buffer_size: int,
    ) -> None:
        """Constructor.

        Args:
            mc: MotionController instance
            servo: drive alias.
            refresh_time: PDO values refresh time.
            buffer_size: Maximum number of register readings to store.

        """
        super().__init__()
        self.__mc = mc
        self.__servo = servo
        self.__refresh_time = refresh_time
        self.__buffer_size = buffer_size
        self.__num_channels: int = 0
        self.__buffer: List[List[Union[int, float]]] = [[]]
        self.__timestamps: List[float] = []
        self.__start_time: Optional[float] = None
        self.__tpdo_map: TPDOMap = self.__mc.capture.pdo.create_empty_tpdo_map()
        self.__rpdo_map: RPDOMap = self.__mc.capture.pdo.create_empty_rpdo_map()
        self.__fill_rpdo_map()

    def start(self) -> None:
        """Start the poller"""
        self._clear_buffers()
        self.__mc.capture.pdo.clear_pdo_mapping(servo=self.__servo)
        self.__mc.capture.pdo.set_pdo_maps_to_slave(
            self.__rpdo_map, self.__tpdo_map, servo=self.__servo
        )
        self.__mc.capture.pdo.subscribe_to_receive_process_data(self._new_data_available)
        self.__start_time = time.time()
        self.__mc.capture.pdo.start_pdos(refresh_rate=self.__refresh_time)

    def stop(self) -> None:
        """Stop the poller"""
        self.__mc.capture.pdo.stop_pdos()
        self.__mc.capture.pdo.unsubscribe_to_receive_process_data(self._new_data_available)

    @property
    def data(self) -> Tuple[List[float], List[List[Union[int, float]]]]:
        """
        Get the poller data. After the data is retrieved, the data buffers are cleared.

        Returns:
            A list with the readings timestamps and values.

        """
        data = self.__buffer
        time_stamps = self.__timestamps
        self._clear_buffers()
        return time_stamps, data

    def add_channels(self, registers: List[Dict[str, Union[int, str]]]) -> None:
        """
        Configure the PDOs with the registers to be read.

        Args:
            registers : list of registers to add to the Poller.

        """
        self.__num_channels = len(registers)
        self.__fill_tpdo_map(registers)

    def _new_data_available(self) -> None:
        """Add readings to the buffers.

        Raises:
            ValueError: If the poller has not been started yet.

        """
        if len(self.__timestamps) == self.__buffer_size:
            self.__timestamps.pop(0)
        if self.__start_time is None:
            raise ValueError("The poller has not been started yet.")
        time_stamp = round(time.time() - self.__start_time, 6)
        self.__timestamps.append(time_stamp)
        for tpdo_index, tpdo_map_item in enumerate(self.__tpdo_map.items):
            if len(self.__buffer[tpdo_index]) == self.__buffer_size:
                self.__buffer[tpdo_index].pop(0)
            self.__buffer[tpdo_index].append(tpdo_map_item.value)

    def _clear_buffers(self) -> None:
        """Clear the data buffers."""
        self.__buffer = [[] for _ in range(self.__num_channels)]
        self.__timestamps = []

    def __fill_rpdo_map(self) -> None:
        """Fill the RPDO Map with padding"""
        padding_rpdo_item = RPDOMapItem(size_bits=8)
        padding_rpdo_item.value = 0
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
            self._net.stop_pdos()
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
        network_type: Optional[COMMUNICATION_TYPE] = None,
        refresh_rate: Optional[float] = None,
    ) -> None:
        """
        Start the PDO exchange process.

        Args:
            network_type: Network type (EtherCAT or CANopen) on which to start the PDO exchange.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.

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
                    "There is more than one network created. The network_type argument must be provided."
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
        self._pdo_thread = None

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

    def create_poller(
        self,
        registers: List[Dict[str, Union[int, str]]],
        servo: str = DEFAULT_SERVO,
        sampling_time: float = 0.125,
        buffer_size: int = 100,
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
            buffer_size: number maximum of sample for each data read.
                ``100`` by default.
            start: if ``True``, function starts poller, if ``False``
                poller should be started after. ``True`` by default.

        Returns:
            The poller instance.

        """
        poller = PDOPoller(self.mc, servo, sampling_time, buffer_size)
        poller.add_channels(registers)
        if start:
            poller.start()
        return poller

    def _notify_send_process_data(self) -> None:
        """Notify subscribers that the RPDO values will be sent."""
        for callback in self._pdo_send_observers:
            callback()

    def _notify_receive_process_data(self) -> None:
        """Notify subscribers that the TPDO values were received."""
        for callback in self._pdo_receive_observers:
            callback()