import threading
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Optional

import ingenialogger

try:
    from fsoe_master.fsoe_master import (
        ApplicationParameter,
        Dictionary,
        DictionaryItem,
        DictionaryItemInput,
        DictionaryItemInputOutput,
        MasterHandler,
        StateData,
    )

    if TYPE_CHECKING:
        from fsoe_master.fsoe_master import State

except ImportError:
    FSOE_MASTER_INSTALLED = False
else:
    FSOE_MASTER_INSTALLED = True

from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.utils._utils import dtype_value

from ingeniamotion.enums import FSoEState
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.metaclass import DEFAULT_SERVO

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


@dataclass
class FSoEError:
    """FSoE Error descriptor."""

    servo: str
    transition_name: str
    description: str


class FSoEMasterHandler:
    """FSoE Master Handler.

    Args:
        slave_address: The servo's FSoE address.
        connection_id: The FSoE connection ID.
        watchdog_timeout: The FSoE master watchdog timeout in seconds.

    """

    STO_COMMAND_KEY = 0x040
    STO_COMMAND_UID = "STO_COMMAND"
    SS1_COMMAND_KEY = 0x050
    SS1_COMMAND_UID = "SS1_COMMAND"
    SAFE_INPUTS_KEY = 0x070
    SAFE_INPUTS_UID = "SAFE_INPUTS"
    PROCESS_DATA_COMMAND = 0x36

    def __init__(
        self,
        slave_address: int,
        connection_id: int,
        watchdog_timeout: float,
        application_parameters: list["ApplicationParameter"],
        report_error_callback: Callable[[str, str], None],
    ):
        if not FSOE_MASTER_INSTALLED:
            return
        self.__master_handler = MasterHandler(
            dictionary=self._saco_phase_1_dictionary(),
            slave_address=slave_address,
            connection_id=connection_id,
            watchdog_timeout_s=watchdog_timeout,
            application_parameters=application_parameters,
            report_error_callback=report_error_callback,
            state_change_callback=self.__state_change_callback,
        )
        self._configure_master()
        self.__safety_master_pdu = RPDOMap()
        self.__safety_slave_pdu = TPDOMap()
        self._configure_pdo_maps()
        self.__running = False
        self.__state_is_data = threading.Event()

        # The saco slave might take a while to answer with a valid command
        # During it's initialization it will respond with 0's, that are ignored
        # To avoid triggering additional errors
        self.__in_initial_reset = False

    def _start(self) -> None:
        """Start the FSoE Master handler."""
        self.__in_initial_reset = True
        self.__master_handler.start()
        self.__running = True

    def stop(self) -> None:
        """Stop the master handler."""
        self.__master_handler.stop()
        self.__in_initial_reset = False
        self.__running = False

    def delete(self) -> None:
        """Delete the master handler."""
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
        self.__master_handler.master.dictionary_map.add_by_key(self.SS1_COMMAND_KEY, bits=1)
        self.__master_handler.master.dictionary_map.add_padding(bits=7)
        self.__master_handler.master.dictionary_map.add_padding(bits=7)

    def _map_inputs(self) -> None:
        """Configure the FSoE master handler's SafeInputs."""
        # Phase 1 mapping
        self.__master_handler.slave.dictionary_map.add_by_key(self.STO_COMMAND_KEY, bits=1)
        self.__master_handler.slave.dictionary_map.add_by_key(self.SS1_COMMAND_KEY, bits=1)
        self.__master_handler.slave.dictionary_map.add_padding(bits=7)
        self.__master_handler.slave.dictionary_map.add_by_key(self.SAFE_INPUTS_KEY, bits=1)
        self.__master_handler.slave.dictionary_map.add_padding(bits=6)

    def get_request(self) -> None:
        """Set the FSoE master handler request to the Safety Master PDU PDOMap."""
        if not self.__running:
            self._start()
        self.safety_master_pdu_map.set_item_bytes(self.__master_handler.get_request())

    def set_reply(self) -> None:
        """Get the FSoE slave response.

        It is extracted from the Safety Slave PDU PDOMap and set to the FSoE master handler.
        """
        reply = self.safety_slave_pdu_map.get_item_bytes()
        if self.__in_initial_reset:
            if reply[0] == 0:
                # Byte 0 of FSoE frame should always be the command
                # 0 is not a valid command
                return
            else:
                self.__in_initial_reset = False

        self.__master_handler.set_reply(reply)

    def sto_deactivate(self) -> None:
        """Set the STO command to deactivate the STO."""
        self.__master_handler.set_fail_safe(False)
        self.__master_handler.dictionary.set(self.STO_COMMAND_UID, True)

    def sto_activate(self) -> None:
        """Set the STO command to activate the STO."""
        self.__master_handler.dictionary.set(self.STO_COMMAND_UID, False)

    def ss1_deactivate(self) -> None:
        """Set the SS1 command to deactivate the SS1."""
        self.__master_handler.set_fail_safe(False)
        self.__master_handler.dictionary.set(self.SS1_COMMAND_UID, True)

    def ss1_activate(self) -> None:
        """Set the SS1 command to activate the SS1."""
        self.__master_handler.dictionary.set(self.SS1_COMMAND_UID, False)

    def safe_inputs_value(self) -> bool:
        """Get the safe inputs register value."""
        safe_inputs_value = self.__master_handler.dictionary.get(self.SAFE_INPUTS_UID)
        if not isinstance(safe_inputs_value, bool):
            raise ValueError(f"Wrong value type. Expected type bool, got {type(safe_inputs_value)}")
        return safe_inputs_value

    def is_sto_active(self) -> bool:
        """Check the STO state.

        Returns:
            True if the STO is active. False otherwise.

        """
        sto_command = self.__master_handler.dictionary.get(self.STO_COMMAND_UID)
        if not isinstance(sto_command, bool):
            raise ValueError(f"Wrong value type. Expected type bool, got {type(sto_command)}")
        return sto_command

    def __state_change_callback(self, state: "State") -> None:
        if state == StateData:
            self.__state_is_data.set()
        else:
            self.__state_is_data.clear()

    def wait_for_data_state(self, timeout: Optional[float] = None) -> None:
        """Wait the FSoE master handler to reach the Data state.

        Args:
            timeout : how many seconds to wait for the FSoE master to reach the
                Data state, if ``None`` it will wait forever.
                ``None`` by default.

        Raises:
            IMTimeoutError: If the Data state is not reached within the timeout.

        """
        if self.__state_is_data.wait(timeout=timeout) is False:
            raise IMTimeoutError("The FSoE Master did not reach the Data state")

    def _saco_phase_1_dictionary(self) -> "Dictionary":
        """Get the SaCo phase 1 dictionary instance."""
        sto_command_dict_item = DictionaryItemInputOutput(
            key=self.STO_COMMAND_KEY,
            name=self.STO_COMMAND_UID,
            data_type=DictionaryItem.DataTypes.BOOL,
            fail_safe_input_value=True,
        )
        ss1_command_dict_item = DictionaryItemInputOutput(
            key=self.SS1_COMMAND_KEY,
            name=self.SS1_COMMAND_UID,
            data_type=DictionaryItem.DataTypes.BOOL,
            fail_safe_input_value=True,
        )
        safe_input_dict_item = DictionaryItemInput(
            key=self.SAFE_INPUTS_KEY,
            name=self.SAFE_INPUTS_UID,
            data_type=DictionaryItem.DataTypes.BOOL,
            fail_safe_value=False,
        )
        return Dictionary(
            [
                sto_command_dict_item,
                ss1_command_dict_item,
                safe_input_dict_item,
            ]
        )

    @property
    def safety_master_pdu_map(self) -> RPDOMap:
        """The PDOMap used for the Safety Master PDU."""
        return self.__safety_master_pdu

    @property
    def safety_slave_pdu_map(self) -> TPDOMap:
        """The PDOMap used for the Safety Slave PDU."""
        return self.__safety_slave_pdu

    @property
    def state(self) -> FSoEState:
        """Get the FSoE master state."""
        return FSoEState(self.__master_handler.state.id)

    @property
    def running(self) -> bool:
        """True if FSoE Master is started, else False."""
        return self.__running


class PDUMapper:
    """Helper class to configure the Safety PDU PDOMaps."""

    FSOE_RPDO_MAP_1_INDEX = 0x1700
    FSOE_TPDO_MAP_1_INDEX = 0x1B00

    # Phase 1 mapping
    FSOE_COMMAND_SIZE_BITS = 8
    STO_COMMAND_SIZE_BITS = 1
    SS1_COMMAND_SIZE_BITS = 1
    STO_COMMAND_PADDING_SIZE_BITS = 6
    SBC_COMMAND_SIZE_BITS = 1
    SBC_COMMAND_PADDING_SIZE_BITS = 7
    CRC_O_SIZE_BITS = 16
    CONN_ID_SIZE_BITS = 16
    SAFE_INPUTS_SIZE_BITS = 1
    SAFE_INPUTS_PADDING_SIZE_BITS = 6

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
        ss1_command_item = RPDOMapItem(size_bits=cls.SS1_COMMAND_SIZE_BITS)
        rpdo_map.add_item(ss1_command_item)
        sto_padding_item = RPDOMapItem(size_bits=cls.STO_COMMAND_PADDING_SIZE_BITS)
        rpdo_map.add_item(sto_padding_item)
        sbc_command_item = RPDOMapItem(size_bits=cls.SBC_COMMAND_SIZE_BITS)
        rpdo_map.add_item(sbc_command_item)
        sbc_padding_item = RPDOMapItem(size_bits=cls.SBC_COMMAND_PADDING_SIZE_BITS)
        rpdo_map.add_item(sbc_padding_item)
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
        ss1_command_item = TPDOMapItem(size_bits=cls.SS1_COMMAND_SIZE_BITS)
        tpdo_map.add_item(ss1_command_item)
        sto_padding_item = TPDOMapItem(size_bits=cls.STO_COMMAND_PADDING_SIZE_BITS)
        tpdo_map.add_item(sto_padding_item)
        sbc_command_item = TPDOMapItem(size_bits=cls.SBC_COMMAND_SIZE_BITS)
        tpdo_map.add_item(sbc_command_item)
        safe_inputs_item = TPDOMapItem(size_bits=cls.SAFE_INPUTS_SIZE_BITS)
        tpdo_map.add_item(safe_inputs_item)
        safe_inputs_padding_item = TPDOMapItem(size_bits=cls.SAFE_INPUTS_PADDING_SIZE_BITS)
        tpdo_map.add_item(safe_inputs_padding_item)
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
        idx=0x4193, subidx=0x00, dtype=RegDtype.U16, access=RegAccess.RW
    )
    SAFE_INPUTS_MAP_REGISTER = EthercatRegister(
        identifier="SAFE_INPUTS_MAP",
        idx=0x46D2,
        subidx=0x00,
        dtype=RegDtype.U16,
        access=RegAccess.RW,
    )
    SS1_TIME_TO_STO_REGISTER = EthercatRegister(
        identifier="SS1_TIME_TO_STO",
        idx=0x6651,
        subidx=0x01,
        dtype=RegDtype.U16,
        access=RegAccess.RW,
    )

    def __init__(self, motion_controller: "MotionController") -> None:
        self.logger = ingenialogger.get_logger(__name__)
        self.__mc = motion_controller
        self.__handlers: dict[str, FSoEMasterHandler] = {}
        self.__next_connection_id = 1
        self._error_observers: list[Callable[[FSoEError], None]] = []
        self.__fsoe_configured = False

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
        application_parameters = self._get_application_parameters(servo)
        master_handler = FSoEMasterHandler(
            slave_address,
            self.__next_connection_id,
            fsoe_master_watchdog_timeout,
            application_parameters,
            partial(self._notify_errors, servo=servo),
        )
        self.__handlers[servo] = master_handler
        self.__next_connection_id += 1

    def configure_pdos(self, start_pdos: bool = False) -> None:
        """Configure the PDOs used for the Safety PDUs.

        Args:
            start_pdos: if ``True``, start the PDO exchange, if ``False``
                the PDO exchange should be started after. ``False`` by default.

        """
        self._set_pdo_maps_to_slaves()
        self._subscribe_to_pdo_thread_events()
        if start_pdos:
            self.__mc.capture.pdo.start_pdos()
        self.__fsoe_configured = True

    def stop_master(self, stop_pdos: bool = False) -> None:
        """Stop all the FSoE Master handlers.

        Args:
            stop_pdos: if ``True``, stop the PDO exchange. ``False`` by default.

        """
        for master_handler in self.__handlers.values():
            if master_handler.running:
                master_handler.stop()
        if self.__fsoe_configured:
            self._unsubscribe_from_pdo_thread_events()
        else:
            self.logger.warning("FSoE master is already stopped")
        if stop_pdos:
            self.__mc.capture.pdo.stop_pdos()
            if self.__fsoe_configured:
                self._remove_pdo_maps_from_slaves()
        self.__fsoe_configured = False

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

    def ss1_deactivate(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self.__handlers[servo]
        master_handler.ss1_deactivate()

    def ss1_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self.__handlers[servo]
        master_handler.ss1_activate()

    def get_safety_inputs_value(self, servo: str = DEFAULT_SERVO) -> bool:
        """Get a drive's safe inputs register value.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
           The safe inputs value.

        """
        master_handler = self.__handlers[servo]
        return master_handler.safe_inputs_value()

    def get_safety_address(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        drive = self.__mc._get_drive(servo)
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
        drive = self.__mc._get_drive(servo)
        drive.write(self.SAFETY_ADDRESS_REGISTER, data=address)

    def check_sto_active(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the STO is active in a given servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            True if the STO is active. False otherwise.

        """
        master_handler = self.__handlers[servo]
        return master_handler.is_sto_active()

    def wait_for_state_data(
        self, servo: str = DEFAULT_SERVO, timeout: Optional[float] = None
    ) -> None:
        """Wait for an FSoE master handler to reach the Data state.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            timeout : how many seconds to wait for the FSoE master to reach the
                Data state, if ``None`` it will wait forever.
                ``None`` by default.

        """
        master_handler = self.__handlers[servo]
        master_handler.wait_for_data_state(timeout)

    def get_fsoe_master_state(self, servo: str = DEFAULT_SERVO) -> FSoEState:
        """Get the servo's FSoE master handler state.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The servo's FSoE master handler state.

        """
        master_handler = self.__handlers[servo]
        return master_handler.state

    def subscribe_to_errors(self, callback: Callable[[FSoEError], None]) -> None:
        """Subscribe to the FSoE errors.

        Args:
            callback: Subscribed callback function.

        """
        if callback in self._error_observers:
            return
        self._error_observers.append(callback)

    def unsubscribe_from_errors(self, callback: Callable[[FSoEError], None]) -> None:
        """Unsubscribe from the FSoE errors.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._error_observers:
            return
        self._error_observers.remove(callback)

    def _notify_errors(self, transition_name: str, error_description: str, servo: str) -> None:
        """Notify subscribers when an FSoE error occurs.

        Args:
            transition_name: FSoE transition name.
            error_description: FSoE error description.
            servo: The servo alias.

        """
        for callback in self._error_observers:
            callback(FSoEError(servo, transition_name, error_description))

    def _delete_master_handler(self, servo: str = DEFAULT_SERVO) -> None:
        """Delete the master handler instance.

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
        """Get the FSoE master handlers requests.

        Callback method to send the FSoE Master handlers requests to the
        corresponding FSoE slave.
        """
        for master_handler in self.__handlers.values():
            master_handler.get_request()

    def _set_reply(self) -> None:
        """Set the FSoE Slaves responses.

        Callback method to provide the FSoE Slaves responses to their
        corresponding FSoE Master handler.
        """
        for master_handler in self.__handlers.values():
            master_handler.set_reply()

    def _pdo_thread_exception_handler(self, exc: Exception) -> None:
        """Callback method for the PDO thread exceptions."""
        self.logger.error(
            "The FSoE Master lost connection to the FSoE slaves. "
            f"An exception occurred during the PDO exchange: {exc}"
        )

    def _get_application_parameters(self, servo: str) -> list["ApplicationParameter"]:
        """Get values of the application parameters."""
        drive = self.__mc.servos[servo]
        application_parameters = []
        for register in [
            self.SAFE_INPUTS_MAP_REGISTER,
            self.SS1_TIME_TO_STO_REGISTER,
        ]:
            register_size_bytes, _ = dtype_value[register.dtype]
            application_parameter = ApplicationParameter(
                name=register.identifier,
                initial_value=drive.read(register),
                n_bytes=register_size_bytes,
            )
            application_parameters.append(application_parameter)
        return application_parameters
