from typing import TYPE_CHECKING, Dict

from fsoe_master.fsoe_master import MasterHandler, Dictionary, DictionaryItem, Watchdog
from ingeniamotion.metaclass import DEFAULT_SERVO

from ingenialink.pdo import RPDOMapItem, TPDOMapItem, RPDOMap, TPDOMap

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class FSoEMasterHandler:
    KEY0x040STO_COMMAND = 0x040

    def __init__(self, slave_address: int, connection_id: int, watchdog_timeout: float):
        default_dict = Dictionary(
            [
                DictionaryItem(
                    key=self.KEY0x040STO_COMMAND,
                    name="STO_COMMAND",
                    data_type=DictionaryItem.DataTypes.BOOL,
                    typ=DictionaryItem.Types.SAFE_OUTPUT,
                )
            ]
        )
        self.__master_handler = MasterHandler(
            dictionary=default_dict,
            slave_address=slave_address,
            connection_id=connection_id,
            watchdog_timeout_s=watchdog_timeout,
            application_parameters=[],
        )
        self._configure_master()
        self.__safety_master_pdu = RPDOMap()
        self.__safety_slave_pdu = TPDOMap()

    def start(self) -> None:
        self.__master_handler.start()

    def configure_pdo_maps(self) -> None:
        PDUMapper.configure_rpdo_map(self.safety_master_pdu_map)
        PDUMapper.configure_tpdo_map(self.safety_slave_pdu_map)
        self.get_request()

    def _configure_master(self) -> None:
        self._map_outputs()
        self._map_inputs()

    def _map_outputs(self) -> None:
        # Phase 1 mapping
        self.__master_handler.master.dictionary_map.add_by_key(self.KEY0x040STO_COMMAND, bits=1)
        self.__master_handler.master.dictionary_map.add_padding(bits=7)

    def _map_inputs(self) -> None:
        # Phase 1 mapping
        self.__master_handler.slave.dictionary_map.add_padding(bits=8)

    def get_request(self) -> None:
        self.safety_master_pdu_map.set_item_bytes(self.__master_handler.get_request())

    def set_reply(self) -> None:
        self.__master_handler.set_reply(self.safety_slave_pdu_map.get_item_bytes())

    @property
    def safety_master_pdu_map(self) -> RPDOMap:
        return self.__safety_master_pdu

    @property
    def safety_slave_pdu_map(self) -> TPDOMap:
        return self.__safety_slave_pdu

    @property
    def watchdog(self) -> Watchdog:
        return self.__master_handler.watchdog


class PDUMapper:
    FSOE_RPDO_MAP_1 = 0x1700
    FSOE_TPDO_MAP_1 = 0x1B00

    FSOE_COMMAND_SIZE_BITS = 8
    STO_COMMAND_SIZE_BITS = 1
    STO_COMMAND_PADDING_SIZE_BITS = 7
    CRC_O_SIZE_BITS = 16
    CONN_ID_SIZE_BITS = 16

    @classmethod
    def configure_rpdo_map(cls, rpdo_map: RPDOMap) -> None:
        # Phase 1 mapping
        rpdo_map.map_register_index = cls.FSOE_RPDO_MAP_1
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
        # Phase 1 mapping
        tpdo_map.map_register_index = cls.FSOE_TPDO_MAP_1
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
    DEFAULT_WATCHDOG_TIMEOUT_S = 1
    DEFAULT_FSOE_SLAVE_ADDRESS = 0

    def __init__(self, motion_controller: "MotionController") -> None:
        self.__mc = motion_controller
        self.__handlers: Dict[str, FSoEMasterHandler] = {}
        self.__latest_connection_id = 1

    def create_fsoe_master_handler(self, servo: str = DEFAULT_SERVO) -> None:
        # TODO: use function to read the FSoE slave address (INGM-446)
        slave_address = self.DEFAULT_FSOE_SLAVE_ADDRESS
        master_handler = FSoEMasterHandler(
            slave_address, self.__latest_connection_id, self.DEFAULT_WATCHDOG_TIMEOUT_S
        )
        self.__handlers[servo] = master_handler
        self.__latest_connection_id += 1

    def start_master(self) -> None:
        for servo, master_handler in self.__handlers.items():
            master_handler.start()
            master_handler.configure_pdo_maps()
            rpdo_map = master_handler.safety_master_pdu_map
            tpdo_map = master_handler.safety_slave_pdu_map
            self.__mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo)
        self.__mc.capture.pdo.subscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.subscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.subscribe_to_exceptions(self._pdo_thread_exception_handler)
        self.__mc.capture.pdo.start_pdos()

    def stop_master(self) -> None:
        self.__mc.capture.pdo.stop_pdos()
        for servo, master_handler in self.__handlers.items():
            if master_handler.watchdog.is_alive():
                master_handler.watchdog.stop()
            self.__mc.capture.pdo.remove_rpdo_map(servo, master_handler.safety_master_pdu_map)
            self.__mc.capture.pdo.remove_tpdo_map(servo, master_handler.safety_slave_pdu_map)
        self.__mc.capture.pdo.unsubscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.unsubscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.unsubscribe_to_exceptions(self._pdo_thread_exception_handler)

    def _get_request(self) -> None:
        for master_handler in self.__handlers.values():
            master_handler.get_request()

    def _set_reply(self) -> None:
        for master_handler in self.__handlers.values():
            master_handler.set_reply()

    def _pdo_thread_exception_handler(self, exc: Exception) -> None:
        print(
            f"An exception occurred during the PDO exchange. The FSoE master will be stopped. Exception: {exc}"
        )
        self.stop_master()
