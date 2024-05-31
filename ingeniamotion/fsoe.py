from typing import TYPE_CHECKING, Dict

import ingenialogger
from fsoe_master.fsoe_master import Dictionary, DictionaryItem, MasterHandler
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.enums.register import REG_ACCESS, REG_DTYPE

from ingeniamotion.metaclass import DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class FSoEMasterHandler:
    """FSoE Master Handler.

    Args:
        slave_address: The servo's FSoE address.
        connection_id: The FSoE connection ID.
        watchdog_timeout: The FSoE master watchdog timeout in seconds.

    """

    STO_COMMAND_KEY = 0x040
    STO_COMMAND_UID = "STO_COMMAND"

    def __init__(self, slave_address: int, connection_id: int, watchdog_timeout: float):
        self.__master_handler = MasterHandler(
            dictionary=self._saco_phase_1_dictionary(),
            slave_address=slave_address,
            connection_id=connection_id,
            watchdog_timeout_s=watchdog_timeout,
            application_parameters=[],
        )
        self._configure_master()
        self.__safety_master_pdu = RPDOMap()
        self.__safety_slave_pdu = TPDOMap()
        self._configure_pdo_maps()

    def start(self) -> None:
        """Start the FSoE Master handler."""
        self.__master_handler.start()
        # Load initial request to the Safety Master PDU PDOMap
        self.get_request()

    def stop(self) -> None:
        """Stop the master handler"""
        self.__master_handler.stop()

    def delete(self) -> None:
        """Delete the master handler"""
        self.__master_handler.delete()

    def _configure_pdo_maps(self) -> None:
        """Configure the PDOMaps used for the Safety PDUs."""
        PDUMapper.configure_rpdo_map(self.safety_master_pdu_map)
        PDUMapper.configure_tpdo_map(self.safety_slave_pdu_map)

    def _configure_master(self) -> None:
        """Configure the FSoE master handler."""
        self._map_outputs()
        self._map_inputs()

    def _map_outputs(self) -> None:
        """Configure the FSoE master handler's SafeOutputs."""
        # Phase 1 mapping
        self.__master_handler.master.dictionary_map.add_by_key(self.STO_COMMAND_KEY, bits=1)
        self.__master_handler.master.dictionary_map.add_padding(bits=7)

    def _map_inputs(self) -> None:
        """Configure the FSoE master handler's SafeInputs."""
        # Phase 1 mapping
        self.__master_handler.slave.dictionary_map.add_padding(bits=8)

    def get_request(self) -> None:
        """Set the FSoE master handler request to the Safety Master PDU PDOMap"""
        self.safety_master_pdu_map.set_item_bytes(self.__master_handler.get_request())

    def set_reply(self) -> None:
        """Get the FSoE slave response from the Safety Slave PDU PDOMap and set it
        to the FSoE master handler."""
        self.__master_handler.set_reply(self.safety_slave_pdu_map.get_item_bytes())

    def sto_deactivate(self) -> None:
        """Set the STO command to deactivate the STO"""
        self.__master_handler.dictionary.set(self.STO_COMMAND_UID, True)

    def sto_activate(self) -> None:
        """Set the STO command to activate the STO"""
        self.__master_handler.dictionary.set(self.STO_COMMAND_UID, False)

    @staticmethod
    def _saco_phase_1_dictionary() -> Dictionary:
        """Get the SaCo phase 1 dictionary instance"""
        sto_command_dict_item = DictionaryItem(
            key=0x040,
            name="STO_COMMAND",
            data_type=DictionaryItem.DataTypes.BOOL,
            typ=DictionaryItem.Types.SAFE_OUTPUT,
        )
        return Dictionary([sto_command_dict_item])

    @property
    def safety_master_pdu_map(self) -> RPDOMap:
        """The PDOMap used for the Safety Master PDU."""
        return self.__safety_master_pdu

    @property
    def safety_slave_pdu_map(self) -> TPDOMap:
        """The PDOMap used for the Safety Slave PDU."""
        return self.__safety_slave_pdu


class PDUMapper:
    """Helper class to configure the Safety PDU PDOMaps."""

    FSOE_RPDO_MAP_1_INDEX = 0x1700
    FSOE_TPDO_MAP_1_INDEX = 0x1B00

    # Phase 1 mapping
    FSOE_COMMAND_SIZE_BITS = 8
    STO_COMMAND_SIZE_BITS = 1
    STO_COMMAND_PADDING_SIZE_BITS = 7
    CRC_O_SIZE_BITS = 16
    CONN_ID_SIZE_BITS = 16

    @classmethod
    def configure_rpdo_map(cls, rpdo_map: RPDOMap) -> None:
        """Configure the RPDOMap used for the Safety Master PDU.

        Args:
            rpdo_map: The RPDOMap instance.

        """
        rpdo_map.map_register_index = cls.FSOE_RPDO_MAP_1_INDEX
        fsoe_command_item = RPDOMapItem(size_bits=cls.FSOE_COMMAND_SIZE_BITS)
        rpdo_map.add_item(fsoe_command_item)
        sto_command_item = RPDOMapItem(size_bits=cls.STO_COMMAND_SIZE_BITS)
        rpdo_map.add_item(sto_command_item)
        padding_item = RPDOMapItem(size_bits=cls.STO_COMMAND_PADDING_SIZE_BITS)
        rpdo_map.add_item(padding_item)
        crc_0_item = RPDOMapItem(size_bits=cls.CRC_O_SIZE_BITS)
        rpdo_map.add_item(crc_0_item)
        conn_id_item = RPDOMapItem(size_bits=cls.CONN_ID_SIZE_BITS)
        rpdo_map.add_item(conn_id_item)

    @classmethod
    def configure_tpdo_map(cls, tpdo_map: TPDOMap) -> None:
        """Configure the TPDOMap used for the Safety Slave PDU.

        Args:
            tpdo_map: The TPDOMap instance.

        """
        tpdo_map.map_register_index = cls.FSOE_TPDO_MAP_1_INDEX
        fsoe_command_item = TPDOMapItem(size_bits=cls.FSOE_COMMAND_SIZE_BITS)
        tpdo_map.add_item(fsoe_command_item)
        sto_command_item = TPDOMapItem(size_bits=cls.STO_COMMAND_SIZE_BITS)
        tpdo_map.add_item(sto_command_item)
        padding_item = TPDOMapItem(size_bits=cls.STO_COMMAND_PADDING_SIZE_BITS)
        tpdo_map.add_item(padding_item)
        crc_0_item = TPDOMapItem(size_bits=cls.CRC_O_SIZE_BITS)
        tpdo_map.add_item(crc_0_item)
        conn_id_item = TPDOMapItem(size_bits=cls.CONN_ID_SIZE_BITS)
        tpdo_map.add_item(conn_id_item)


class FSoEMaster:
    """FSoE Master.

    Args:
        motion_controller: The MotionController instance.

    """

    DEFAULT_WATCHDOG_TIMEOUT_S = 1

    SAFETY_ADDRESS_REGISTER = EthercatRegister(
        idx=0x4193, subidx=0x00, dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )

    def __init__(self, motion_controller: "MotionController") -> None:
        self.logger = ingenialogger.get_logger(__name__)
        self.__mc = motion_controller
        self.__handlers: Dict[str, FSoEMasterHandler] = {}
        self.__next_connection_id = 1

    def create_fsoe_master_handler(
        self,
        servo: str = DEFAULT_SERVO,
        fsoe_master_watchdog_timeout: float = DEFAULT_WATCHDOG_TIMEOUT_S,
    ) -> None:
        """Create an FSoE Master handler linked to a Safe servo drive.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            fsoe_master_watchdog_timeout: The FSoE master watchdog timeout in seconds.

        """
        slave_address = self.get_safety_address(servo)
        master_handler = FSoEMasterHandler(
            slave_address, self.__next_connection_id, fsoe_master_watchdog_timeout
        )
        self.__handlers[servo] = master_handler
        self.__next_connection_id += 1

    def start_master(self, start_pdos: bool = False) -> None:
        """Start all the FSoE Master handlers.

        Args:
            start_pdos: if ``True``, start the PDO exchange, if ``False``
                the PDO exchange should be started after. ``False`` by default.

        """
        for servo, master_handler in self.__handlers.items():
            master_handler.start()
        self._set_pdo_maps_to_slaves()
        self._subscribe_to_pdo_thread_events()
        if start_pdos:
            self.__mc.capture.pdo.start_pdos()

    def stop_master(self, stop_pdos: bool = False) -> None:
        """Stop all the FSoE Master handlers.

        Args:
            stop_pdos: if ``True``, stop the PDO exchange. ``False`` by default.

        """
        for master_handler in self.__handlers.values():
            master_handler.stop()
        self._unsubscribe_from_pdo_thread_events()
        self._remove_pdo_maps_from_slaves()
        if stop_pdos:
            self.__mc.capture.pdo.stop_pdos()

    def sto_deactivate(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the Safety Torque Off.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self.__handlers[servo]
        master_handler.sto_deactivate()

    def sto_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the Safety Torque Off.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self.__handlers[servo]
        master_handler.sto_activate()

    def get_safety_address(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        drive = self.__mc.servos[servo]
        value = drive.read(self.SAFETY_ADDRESS_REGISTER)
        if not isinstance(value, int):
            raise ValueError(f"Wrong safety address value type. Expected int, got {type(value)}")
        return value

    def set_safety_address(self, address: int, servo: str = DEFAULT_SERVO) -> None:
        """Set the drive's FSoE slave address.

        Args:
            address: The address to be set.
            servo: servo alias to reference it. ``default`` by default.

        """
        drive = self.__mc.servos[servo]
        drive.write(self.SAFETY_ADDRESS_REGISTER, data=address)

    def _delete_master_handler(self, servo: str = DEFAULT_SERVO) -> None:
        """Delete the master handler instance

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        if servo not in self.__handlers:
            return
        self.__handlers[servo].delete()
        del self.__handlers[servo]

    def _subscribe_to_pdo_thread_events(self) -> None:
        """Subscribe to the PDO thread events.

        This allows to send the Safety Master PDU and to retrieve the Safety Slave PDU.

        """
        self.__mc.capture.pdo.subscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.subscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.subscribe_to_exceptions(self._pdo_thread_exception_handler)

    def _unsubscribe_from_pdo_thread_events(self) -> None:
        """Unsubscribe from the PDO thread events."""
        self.__mc.capture.pdo.unsubscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.unsubscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.unsubscribe_to_exceptions(self._pdo_thread_exception_handler)

    def _set_pdo_maps_to_slaves(self) -> None:
        """Set the PDOMaps to be used by the Safety PDUs to the slaves."""
        for servo, master_handler in self.__handlers.items():
            rpdo_map = master_handler.safety_master_pdu_map
            tpdo_map = master_handler.safety_slave_pdu_map
            self.__mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo)

    def _remove_pdo_maps_from_slaves(self) -> None:
        """Remove the PDOMaps used by the Safety PDUs from the slaves."""
        for servo, master_handler in self.__handlers.items():
            self.__mc.capture.pdo.remove_rpdo_map(servo, master_handler.safety_master_pdu_map)
            self.__mc.capture.pdo.remove_tpdo_map(servo, master_handler.safety_slave_pdu_map)

    def _get_request(self) -> None:
        """Callback method to send the FSoE Master handlers requests to the
        corresponding FSoE slave."""
        for master_handler in self.__handlers.values():
            master_handler.get_request()

    def _set_reply(self) -> None:
        """Callback method to provide the FSoE Slaves responses to their
        corresponding FSoE Master handler."""
        for master_handler in self.__handlers.values():
            master_handler.set_reply()

    def _pdo_thread_exception_handler(self, exc: Exception) -> None:
        """Callback method for the PDO thread exceptions."""
        self.logger.error(
            "The FSoE Master lost connection to the FSoE slaves. "
            f"An exception occurred during the PDO exchange: {exc}"
        )
