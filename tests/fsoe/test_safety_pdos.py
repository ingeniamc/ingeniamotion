import time
from typing import TYPE_CHECKING

import pytest
from ingenialink.pdo import RPDOMapItem

from ingeniamotion.metaclass import DEFAULT_AXIS

try:
    import pysoem
except ImportError:
    pysoem = None

from ingeniamotion.enums import FSoEState
from ingeniamotion.motion_controller import MotionController

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork
    from ingenialink.ethercat.servo import EthercatServo
    from ingenialink.pdo import RPDOMap, TPDOMap

    from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


@pytest.fixture
def received_data() -> list[float]:
    data = []
    return data


@pytest.fixture
def exceptions() -> list[Exception]:
    exc = []
    return exc


@pytest.fixture
def create_pdo_maps(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    alias: str,
    received_data: list[float],
    exceptions: list[Exception],
) -> tuple["RPDOMap", "TPDOMap"]:
    mc, _ = mc_with_fsoe_with_sra
    actual_position = mc.capture.pdo.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=alias, axis=DEFAULT_AXIS
    )
    padding_rpdo_item = RPDOMapItem(size_bits=8)
    padding_rpdo_item.raw_data_bytes = int.to_bytes(0, 1, "little")
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps([padding_rpdo_item], [actual_position])
    tpdo_map.add_item(actual_position)
    mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=alias)

    def receive_callback():
        time_stamp = round(time.time(), 6)
        data_sample = [tpdo_map_item.value for tpdo_map_item in tpdo_map.items]
        received_data.append((time_stamp, data_sample))

    def exception_callback(exc):
        exceptions.append(exc)

    tpdo_map.subscribe_to_process_data_event(receive_callback)
    mc.capture.pdo.subscribe_to_exceptions(exception_callback, servo=alias)
    return rpdo_map, tpdo_map


@pytest.mark.fsoe
def test_start_pdos_without_starting_safety_master(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    alias: str,
    servo: "EthercatServo",
    exceptions: list[Exception],
    received_data: list[float],
    create_pdo_maps: tuple["RPDOMap", "TPDOMap"],  # noqa: ARG001
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Set safety maps to slave, do not start FSoE master
    # Setting the map to slaves already subscribes to safety PDU map events,
    # so unsubscribe from safe pdo map events that to avoid the master to start
    mc.fsoe.configure_pdos(start_pdos=False)
    handler.safety_master_pdu_map.unsubscribe_to_process_data_event()
    handler.safety_slave_pdu_map.unsubscribe_to_process_data_event()

    refresh_rate: float = 0.5
    mc.capture.pdo.start_pdos(refresh_rate=refresh_rate, servo=alias)
    time.sleep(4 * refresh_rate)
    assert len(exceptions) == 0
    assert len(received_data) > 0
    assert servo.slave.state is pysoem.OP_STATE


@pytest.mark.fsoe
def test_stop_master_while_pdos_are_still_active(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    exceptions: list[Exception],
    received_data: list[float],
    net: "EthercatNetwork",
    alias: str,
    create_pdo_maps: tuple["RPDOMap", "TPDOMap"],  # noqa: ARG001
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Configure and start the PDOs
    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert mc.fsoe.get_fsoe_master_state(servo=alias) is FSoEState.DATA

    # Data from non-safety PDOs should be received
    refresh_rate: float = net.pdo_manager._pdo_thread._refresh_rate
    time.sleep(2 * refresh_rate)
    assert len(exceptions) == 0
    assert len(received_data) > 0
    n_received_data = len(received_data)

    # Now stop the FSoE master while PDOs are still active
    assert handler.running is True
    mc.fsoe.stop_master(stop_pdos=False)
    assert handler.running is False

    # Data from non-safety PDOs should still be received
    time.sleep(2 * refresh_rate)
    assert len(exceptions) == 0
    assert len(received_data) > n_received_data


@pytest.mark.fsoe
def test_pdo_poller_with_fsoe_active(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    alias: str,
) -> None:
    """Test that a PDO poller can collect data while the FSoE master is active.

    The FSoE maps are configured first, then the poller sets its own maps without
    starting PDOs. The FSoE master is started, and only then PDOs are started so
    the safety callbacks find the master already running.
    """
    mc, _handler = mc_with_fsoe_with_sra

    # Configure FSoE maps without starting PDOs or master
    mc.fsoe.configure_pdos(start_pdos=False, start_master=False)

    # Create the poller without starting it (maps are set to the servo)
    registers = [{"name": "CL_POS_FBK_VALUE", "axis": 1}]
    sampling_time = 0.25
    samples_target = 4
    poller = mc.capture.pdo.create_poller(
        registers=registers, servo=alias, sampling_time=sampling_time, start=False
    )

    # Start the FSoE master with PDOs, then start the poller.
    # Since PDOs are already active, start() just subscribes to events.
    mc.fsoe.start_master(start_pdos=True)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert mc.fsoe.get_fsoe_master_state(servo=alias) is FSoEState.DATA
    poller.start()

    time.sleep((samples_target - 0.5) * sampling_time)

    # FSoE should still be in DATA while poller is running
    assert mc.fsoe.get_fsoe_master_state(servo=alias) is FSoEState.DATA

    # Stop FSoE master before stopping PDOs to avoid safety errors
    mc.fsoe.stop_master(stop_pdos=False)

    poller.stop()
    _timestamps, data = poller.data
    assert len(data) == len(registers)
    assert len(data[0]) >= samples_target
