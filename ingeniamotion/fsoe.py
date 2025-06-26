from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Optional, Union

import ingenialogger
from ingenialink.dictionary import DictionarySafetyModule
from ingenialink.ethercat.servo import EthercatServo

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe_master.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.metaclass import DEFAULT_SERVO

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController

__all__ = ["FSOE_MASTER_INSTALLED", "FSoEMaster", "FSoEError"]


@dataclass
class FSoEError:
    """FSoE Error descriptor."""

    servo: str
    transition_name: str
    description: str


class FSoEMaster:
    """FSoE Master.

    Args:
        motion_controller: The MotionController instance.

    """

    __MDP_CONFIGURED_MODULE_1 = "MDP_CONFIGURED_MODULE_1"

    def __init__(self, motion_controller: "MotionController") -> None:
        self.logger = ingenialogger.get_logger(__name__)
        self.__mc = motion_controller
        self._handlers: dict[str, FSoEMasterHandler] = {}
        self.__next_connection_id = 1
        self._error_observers: list[Callable[[FSoEError], None]] = []
        self.__fsoe_configured = False

    def create_fsoe_master_handler(
        self, servo: str = DEFAULT_SERVO, fsoe_master_watchdog_timeout: Optional[float] = None
    ) -> "FSoEMasterHandler":
        """Create an FSoE Master handler linked to a Safe servo drive.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            fsoe_master_watchdog_timeout: The FSoE master watchdog timeout in seconds.

        """
        if fsoe_master_watchdog_timeout is None:
            fsoe_master_watchdog_timeout = FSoEMasterHandler.DEFAULT_WATCHDOG_TIMEOUT_S
        node = self.__mc.servos[servo]
        if not isinstance(node, EthercatServo):
            raise TypeError("Functional Safety over Ethercat is only available for Ethercat servos")
        slave_address = self._get_safety_address_from_drive(servo)

        master_handler = FSoEMasterHandler(
            node,
            safety_module=self.__get_safety_module(servo=servo),
            slave_address=slave_address,
            connection_id=self.__next_connection_id,
            watchdog_timeout=fsoe_master_watchdog_timeout,
            report_error_callback=partial(self._notify_errors, servo=servo),
        )
        self._handlers[servo] = master_handler
        self.__next_connection_id += 1
        return master_handler

    def _get_safety_address_from_drive(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address configured in the drive.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        value = self.__mc.communication.get_register(
            FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS, servo
        )
        if not isinstance(value, int):
            raise ValueError(f"Wrong safety address value type. Expected int, got {type(value)}")
        return value

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
        for master_handler in self._handlers.values():
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
        master_handler = self._handlers[servo]
        master_handler.sto_deactivate()

    def sto_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the Safety Torque Off.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.sto_activate()

    def ss1_deactivate(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.ss1_deactivate()

    def ss1_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.ss1_activate()

    def get_safety_inputs_value(self, servo: str = DEFAULT_SERVO) -> bool:
        """Get a drive's safe inputs register value.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
           The safe inputs value.

        """
        master_handler = self._handlers[servo]
        return master_handler.safe_inputs_value()

    def get_safety_address(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        master_handler = self._handlers[servo]
        return master_handler.get_safety_address()

    def set_safety_address(self, address: int, servo: str = DEFAULT_SERVO) -> None:
        """Set the drive's FSoE slave address.

        Args:
            address: The address to be set.
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        return master_handler.set_safety_address(address)

    def __get_configured_module_ident_1(
        self, servo: str = DEFAULT_SERVO
    ) -> Union[int, float, str, bytes]:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Configured Module Ident 1.
        """
        return self.__mc.communication.get_register(
            register=self.__MDP_CONFIGURED_MODULE_1, servo=servo, axis=0
        )

    def __get_safety_module(self, servo: str = DEFAULT_SERVO) -> DictionarySafetyModule:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Safety module.

        Raises:
            NotImplementedError: if the safety module uses SRA.
        """
        drive = self.__mc._get_drive(servo)
        module_ident = int(self.__get_configured_module_ident_1(servo=servo))
        safety_module = drive.dictionary.get_safety_module(module_ident=module_ident)
        if safety_module.uses_sra:
            self.logger.warning("Safety module with SRA is not available.")
        return safety_module

    def check_sto_active(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the STO is active in a given servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            True if the STO is active. False otherwise.

        """
        master_handler = self._handlers[servo]
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
        master_handler = self._handlers[servo]
        master_handler.wait_for_data_state(timeout)

    def get_fsoe_master_state(self, servo: str = DEFAULT_SERVO) -> FSoEState:
        """Get the servo's FSoE master handler state.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The servo's FSoE master handler state.

        """
        master_handler = self._handlers[servo]
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
        if servo not in self._handlers:
            return
        self._handlers[servo].delete()
        del self._handlers[servo]

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
        for master_handler in self._handlers.values():
            master_handler.set_pdo_maps_to_slave()

    def _remove_pdo_maps_from_slaves(self) -> None:
        """Remove the PDOMaps used by the Safety PDUs from the slaves."""
        for master_handler in self._handlers.values():
            master_handler.remove_pdo_maps_from_slave()

    def _get_request(self) -> None:
        """Get the FSoE master handlers requests.

        Callback method to send the FSoE Master handlers requests to the
        corresponding FSoE slave.
        """
        for master_handler in self._handlers.values():
            master_handler.get_request()

    def _set_reply(self) -> None:
        """Set the FSoE Slaves responses.

        Callback method to provide the FSoE Slaves responses to their
        corresponding FSoE Master handler.
        """
        for master_handler in self._handlers.values():
            master_handler.set_reply()

    def _pdo_thread_exception_handler(self, exc: Exception) -> None:
        """Callback method for the PDO thread exceptions."""
        self.logger.error(
            "The FSoE Master lost connection to the FSoE slaves. "
            f"An exception occurred during the PDO exchange: {exc}"
        )
