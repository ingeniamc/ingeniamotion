import logging
import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, TextIO

import pytest
from ingenialink.dictionary import DictionarySafetyModule
from ingenialink.ethercat.network import EthercatNetwork

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError, FSoEMaster
from tests.conftest import refresh_registers_for_test_rollback
from tests.dictionaries import SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_XDFV3_DICTIONARY
from tests.fsoe.conftest import MockNetwork, MockServo

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.fsoe import FSoEApplicationParameter
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo
    from pytest_mock import MockerFixture

    from ingeniamotion.motion_controller import MotionController


@pytest.mark.fsoe
@pytest.mark.parametrize("use_sra", [False, True])
def test_create_fsoe_master_handler_use_sra(mc: "MotionController", use_sra: bool) -> None:
    master = FSoEMaster(mc)
    handler = master.create_fsoe_master_handler(use_sra=use_sra)
    safety_module = handler._FSoEMasterHandler__get_safety_module()

    assert safety_module.uses_sra is use_sra
    if not use_sra:
        assert handler._sra_fsoe_application_parameter is None
    else:
        assert isinstance(handler._sra_fsoe_application_parameter, FSoEApplicationParameter)

    assert len(safety_module.application_parameters) > 1
    assert len(handler.safety_parameters) == len(safety_module.application_parameters)

    # If SRA is not used, all safety parameters are passed
    if not use_sra:
        assert len(handler._master_handler.master.application_parameters) == len(
            safety_module.application_parameters
        )
    # If SRA is used, a single parameter with the CRC value of all application parameters is passed
    else:
        assert len(handler._master_handler.master.application_parameters) == 1

    master._delete_master_handler()


@pytest.mark.fsoe
def test_set_configured_module_ident_1(
    servo: "EthercatServo",
    mocker: "MockerFixture",
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    caplog: "pytest.LogCaptureFixture",
) -> None:
    _, handler = mc_with_fsoe_with_sra
    with refresh_registers_for_test_rollback(servo, ["MDP_CONFIGURED_MODULE_1"]):

        def create_mock_safety_module(
            module_ident: int, uses_sra: bool = True, has_project_crc: bool = False
        ) -> DictionarySafetyModule:
            if has_project_crc:
                params = [
                    DictionarySafetyModule.ApplicationParameter(
                        uid=handler._FSoEMasterHandler__FSOE_SAFETY_PROJECT_CRC
                    )
                ]
            else:
                params = [DictionarySafetyModule.ApplicationParameter(uid="DUMMY_PARAM")]

            return DictionarySafetyModule(
                module_ident=module_ident,
                uses_sra=uses_sra,
                application_parameters=params,
            )

        # Do not write mocked values to the servo
        mocker.patch.object(handler._FSoEMasterHandler__servo, "write")
        mock_safety_modules = {
            1: create_mock_safety_module(module_ident=1, uses_sra=True, has_project_crc=True)
        }
        mocker.patch.object(
            handler._FSoEMasterHandler__servo.dictionary,
            "safety_modules",
            mock_safety_modules,
        )

        caplog.set_level(logging.WARNING)
        with pytest.raises(
            RuntimeError,
            match="Module ident value to write could not be retrieved.",
        ):
            handler._FSoEMasterHandler__set_configured_module_ident_1()
        expected_warning = (
            f"Safety module has the application parameter "
            f"{handler._FSoEMasterHandler__FSOE_SAFETY_PROJECT_CRC}, skipping it."
        )
        assert expected_warning in caplog.text

        # Use a proper safety module
        mock_safety_modules = {
            2: create_mock_safety_module(module_ident=2, uses_sra=True, has_project_crc=False)
        }
        mocker.patch.object(
            handler._FSoEMasterHandler__servo.dictionary,
            "safety_modules",
            mock_safety_modules,
        )
        result = handler._FSoEMasterHandler__set_configured_module_ident_1()
        assert result == mock_safety_modules[2]


@pytest.mark.fsoe
def test_fsoe_master_get_safety_parameters(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    _, handler = mc_with_fsoe

    assert len(handler.safety_parameters) != 0


@pytest.mark.fsoe
def test_create_fsoe_handler_from_invalid_pdo_maps(
    caplog: "pytest.LogCaptureFixture", fsoe_error_monitor: Callable[[FSoEError], None]
) -> None:
    mock_servo = MockServo(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY)
    mock_servo.write("ETG_COMMS_RPDO_MAP256_6", 0x123456)  # Invalid pdo map value

    caplog.set_level(logging.ERROR)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        # An error has been logged
        logger_error = caplog.records[-1]
        assert logger_error.levelno == logging.ERROR
        assert (
            logger_error.message
            == "Error creating FSoE Process Image from RPDO and TPDO on the drive. "
            "Falling back to a default map."
        )

        # And the default minimal map is used
        assert len(handler.process_image.inputs) == 1
        assert len(handler.process_image.outputs) == 1
        assert handler.process_image.outputs[0].item.name == "FSOE_STO"
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_set_slave_address(fsoe_error_monitor: Callable[[FSoEError], None]) -> None:
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            slave_address=0x7412,
            report_error_callback=fsoe_error_monitor,
        )

        assert mock_servo.read(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS) == 0x7412
        assert handler._master_handler.get_slave_address() == 0x7412
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_inherit_slave_address(fsoe_error_monitor: Callable[[FSoEError], None]) -> None:
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        # Set the slave address in the servo
        mock_servo.write(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS, 0x4986)

        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        assert mock_servo.read(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS) == 0x4986
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_set_connection_id(fsoe_error_monitor: Callable[[FSoEError], None]) -> None:
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            connection_id=0x3742,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler._master_handler.master.session.connection_id.value == 0x3742
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_random_connection_id(fsoe_error_monitor: Callable[[FSoEError], None]) -> None:
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)

    random.seed(0x1234)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler._master_handler.master.session.connection_id.value == 0xED9A
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_pass_through_states(
    mc_state_data: "MotionController",  # noqa: ARG001
    fsoe_states: list["FSoEState"],
) -> None:
    assert fsoe_states == [
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ]


@pytest.mark.fsoe
def test_pass_through_states_sra(
    mc_state_data_with_sra: "MotionController",  # noqa: ARG001
    fsoe_states: list["FSoEState"],
) -> None:
    assert fsoe_states == [
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ]


@pytest.mark.fsoe
def test_handler_is_stopped_if_error_in_pdo_thread(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_states: list["FSoEState"],
    mocker: "MockerFixture",
) -> None:
    def mock_send_receive_processdata(*args, **kwargs):
        raise RuntimeError("Test error in PDO thread")

    mc, handler = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert fsoe_states[-1] == FSoEState.DATA
    assert handler.running is True

    # Force an error in data state and verify that the handler is stopped
    mocker.patch.object(
        EthercatNetwork,
        "send_receive_processdata",
        side_effect=mock_send_receive_processdata,
    )
    time.sleep(1.0)
    assert handler.running is False
    assert fsoe_states[-1] == FSoEState.RESET


if FSOE_MASTER_INSTALLED:
    from fsoe_master.fsoe_master import FSOECommand, FSOEFrame


class FSoESlave:
    """Represents a physical FSoE slave device, computing genuine replies via
    the ``fsoe_master`` library for framing/CRC generation - so the replies
    are real protocol traffic, not fabricated constants.

    Deliberately holds no reference to any ``FSoEMasterHandler``: a real FSoE
    slave doesn't contain a master, it only exchanges bytes with one over the
    wire - see ``FSoENetwork`` below, the only object that needs a reference
    to both sides. Because it outlives any one master connection (it's never
    power-cycled), it can hold onto a stale reply from a previous session and
    deliver it as the response to the first non-Reset request after a Reset,
    exactly what a PDO thread would briefly deliver right after a restart.

    The reply formula:
      - The safe data is an exact echo of the request's safe data.
      - The command matches the request's command.
      - ``crc0`` is the crc0 of the request being answered.
      - The frame header's connection_id is 0 during Reset/Session (before a
        session is established); from Connection state onward, the master's
        own request already carries the now-established connection_id in its
        header, so it's read directly off each request rather than tracked
        separately - no need to peek at the master's internal session object.
      - ``sequence_number`` is the number of replies already sent *in the
        current session* (0-indexed, reset every time a new Reset request
        starts a fresh session): confirmed via gdb that the compiled master
        checks it against replies accepted since the current session began,
        not a lifetime total. Reset itself doesn't validate
        sequence_number/crc0 at all (any command-matching frame is accepted)
        - but it does reject an exact byte-for-byte repeat of a
        previously-accepted frame, so a separate, never-resetting counter is
        used just for Reset's own crc/seq input, purely to keep its output
        bytes from colliding with an earlier session's Reset reply when the
        same handler restarts.

    None of ``sequence_number``/``crc0`` is transmitted on the wire - each
    side tracks them independently - so ``FSOEFrame.generate_crcs()`` only
    produces a CRC the real master will accept when fed the values above.

    When a new Reset request arrives, the slave first returns its previous
    output buffer, if any, before processing the Reset. The preserved output
    remains available for three exchange iterations, until the simulated PDO
    buffer is replaced by fresh output.
    """

    def __init__(self) -> None:
        self._replies_ever = 0
        self._replies_this_session = 0
        self._outgoing_reply: Optional[bytes] = None
        self._held_stale_reply: Optional[bytes] = None
        self._stale_replies_remaining = 0
        self._last_reply_source = "fresh"

    def _consume_stale_reply(self) -> Optional[bytes]:
        """Return the preserved reply while its simulated buffer is held."""
        if self._held_stale_reply is None or self._stale_replies_remaining == 0:
            return None
        stale_reply = self._held_stale_reply
        self._stale_replies_remaining -= 1
        if self._stale_replies_remaining == 0:
            self._held_stale_reply = None
        self._last_reply_source = "stale"
        self._replies_ever += 1
        return stale_reply

    @property
    def last_reply_source(self) -> str:
        """Return whether the last reply was fresh or stale."""
        return self._last_reply_source

    def compute_reply(self, request_bytes: bytes) -> bytes:
        """Compute the reply for one request.

        On the first non-Reset request after a Reset, returns the stale reply
        from the previous session (if any) instead of computing a fresh one.
        All other requests are answered with a freshly computed reply.

        Args:
            request_bytes: The master's current request, as raw bytes.

        Returns:
            The reply bytes.
        """
        request = FSOEFrame.frame_from_array(request_bytes)
        data = request.get_safe_data_bytes()[: request.safe_data_size_bytes]
        command = request.control.command
        self._last_reply_source = "fresh"

        if command == FSOECommand.RESET and self._outgoing_reply is not None:
            # The first PDO cycle after a restart can deliver the previous
            # output before the slave has processed the new Reset request.
            stale_reply = self._outgoing_reply
            self._held_stale_reply = stale_reply
            self._stale_replies_remaining = 3
            self._outgoing_reply = None
            stale_reply = self._consume_stale_reply()
            assert stale_reply is not None
            return stale_reply
        stale_reply = self._consume_stale_reply() if command != FSOECommand.RESET else None
        if stale_reply is not None:
            return stale_reply
        if command == FSOECommand.RESET:
            self._replies_this_session = 0
            sequence_number = self._replies_ever
            connection_id = 0
        elif command == FSOECommand.SESSION:
            sequence_number = self._replies_this_session
            connection_id = 0
        else:
            sequence_number = self._replies_this_session
            connection_id = request.control.connection_id

        reply = FSOEFrame.frame_from_array(request_bytes)
        reply.control.command = command
        reply.control.connection_id = connection_id
        reply.control.sequence_number = sequence_number
        reply.control.crc0 = int(request.crcs[0])
        reply.set_safe_data_bytes(data)
        reply.generate_crcs()
        reply_bytes = reply.frame_to_array()

        self._outgoing_reply = reply_bytes

        self._replies_ever += 1
        self._replies_this_session += 1
        return reply_bytes


class FSoENetwork:
    """The EtherCAT medium connecting a master handler to a slave device,
    cycling PDO data between them - the only object that needs a reference
    to both sides.

    The slave survives a master being replaced, e.g. when a different master
    handler connects to it after a previous one disconnects - matching real
    hardware, which is never power-cycled between them.
    """

    def __init__(
        self,
        handler: "FSoEMasterHandler",
        slave: FSoESlave,
        trace_path: Optional[Path] = None,
    ) -> None:
        self.master = handler
        self.slave = slave
        self._trace_path = trace_path
        self._trace_file: Optional[TextIO] = None
        self._round = 0
        if self._trace_path is not None:
            self._trace_file = self._trace_path.open("w", encoding="utf-8")
            self._trace_file.write("FSoE exchange trace\n")
            self._trace_file.flush()

    def __enter__(self) -> "FSoENetwork":
        """Return the network with its trace lifecycle managed by a context."""
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the trace file when leaving the network context."""
        self.close()

    def trace(self, marker: str, message: str) -> None:
        """Append a marked event to the exchange trace, if enabled."""
        if self._trace_file is None:
            return
        self._trace_file.write(f"[{marker}] {message}\n")
        self._trace_file.flush()

    def close(self) -> None:
        """Close the trace file, if one is open."""
        if self._trace_file is not None:
            self._trace_file.close()
            self._trace_file = None

    def replace_master(self, handler: "FSoEMasterHandler") -> None:
        """Connect a different master handler to the same slave."""
        self.master = handler

    def exchange_one_round(self) -> bytes:
        """Exchange one request/reply round.

        Returns:
            The reply bytes sent.
        """
        self._round += 1
        self.trace(
            f"ROUND {self._round:02d}",
            f"state_before={self.master.state.name}",
        )
        try:
            self.master.get_request()
            request_bytes = self.master.safety_master_pdu_map.get_item_bytes()
            self.trace(f"ROUND {self._round:02d}", f"request={request_bytes.hex(' ')}")
            reply_bytes = self.slave.compute_reply(request_bytes)
            self.trace(
                f"ROUND {self._round:02d}",
                f"reply_source={self.slave.last_reply_source}",
            )
            self.trace(f"ROUND {self._round:02d}", f"reply={reply_bytes.hex(' ')}")
            self.master.safety_slave_pdu_map.set_item_bytes(reply_bytes)
            self.master.set_reply()
            self.trace(
                f"ROUND {self._round:02d}",
                f"state_after={self.master.state.name}",
            )
            return reply_bytes
        except Exception as error:
            self.trace(
                f"ROUND {self._round:02d} EXCEPTION",
                f"{type(error).__name__}: {error}",
            )
            raise

    def exchange_to_data(self, max_rounds: int = 20) -> list[bytes]:
        """Exchange rounds until the master's startup handshake reaches Data.

        Reusable across a real ``stop()``/``start()`` restart, or a master
        replacement: the slave's own per-session counter resets whenever it
        sees a new Reset request, matching the real master's own behavior.

        Returns:
            The reply bytes sent, in order.

        Raises:
            RuntimeError: If Data state isn't reached within ``max_rounds``.
        """
        replies = []
        for _ in range(max_rounds):
            if self.master.state == FSoEState.DATA:
                return replies
            replies.append(self.exchange_one_round())
        raise RuntimeError(f"Did not reach Data state within {max_rounds} rounds")


@pytest.mark.fsoe
def test_mock_slave_drives_real_handshake_to_data_state() -> None:
    errors: list[tuple[str, str]] = []
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    handler = FSoEMasterHandler(
        servo=mock_servo,
        net=MockNetwork(),
        use_sra=True,
        report_error_callback=lambda name, err: errors.append((name, err)),
    )
    try:
        handler.start()
        FSoENetwork(handler, FSoESlave()).exchange_to_data()

        assert handler.state == FSoEState.DATA
        assert errors == []
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_stale_data_reply_survives_master_replacement() -> None:
    # One physical slave, one master instance connecting to it after another -
    # e.g. Motionlab switching between two FSoE master configurations against
    # the same drive - not two independent slaves.
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    mock_network = MockNetwork()
    trace_path = Path(os.environ.get("FSOE_TRACE_FILE", "fsoe_startup_sequence.log"))

    errors_a: list[tuple[str, str]] = []

    def report_error_a(name: str, error: str) -> None:
        errors_a.append((name, error))
        network.trace("HANDLER_A_ERROR", f"{name}: {error}")

    handler_a = FSoEMasterHandler(
        servo=mock_servo,
        net=mock_network,
        use_sra=True,
        report_error_callback=report_error_a,
    )
    network = FSoENetwork(handler_a, FSoESlave(), trace_path=trace_path)
    network.trace("TEST", "handler_a startup")
    try:
        # handler_a completes a real startup and exchanges one live DATA
        # packet, leaving that packet in the physical slave's PDO buffer.
        handler_a.start()
        network.exchange_to_data()
        assert handler_a.state == FSoEState.DATA
        network.exchange_one_round()  # DATA -> last live data reply
        network.trace(
            "STOP",
            f"request_before_stop={handler_a.safety_master_pdu_map.get_item_bytes().hex(' ')}, "
            f"state={handler_a.state.name}",
        )
        handler_a.stop()
        network.trace(
            "STOP",
            f"request_after_stop={handler_a.safety_master_pdu_map.get_item_bytes().hex(' ')}, "
            f"state={handler_a.state.name}",
        )
        assert errors_a == []
    finally:
        handler_a.stop()
        handler_a.delete()

    # handler_a has fully disconnected from the slave. A second, independent
    # master instance now takes over the SAME slave (never power-cycled),
    # which still has handler_a's last DATA reply as its last output.
    errors_b: list[tuple[str, str]] = []

    def report_error_b(name: str, error: str) -> None:
        errors_b.append((name, error))
        network.trace("HANDLER_B_ERROR", f"{name}: {error}")

    handler_b = FSoEMasterHandler(
        servo=mock_servo,
        net=mock_network,
        use_sra=True,
        report_error_callback=report_error_b,
    )
    try:
        network.replace_master(handler_b)
        network.trace("TEST", "handler_b startup on the same slave")
        handler_b.start()
        # The stale incoming DATA packet is delivered before B processes its
        # Reset, while the outgoing master request is independently replaced
        # with a fresh Reset on the next cycle.
        network.exchange_one_round()  # Reset -> stale DATA reply
        assert handler_b.state == FSoEState.RESET
        assert errors_b == []

        network.exchange_one_round()  # Reset -> fresh Reset reply
        assert handler_b.state == FSoEState.SESSION

        # The stale incoming DATA packet is delivered again while the master
        # is in SESSION. The master still reacts to it internally (it isn't
        # withheld), but the resulting error is recognized as caused by a
        # repeated slave reply and is not reported to the user.
        network.exchange_one_round()  # Session -> stale DATA reply
        assert errors_b == []
        assert handler_b.state == FSoEState.RESET
    finally:
        handler_b.delete()
        network.close()


@pytest.mark.fsoe
def test_safety_pdo_map_subscription(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    servo: "EthercatServo",
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Handler not subscribed if PDO maps are not set and no PDO map is mapped
    assert not handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {}
    assert servo._tpdo_maps == {}

    # Handler is subscribed after configuring the PDO maps
    # PDO maps are set but not yet started
    mc.fsoe.configure_pdos(start_pdos=False)
    assert handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {
        handler.safety_master_pdu_map.map_register_index: handler.safety_master_pdu_map
    }
    assert servo._tpdo_maps == {
        handler.safety_slave_pdu_map.map_register_index: handler.safety_slave_pdu_map
    }

    mc.fsoe.start_master()
    mc.capture.pdo.start_pdos()
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

    # Handler remains subscribed while in Data state
    assert handler._FSoEMasterHandler__is_subscribed_to_process_data_events

    # Stop the master, handler unsubscribes but the PDO maps remain
    mc.fsoe.stop_master(stop_pdos=False)
    assert not handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {
        handler.safety_master_pdu_map.map_register_index: handler.safety_master_pdu_map
    }
    assert servo._tpdo_maps == {
        handler.safety_slave_pdu_map.map_register_index: handler.safety_slave_pdu_map
    }

    mc.capture.pdo.stop_pdos()
