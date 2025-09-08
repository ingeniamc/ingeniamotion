import time
from typing import TYPE_CHECKING

import pytest
from ingenialink.ethercat.network import EthercatNetwork

from ingeniamotion.enums import FSoEState

if TYPE_CHECKING:
    from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
    from ingeniamotion.motion_controller import MotionController

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


@pytest.mark.fsoe
def test_handler_is_stopped_if_error_in_pdo_thread(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_states: list["FSoEState"],
    mocker,
):
    def mock_send_receive_processdata(*args, **kwargs):
        raise RuntimeError("Test error in PDO thread")

    mc, handler = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True)

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
