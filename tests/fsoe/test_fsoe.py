import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController
from tests.conftest import timeout_loop

if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


def test_fsoe_master_not_installed() -> None:
    try:
        import fsoe_master  # noqa: F401
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
