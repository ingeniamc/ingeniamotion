import logging
import random
import time
from typing import TYPE_CHECKING, Callable, Optional

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

    On a Reset request, the slave captures its own last Session-state reply
    as a stale reply, to be returned automatically on the first non-Reset
    request of the new session. Once that stale reply has been delivered, the
    previous session's memory is forgotten so the next fresh startup (e.g.
    a different master handler connecting to the same physical slave) does
    not re-deliver it.
    """

    def __init__(self) -> None:
        self._replies_ever = 0
        self._replies_this_session = 0
        self._session_reply: Optional[bytes] = None
        self._stale_reply: Optional[bytes] = None

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

        if command == FSOECommand.RESET:
            # A new session is starting: this device's own Session-state
            # reply from whatever session just ended is still the last thing
            # it transmitted - exactly what a PDO thread would briefly
            # deliver right after a restart, since the device is never
            # power-cycled between sessions.
            self._stale_reply = self._session_reply
            self._replies_this_session = 0
            sequence_number = self._replies_ever
            connection_id = 0
        elif self._stale_reply is not None and command != FSOECommand.RESET:
            # First non-Reset request after a Reset: deliver the stale reply
            # from the previous session, then forget that previous session
            # entirely so the next fresh startup does not re-deliver it.
            stale_reply = self._stale_reply
            self._stale_reply = None
            self._session_reply = None
            self._replies_ever += 1
            return stale_reply
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

        if command == FSOECommand.SESSION:
            self._session_reply = reply_bytes

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

    def __init__(self, handler: "FSoEMasterHandler", slave: FSoESlave) -> None:
        self.master = handler
        self.slave = slave

    def replace_master(self, handler: "FSoEMasterHandler") -> None:
        """Connect a different master handler to the same slave."""
        self.master = handler

    def exchange_one_round(self) -> bytes:
        """Exchange one request/reply round.

        Returns:
            The reply bytes sent.
        """
        self.master.get_request()
        request_bytes = self.master.safety_master_pdu_map.get_item_bytes()
        reply_bytes = self.slave.compute_reply(request_bytes)
        self.master.safety_slave_pdu_map.set_item_bytes(reply_bytes)
        self.master.set_reply()
        return reply_bytes

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
def test_startup_replay_filter_is_not_shared_between_handler_instances() -> None:
    # One physical slave, one master instance connecting to it after another -
    # e.g. Motionlab switching between two FSoE master configurations against
    # the same drive - not two independent slaves.
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    mock_network = MockNetwork()

    errors_a: list[tuple[str, str]] = []
    handler_a = FSoEMasterHandler(
        servo=mock_servo,
        net=mock_network,
        use_sra=True,
        report_error_callback=lambda name, err: errors_a.append((name, err)),
    )
    network = FSoENetwork(handler_a, FSoESlave())
    try:
        # handler_a completes one full, real startup, is stopped, and
        # restarted - genuinely progressing past its own Reset state for
        # real, matching production timing where the CURRENT session's real
        # replies advance the handshake before any leftover PDO bytes from
        # the PREVIOUS session show up. This is also what turns
        # __in_initial_reset off, so a real error is no longer suppressed and
        # becomes visible in report_error_callback - the actual, user-facing
        # symptom from the original bug report.
        handler_a.start()
        network.exchange_to_data()
        assert handler_a.state == FSoEState.DATA
        handler_a.stop()

        handler_a.start()
        network.exchange_one_round()  # Reset -> fresh Reset reply, state -> SESSION
        assert handler_a.state == FSoEState.SESSION

        # The slave is never power-cycled: it still has its own Session-state
        # reply from the session that just ended as its last output, exactly
        # what a real device would still be transmitting right after a
        # restart. The slave auto-delivers its previous Session reply on the
        # next round; handler_a recognizes it as its own previously-seen reply
        # and suppresses it: no user-visible error is reported, and its state
        # is undisturbed.
        network.exchange_one_round()  # Session -> stale reply auto-delivered
        assert errors_a == []
        assert handler_a.state == FSoEState.SESSION

        # Complete the new session so the slave has a current Session reply
        # ready to replay when the next master connects.
        network.exchange_to_data()
        assert handler_a.state == FSoEState.DATA
        handler_a.stop()
    finally:
        handler_a.stop()
        handler_a.delete()

    # handler_a has fully disconnected from the slave. A second, independent
    # master instance now takes over the SAME slave (never power-cycled),
    # which still has handler_a's current Session reply as its last output.
    errors_b: list[tuple[str, str]] = []
    handler_b = FSoEMasterHandler(
        servo=mock_servo,
        net=mock_network,
        use_sra=True,
        report_error_callback=lambda name, err: errors_b.append((name, err)),
    )
    try:
        network.replace_master(handler_b)
        handler_b.start()
        network.exchange_one_round()  # Reset -> fresh Reset reply, state -> SESSION
        assert handler_b.state == FSoEState.SESSION

        # The slave automatically replays handler_a's Session reply. handler_b
        # has never seen it, so its own filter does not catch it: it reaches
        # the real master, which correctly rejects it as invalid for this
        # session, and that rejection is reported to the user.
        network.exchange_one_round()  # Session -> handler_a's reply replayed
        assert errors_b == [("SESSION_STAY2", "Invalid slave CRC")]
    finally:
        handler_b.delete()


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
