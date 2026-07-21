import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Callable

import pytest
from ingenialogger import get_logger

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError
from ingeniamotion.motion_controller import MotionController
from tests.conftest import timeout_loop

if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master

    from tests.fsoe.conftest import __set_default_phase2_mapping

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

logger = get_logger(__name__)


def test_fsoe_master_not_installed() -> None:
    try:
        import fsoe_master  # noqa: F401, PLC0415
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("fsoe_master is installed")

    mc = MotionController()
    with pytest.raises(NotImplementedError):
        mc.fsoe


@pytest.mark.fsoe
def test_start_and_stop_multiple_times(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Any fsoe error during the start/stop process
    # will fail the test because of error_handler

    for i in range(4):
        mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        assert handler.state == FSoEState.DATA
        time.sleep(1)
        assert handler.state == FSoEState.DATA
        mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
@pytest.mark.parametrize("mc_instance", ["mc_state_data", "mc_state_data_with_sra"])
def test_safe_inputs_value(request: pytest.FixtureRequest, mc_instance: str) -> None:
    mc = request.getfixturevalue(mc_instance)
    value = mc.fsoe.get_safety_inputs_value()

    # Assume safe inputs are disconnected on the setup
    assert value == 0


@pytest.mark.fsoe
def test_safety_address(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"], alias: str
) -> None:
    mc, _ = mc_with_fsoe

    master_handler = mc.fsoe._handlers[alias]

    mc.fsoe.set_safety_address(0x7453)
    # Setting the safety address has effects on the master
    assert master_handler._master_handler.master.session.slave_address.value == 0x7453

    # And on the slave
    assert mc.communication.get_register("FSOE_MANUF_SAFETY_ADDRESS") == 0x7453

    # The getter also works
    assert mc.fsoe.get_safety_address() == 0x7453


def mc_state_to_fsoe_master_state(state: FSoEState) -> Any:
    return {
        FSoEState.RESET: fsoe_master.StateReset,
        FSoEState.SESSION: fsoe_master.StateSession,
        FSoEState.CONNECTION: fsoe_master.StateConnection,
        FSoEState.PARAMETER: fsoe_master.StateParameter,
        FSoEState.DATA: fsoe_master.StateData,
    }[state]


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "state_enum",
    [
        FSoEState.RESET,
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ],
)
def test_get_master_state(
    mocker: "MockerFixture",
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
    state_enum: FSoEState,
) -> None:
    mc, _ = mc_with_fsoe

    # Master state is obtained as function
    # and not on the parametrize
    # to avoid depending on the optionally installed module
    # on pytest collection
    fsoe_master_state = mc_state_to_fsoe_master_state(state_enum)

    mocker.patch("fsoe_master.fsoe_master.MasterHandler.state", fsoe_master_state)

    assert mc.fsoe.get_fsoe_master_state() == state_enum


@pytest.mark.fsoe
def test_motor_enable(mc_state_data_with_sra: "MotionController") -> None:
    mc = mc_state_data_with_sra

    # Deactivate the SS1
    mc.fsoe.ss1_deactivate()
    # Deactivate the STO
    mc.fsoe.sto_deactivate()
    # Wait for the STO to be deactivated
    for _ in timeout_loop(
        timeout_sec=5, other=RuntimeError("Timeout waiting for STO deactivation")
    ):
        if not mc.fsoe.check_sto_active():
            break
    # Enable the motor
    mc.motion.motor_enable()
    # Disable the motor
    mc.motion.motor_disable()
    # Activate the SS1
    mc.fsoe.ss1_activate()
    # Activate the STO
    mc.fsoe.sto_activate()


@pytest.fixture
def pdo_thread_error_tracker(mc: "MotionController") -> Iterator[list[Exception]]:
    """Tracks errors in the PDO thread.

    Args:
        mc: Motion controller.

    Yields:
        List of exceptions captured from the PDO thread.
    """
    errors = []

    def error_callback(error: Exception) -> None:
        errors.append(error)

    mc.capture.pdo.subscribe_to_exceptions(error_callback)
    yield errors
    mc.capture.pdo.unsubscribe_to_exceptions(error_callback)


@pytest.mark.fsoe
def test_configure_pdos_without_starting_master(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    pdo_thread_error_tracker: list[Exception],
) -> None:
    """If master has not started, PDOs will fail in the first request."""
    mc, _ = mc_with_fsoe_with_sra

    assert len(pdo_thread_error_tracker) == 0
    mc.fsoe.configure_pdos(start_pdos=True, start_master=False)
    time.sleep(1.0)
    assert len(pdo_thread_error_tracker) == 1
    assert "FSoE Master is not running" in str(pdo_thread_error_tracker[0])


@pytest.mark.fsoe
def test_configure_pdos_starting_master(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    pdo_thread_error_tracker: list[Exception],
) -> None:
    """If master is started and PDOs are configured, data state should be reached."""
    mc, _ = mc_with_fsoe_with_sra

    assert len(pdo_thread_error_tracker) == 0
    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert len(pdo_thread_error_tracker) == 0

    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_start_master_without_configuring_pdos(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"], alias: str
) -> None:
    """Starting the master without configuring the PDOs should raise an error."""
    mc, _ = mc_with_fsoe_with_sra

    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    mc.capture.pdo.subscribe_to_exceptions(exception_callback)

    mc.fsoe.start_master(start_pdos=False)
    assert len(exceptions) == 0
    refresh_rate: float = 0.5
    mc.capture.pdo.start_pdos(refresh_rate=refresh_rate, servo=alias)
    time.sleep(2 * refresh_rate)
    assert len(exceptions) == 1
    assert "Please, check that the safe PDOs are correctly mapped" in str(exceptions[0])

    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_start_master_if_master_already_running(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    mc, _ = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    with pytest.raises(RuntimeError, match="FSoE Master is already running."):
        mc.fsoe.start_master(start_pdos=False)

    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_start_stop_master(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    fsoe_states: list["FSoEState"],
    timeout_for_data_sra: float,
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    assert handler.running is False
    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    assert handler.running is True

    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert fsoe_states[-1] is FSoEState.DATA

    # Stop the master without stopping the PDOs,
    # handler stops but the PDO maps remain even if it unsubscribes
    mc.fsoe.stop_master(stop_pdos=False)
    assert handler.running is False
    time.sleep(0.1)
    assert fsoe_states[-1] is FSoEState.RESET

    # FSoE state cycle is done again after restarting the master
    n_states = len(fsoe_states)
    mc.fsoe.start_master(start_pdos=False)
    assert handler.running is True
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert fsoe_states[-1] is FSoEState.DATA
    assert fsoe_states[n_states:] == [
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ]

    mc.fsoe.stop_master(stop_pdos=True)
    assert handler.running is False


def _setup_handler(
    mc: "MotionController",
    handler_states: dict["FSoEMasterHandler", list["FSoEState"]],
    state_change_callback: Callable[[FSoEState], None],
) -> "FSoEMasterHandler":
    handler = mc.fsoe.create_fsoe_master_handler(
        use_sra=True, state_change_callback=state_change_callback
    )
    handler_states[handler] = []
    if handler.process_image.editable:
        __set_default_phase2_mapping(handler)
        handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").set(0)

    if handler.sout_function() is not None:
        handler.sout_disable()
    return handler


@pytest.mark.fsoe
def test_start_precreated_first_handler_after_previous_fsoe_session(
    mc: "MotionController",
    alias: str,
    timeout_for_data_sra: float,
) -> None:
    """This test creates two FSoE master handlers and alternates between them,
    starting and stopping the FSoE session multiple times.
    It verifies that the handlers can successfully transition through the expected FSoE
    states without encountering errors.

    Args:
        mc: Motion controller.
        alias: Alias of the servo to test.
        timeout_for_data_sra: Timeout for waiting for FSoE data state.
    """
    n_iterations: int = 5
    handler_errors: list[FSoEError] = []
    handler_states: dict[FSoEMasterHandler, list[FSoEState]] = {}

    def on_handler_error(error: FSoEError) -> None:
        handler_errors.append(error)

    def on_handler_state_change(state: FSoEState) -> None:
        handler_states[active_handler].append(state)

    first_handler = _setup_handler(mc, handler_states, on_handler_state_change)
    second_handler = _setup_handler(mc, handler_states, on_handler_state_change)
    mc.fsoe.subscribe_to_errors(on_handler_error)

    logger.info(
        f"Starting test with {n_iterations} iterations and two FSoE "
        f"master handlers: {first_handler} and {second_handler}"
    )

    try:
        active_handler = first_handler

        for idx, _ in enumerate(range(n_iterations), start=1):
            logger.info(
                f"{idx}/{n_iterations}: Starting FSoE session with handler {active_handler}"
            )

            active_handler.configure_pdo_maps()
            active_handler.set_pdo_maps_to_slave()
            active_handler.start()

            mc.capture.pdo.start_pdos(servo=alias)
            assert active_handler.state is FSoEState.RESET, (
                f"{idx}/{n_iterations}: Expected state RESET, got {active_handler.state}"
            )
            active_handler.wait_for_data_state(timeout=timeout_for_data_sra)
            assert active_handler.state is FSoEState.DATA, (
                f"{idx}/{n_iterations}: Expected state DATA, got {active_handler.state}"
            )
            assert handler_errors == [], (
                f"{idx}/{n_iterations}: Unexpected errors: {handler_errors}"
            )
            assert handler_states[active_handler][-4:] == [
                FSoEState.SESSION,
                FSoEState.CONNECTION,
                FSoEState.PARAMETER,
                FSoEState.DATA,
            ], (
                f"{idx}/{n_iterations}: Unexpected state sequence: "
                f"{handler_states[active_handler][-4:]}"
            )

            active_handler.stop()
            mc.capture.pdo.stop_pdos(servo=alias)
            active_handler = second_handler if active_handler is first_handler else first_handler
    finally:
        mc.fsoe.unsubscribe_from_errors(on_handler_error)
        mc.fsoe.stop_master(stop_pdos=False)
        mc.fsoe._delete_master_handler()
        first_handler.delete()
        second_handler.delete()


@pytest.mark.fsoe
def test_startup_replies_from_previous_master_do_not_break_new_master(  # noqa: C901
    mc: "MotionController",
    alias: str,
    timeout_for_data_sra: float,
) -> None:
    """Replay all startup replies from a previous FSoE session into a fresh
    master and verify that startup still reaches DATA.

    The goal is to simulate a new master receiving a sequence of stale startup
    frames instead of a single stale frame.
    """

    handler_states: dict[FSoEMasterHandler, list[FSoEState]] = {}

    def on_handler_state_change(state: FSoEState) -> None:
        handler_states[active_handler].append(state)

    handler_a = _setup_handler(mc, handler_states, on_handler_state_change)
    handler_b = _setup_handler(mc, handler_states, on_handler_state_change)

    startup_replies: list[bytes] = []
    seen_replies: set[bytes] = set()

    try:
        # Handler A reaches DATA while we capture every unique reply seen during startup
        active_handler = handler_a
        handler_a.configure_pdo_maps()
        handler_a.set_pdo_maps_to_slave()
        handler_a.start()
        mc.capture.pdo.start_pdos(servo=alias)

        last_state_count = 0
        while handler_a.state is not FSoEState.DATA:
            try:
                reply = handler_a.safety_slave_pdu_map.get_item_bytes()

                if reply not in seen_replies:
                    startup_replies.append(reply)
                    seen_replies.add(reply)

                    logger.info(f"Captured startup reply {len(startup_replies)}: {reply.hex()}")
            except Exception:
                pass

            if len(handler_states[handler_a]) > last_state_count:
                logger.info(
                    f"Handler A transition => {handler_states[handler_a][-1]}",
                )

                last_state_count = len(handler_states[handler_a])

            time.sleep(0.01)

        handler_a.wait_for_data_state(timeout=timeout_for_data_sra)

        # Also capture one DATA-state frame
        data_reply = handler_a.safety_slave_pdu_map.get_item_bytes()
        if data_reply not in seen_replies:
            startup_replies.append(data_reply)
            seen_replies.add(data_reply)

        for idx, reply in enumerate(startup_replies):
            logger.info(
                f"Captured reply {idx + 1} = {reply.hex()}",
            )

        handler_a.stop()
        mc.capture.pdo.stop_pdos(servo=alias)

        # Fresh handler
        active_handler = handler_b
        handler_b.configure_pdo_maps()
        handler_b.set_pdo_maps_to_slave()
        handler_b.start()
        assert handler_b.state is FSoEState.RESET
        mc.capture.pdo.start_pdos(servo=alias)

        logger.info(
            f"Handler B before replay: state={handler_b.state} "
            f"transitions={handler_states[handler_b]}"
        )

        # Replay ALL startup replies from handler A
        for idx, reply in enumerate(startup_replies):
            logger.info(f"Replaying stale reply {idx + 1}/{len(startup_replies)}: {reply.hex()}")
            handler_b._master_handler.set_reply(reply)
            logger.info(
                f"After replay {idx + 1}: state={handler_b.state} "
                f"low_level={handler_b._master_handler.state.__name__} "
                f"command={handler_b._master_handler.slave.frame.control.command}"
            )

        previous_transition_count = len(handler_states[handler_b])

        # Observe the recovery/startup process after replaying all frames
        while handler_b.state is not FSoEState.DATA:
            try:
                current_reply = handler_b.safety_slave_pdu_map.get_item_bytes()

                logger.info(f"Live slave reply: {current_reply.hex()}")

                logger.info(
                    f"Parsed command={handler_b._master_handler.slave.frame.control.command} "
                    f"connection_id={handler_b._master_handler.slave.frame.control.connection_id}",
                )
            except Exception:
                pass

            if len(handler_states[handler_b]) > previous_transition_count:
                logger.info(f"Handler B transition => {handler_states[handler_b][-1]}")
                logger.info(f"Current request => {handler_b._master_handler.get_request().hex()}")
                previous_transition_count = len(handler_states[handler_b])

            time.sleep(0.01)

        logger.info(f"Handler B final state={handler_b.state}")
        logger.info(f"Handler B transitions={handler_states[handler_b]}")

        assert handler_b.state is FSoEState.DATA
        assert handler_states[handler_b][-4:] == [
            FSoEState.SESSION,
            FSoEState.CONNECTION,
            FSoEState.PARAMETER,
            FSoEState.DATA,
        ]
        handler_b.stop()

    finally:
        mc.capture.pdo.stop_pdos(servo=alias)
        handler_a.delete()
        handler_b.delete()
