import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from ingeniamotion.enums import FSoEState

if TYPE_CHECKING:
    from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
    from ingeniamotion.motion_controller import MotionController

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


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
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    """Starting the master without configuring the PDOs should raise an error."""
    mc, _ = mc_with_fsoe_with_sra

    with pytest.raises(
        RuntimeError, match="FSoE master is not configured, can't start the master."
    ):
        mc.fsoe.start_master()


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
