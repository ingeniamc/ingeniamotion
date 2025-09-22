import time
from typing import TYPE_CHECKING

import pytest
from ingenialink.ethercat.network import EthercatNetwork

from ingeniamotion.enums import FSoEState

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo

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


@pytest.mark.fsoe
def test_safety_pdo_map_subscription(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    servo: "EthercatServo",
):
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
