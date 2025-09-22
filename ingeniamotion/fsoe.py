from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Optional, cast

import ingenialogger
from ingenialink.ethercat.servo import EthercatServo

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe_master.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.metaclass import DEFAULT_SERVO

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork

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

    def __init__(self, motion_controller: "MotionController") -> None:
        self.logger = ingenialogger.get_logger(__name__)
        self.__mc = motion_controller
        self._handlers: dict[str, FSoEMasterHandler] = {}
        self.__next_connection_id = 1
        self._error_observers: list[Callable[[FSoEError], None]] = []

    def create_fsoe_master_handler(
        self,
        use_sra: bool,
        servo: str = DEFAULT_SERVO,
        fsoe_master_watchdog_timeout: Optional[float] = None,
        state_change_callback: Optional[Callable[[FSoEState], None]] = None,
    ) -> "FSoEMasterHandler":
        """Create an FSoE Master handler linked to a Safe servo drive.

        Raises:
            TypeError: If the servo is not an EthercatServo.

        Args:
            use_sra: True to use SRA, False otherwise.
            servo: servo alias to reference it. ``default`` by default.
            fsoe_master_watchdog_timeout: The FSoE master watchdog timeout in seconds.
            state_change_callback: Optional callback to be called when the
                FSoE master handler state changes.

        Returns:
            An instance of FSoEMasterHandler.
        """
        if fsoe_master_watchdog_timeout is None:
            fsoe_master_watchdog_timeout = FSoEMasterHandler.DEFAULT_WATCHDOG_TIMEOUT_S
        node = self.__mc.servos[servo]
        if not isinstance(node, EthercatServo):
            raise TypeError("Functional Safety over Ethercat is only available for Ethercat servos")
        net = cast("EthercatNetwork", self.__mc._get_network(servo=servo))

        master_handler = FSoEMasterHandler(
            servo=node,
            net=net,
            use_sra=use_sra,
            connection_id=self.__next_connection_id,
            watchdog_timeout=fsoe_master_watchdog_timeout,
            report_error_callback=partial(self._notify_errors, servo=servo),
            state_change_callback=state_change_callback,
        )
        self._handlers[servo] = master_handler
        self.__next_connection_id += 1
        return master_handler

    def start_master(self, start_pdos: bool = False) -> None:
        """Start an FSoE Master handler.

        Args:
            start_pdos: if ``True``, start the PDO exchange, if ``False``
                the PDO exchange should be started after. ``False`` by default.
        """
        for master_handler in self._handlers.values():
            master_handler.start()

        if start_pdos:
            for servo in self._handlers:
                self.__mc.capture.pdo.start_pdos(servo=servo)

    def configure_pdos(self, start_pdos: bool = False, start_master: bool = False) -> None:
        """Configure the PDOs used for the Safety PDUs.

        Args:
            start_pdos: if ``True``, start the PDO exchange, if ``False``
                the PDO exchange should be started after. ``False`` by default.
            start_master: if ``True``, start the FSoE master handlers after
                configuring the PDOs. ``False`` by default.
        """
        self._configure_and_set_pdo_maps_to_slaves()
        if start_master:
            self.start_master(start_pdos=start_pdos)
        elif start_pdos:
            for servo in self._handlers:
                self.__mc.capture.pdo.start_pdos(servo=servo)

    def stop_master(self, stop_pdos: bool = False) -> None:
        """Stop all the FSoE Master handlers.

        Args:
            stop_pdos: if ``True``, stop the PDO exchange. ``False`` by default.

        """
        for master_handler in self._handlers.values():
            if master_handler.running:
                master_handler.stop()
        if stop_pdos:
            for servo in self._handlers:
                self.__mc.capture.pdo.stop_pdos(servo=servo)

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

    def sout_disable(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the Safety Output.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.sout_disable()

    def sout_enable(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the Safety Output.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.sout_enable()

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

    def set_fail_safe(self, fail_safe: bool, servo: str = DEFAULT_SERVO) -> None:
        """Set the fail-safe mode of the FSoE master handler.

        Args:
            fail_safe: True to set the fail-safe mode, False to remove it.
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.set_fail_safe(fail_safe)

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

    def _configure_and_set_pdo_maps_to_slaves(self) -> None:
        """Configure the PDOMaps used by the Safety PDUs in the slaves."""
        for master_handler in self._handlers.values():
            master_handler.configure_pdo_maps()
            master_handler.set_pdo_maps_to_slave()

    def _remove_pdo_maps_from_slaves(self) -> None:
        """Remove the PDOMaps used by the Safety PDUs from the slaves."""
        for master_handler in self._handlers.values():
            master_handler.remove_pdo_maps_from_slave()
