import random
import time
from typing import TYPE_CHECKING

import pytest
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILError, ILWrongWorkingCountError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from packaging import version
from summit_testing_framework.setups.descriptors import EthercatMultiSlaveSetup

from ingeniamotion.enums import CommunicationType, OperationMode
from ingeniamotion.metaclass import DEFAULT_AXIS
from ingeniamotion.motion_controller import MotionController

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo


@pytest.mark.soem
def test_create_rpdo_item(mc: "MotionController", alias: str) -> None:
    position_set_point_initial_value = 100
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE",
        servo=alias,
        value=position_set_point_initial_value,
        axis=DEFAULT_AXIS,
    )
    assert isinstance(position_set_point, RPDOMapItem)
    assert position_set_point.value == position_set_point_initial_value


@pytest.mark.soem
def test_create_tpdo_item(mc: "MotionController", alias: str) -> None:
    actual_position = mc.capture.pdo.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=alias, axis=DEFAULT_AXIS
    )
    assert isinstance(actual_position, TPDOMapItem)


@pytest.mark.soem
def test_create_rpdo_item_no_initial_value(mc: "MotionController", alias: str) -> None:
    with pytest.raises(AttributeError):
        mc.capture.pdo.create_pdo_item("CL_POS_SET_POINT_VALUE", servo=alias, axis=DEFAULT_AXIS)


@pytest.mark.soem
def test_create_empty_rpdo_map(mc: "MotionController") -> None:
    rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 0


@pytest.mark.soem
def test_create_empty_tpdo_map(mc: "MotionController") -> None:
    tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 0


@pytest.mark.soem
def test_create_pdo_maps_single_item(mc: "MotionController", alias: str) -> None:
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=alias, value=0, axis=DEFAULT_AXIS
    )
    actual_position = mc.capture.pdo.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=alias, axis=DEFAULT_AXIS
    )
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps(position_set_point, actual_position)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 1
    assert position_set_point in rpdo_map.items
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 1
    assert actual_position in tpdo_map.items


@pytest.mark.soem
def test_create_pdo_maps_list_items(mc: "MotionController", alias: str) -> None:
    rpdo_regs = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    tpdo_regs = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
    rpdo_items = [
        mc.capture.pdo.create_pdo_item(rpdo_reg, servo=alias, value=0, axis=DEFAULT_AXIS)
        for rpdo_reg in rpdo_regs
    ]
    tpdo_items = [
        mc.capture.pdo.create_pdo_item(tpdo_reg, servo=alias, axis=DEFAULT_AXIS)
        for tpdo_reg in tpdo_regs
    ]
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps(rpdo_items, tpdo_items)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == len(rpdo_items)
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == len(tpdo_items)


@pytest.mark.soem
@pytest.mark.parametrize(
    "rpdo_maps, tpdo_maps",
    [
        [["rpdo", "rpdo"], ["rpdo", "tpdo"]],
        [["rpdo", "tpdo"], ["tpdo", "tpdo"]],
    ],
)
def test_set_pdo_maps_to_slave_exception(
    mc: "MotionController", alias: str, rpdo_maps: list[str], tpdo_maps: list[str]
) -> None:
    rx_maps = []
    tx_maps = []
    for map_type in rpdo_maps:
        pdo_map = (
            mc.capture.pdo.create_empty_rpdo_map()
            if map_type == "rpdo"
            else mc.capture.pdo.create_empty_tpdo_map()
        )
        rx_maps.append(pdo_map)
    for map_type in tpdo_maps:
        pdo_map = (
            mc.capture.pdo.create_empty_rpdo_map()
            if map_type == "rpdo"
            else mc.capture.pdo.create_empty_tpdo_map()
        )
        tx_maps.append(pdo_map)
    with pytest.raises(ValueError):
        mc.capture.pdo.set_pdo_maps_to_slave(rx_maps, tx_maps, servo=alias)


@pytest.mark.soem
def test_pdos_min_refresh_rate(net: "EthercatNetwork"):
    refresh_rate = 0.0001
    with pytest.raises(ValueError):
        net.activate_pdos(refresh_rate=refresh_rate)


@pytest.mark.soem
def test_pdos_watchdog_exception_auto(net: "EthercatNetwork"):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    refresh_rate = 3.5
    net.pdo_manager.subscribe_to_exceptions(exception_callback)
    net.activate_pdos(refresh_rate=refresh_rate)
    time.sleep(1)
    net.pdo_manager.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert str(exception) == "The sampling time is too high. The max sampling time is 3276.75 ms."


@pytest.mark.soem
def test_pdos_watchdog_exception_manual(net: "EthercatNetwork"):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    watchdog_timeout = 7
    net.pdo_manager.subscribe_to_exceptions(exception_callback)
    net.activate_pdos(watchdog_timeout=watchdog_timeout)
    time.sleep(1)
    net.pdo_manager.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert (
        str(exception) == "The watchdog timeout is too high. The max watchdog timeout is 6553.5 ms."
    )


@pytest.mark.soem_multislave
def test_start_pdos(
    mc: "MotionController",
    servo: list["EthercatServo"],
    alias: list[str],
    setup_descriptor,
) -> None:
    if not isinstance(setup_descriptor, EthercatMultiSlaveSetup):
        raise ValueError("Invalid setup config for test")

    pdo_map_items = {}
    initial_operation_modes = {}
    rpdo_values = {}
    tpdo_values = {}
    for s, a in zip(servo, alias):
        rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
        tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
        initial_operation_mode = mc.motion.get_operation_mode(servo=a)
        operation_mode = mc.capture.pdo.create_pdo_item(
            "DRV_OP_CMD", servo=a, value=initial_operation_mode.value, axis=DEFAULT_AXIS
        )
        actual_position = mc.capture.pdo.create_pdo_item(
            "CL_POS_FBK_VALUE", servo=a, axis=DEFAULT_AXIS
        )
        rpdo_map.add_item(operation_mode)
        tpdo_map.add_item(actual_position)
        mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=a)
        pdo_map_items[a] = (operation_mode, actual_position)
        random_op_mode = random.choice([
            op_mode for op_mode in OperationMode if op_mode != initial_operation_mode
        ])
        initial_operation_modes[a] = initial_operation_mode
        rpdo_values[a] = random_op_mode

    def send_callback():
        for a in alias:
            rpdo_map_item, _ = pdo_map_items[a]
            rpdo_map_item.value = rpdo_values[a].value

    def receive_callback():
        for a in alias:
            _, tpdo_map_item = pdo_map_items[a]
            tpdo_values[a] = tpdo_map_item.value

    refresh_rate = 0.5
    for s, a in zip(servo, alias):
        mc.capture.pdo.subscribe_to_send_process_data(send_callback, servo=a)
        mc.capture.pdo.subscribe_to_receive_process_data(receive_callback, servo=a)
        assert not mc.capture.pdo.is_active(servo=a)
        mc.capture.pdo.start_pdos(refresh_rate=refresh_rate, servo=a)
        assert mc.capture.pdo.is_active(servo=a)
        time.sleep(2 * refresh_rate)
        mc.capture.pdo.stop_pdos(servo=a)
        assert not mc.capture.pdo.is_active(servo=a)

        # TODO: check that pdos are still active after first drive removal, they will only be full deactivated if all servos are removed

        # Check that RPDO are being sent
        assert rpdo_values[a] == mc.motion.get_operation_mode(servo=a)
        # Check that TPDO are being received
        assert pytest.approx(tpdo_values[a], abs=2) == mc.motion.get_actual_position(servo=a)
        # Restore the initial operation mode
        mc.motion.set_operation_mode(initial_operation_modes[a], servo=a)
        s.remove_rpdo_map(rpdo_map_index=0)
        s.remove_tpdo_map(tpdo_map_index=0)


@pytest.mark.soem
def test_stop_pdos_exception(net: "EthercatNetwork") -> None:
    with pytest.raises(ILError):
        net.deactivate_pdos()


@pytest.mark.soem
def test_start_pdos_not_implemented_exception(mc: "MotionController") -> None:
    with pytest.raises(NotImplementedError):
        mc.capture.pdo.start_pdos(CommunicationType.Canopen)


@pytest.mark.virtual
def test_start_pdos_no_network() -> None:
    mc = MotionController()
    with pytest.raises(
        ValueError, match="No network created. Please create a network before starting PDOs."
    ):
        mc.capture.pdo.start_pdos()


@pytest.mark.virtual
def test_start_pdos_wrong_network_type_exception(mc: "MotionController", alias: str) -> None:
    """Error is raised if the servo to start the PDOs is not connected to an EtherCAT network."""
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos(servo=alias)


@pytest.mark.soem
def test_start_pdos_for_multiple_networks(mocker, mc: "MotionController") -> None:
    mock_net = {"ifname1": EthercatNetwork("ifname1"), "ifname2": EthercatNetwork("ifname2")}
    mock_servo_net = {"servo1": "ifname1", "servo2": "ifname2"}
    mocker.patch.object(mc, "_MotionController__net", mock_net)
    mocker.patch.object(mc, "_MotionController__servo_net", mock_servo_net)
    mocker.patch.object(EthercatNetwork, "activate_pdos")

    assert not len(mc.capture.pdo._PDONetworkManager__nets)
    mc.capture.pdo.start_pdos(servo="servo1")
    assert len(mc.capture.pdo._PDONetworkManager__nets) == 1
    assert "ifname1" in mc.capture.pdo._PDONetworkManager__nets

    mc.capture.pdo.start_pdos(servo="servo2")
    assert len(mc.capture.pdo._PDONetworkManager__nets) == 2
    assert "ifname2" in mc.capture.pdo._PDONetworkManager__nets


@pytest.mark.soem
def test_start_pdos_for_multiple_servos_in_same_network(mocker, mc: "MotionController") -> None:
    mock_net = {"ifname1": EthercatNetwork("ifname1")}
    mock_servo_net = {"servo1": "ifname1", "servo2": "ifname1"}
    mocker.patch.object(mc, "_MotionController__net", mock_net)
    mocker.patch.object(mc, "_MotionController__servo_net", mock_servo_net)
    mocker.patch.object(EthercatNetwork, "activate_pdos")

    assert not len(mc.capture.pdo._PDONetworkManager__nets)
    assert not len(mc.capture.pdo._PDONetworkManager__servo_to_nets)
    mc.capture.pdo.start_pdos(servo="servo1")
    assert len(mc.capture.pdo._PDONetworkManager__nets) == 1
    assert len(mc.capture.pdo._PDONetworkManager__servo_to_nets) == 1
    assert "ifname1" in mc.capture.pdo._PDONetworkManager__nets
    assert mc.capture.pdo._PDONetworkManager__servo_to_nets == {"servo1": "ifname1"}

    mc.capture.pdo.start_pdos(servo="servo2")
    assert len(mc.capture.pdo._PDONetworkManager__nets) == 1
    assert len(mc.capture.pdo._PDONetworkManager__servo_to_nets) == 2
    assert mc.capture.pdo._PDONetworkManager__servo_to_nets == {
        "servo1": "ifname1",
        "servo2": "ifname1",
    }


def skip_if_pdo_padding_is_not_available(mc: "MotionController", alias: str) -> None:
    # Check if monitoring is available (To discard EVE-XCR-E)
    try:
        mc.capture._check_version(alias)
    except NotImplementedError:
        is_monitoring_available = False
    else:
        is_monitoring_available = True
    pdo_poller_fw_version = "2.5.0"
    firmware_version = mc.configuration.get_fw_version(alias, 1)
    if (
        version.parse(firmware_version) < version.parse(pdo_poller_fw_version)
        or not is_monitoring_available
    ):
        pytest.skip(
            f"PDO poller is available for firmware version {pdo_poller_fw_version} or higher. "
            f"Firmware version found: {firmware_version}"
        )


@pytest.mark.soem
def test_create_poller(mc: "MotionController", alias: str) -> None:
    skip_if_pdo_padding_is_not_available(mc, alias)
    registers = [{"name": "CL_POS_FBK_VALUE", "axis": 1}, {"name": "CL_VEL_FBK_VALUE", "axis": 1}]
    sampling_time = 0.25
    samples_target = 4
    sleep_time = (samples_target - 0.5) * sampling_time
    poller = mc.capture.pdo.create_poller(
        registers=registers, servo=alias, sampling_time=sampling_time
    )
    time.sleep(sleep_time)
    poller.stop()
    timestamps, data = poller.data
    channel_0_data, channel_1_data = data
    assert len(channel_0_data) == samples_target
    assert len(channel_1_data) == samples_target
    assert len(data) == len(registers)
    assert len(timestamps) == len(channel_0_data)


@pytest.mark.soem
def test_subscribe_exceptions(net: "EthercatNetwork", mocker) -> None:
    error_msg = "Test error"

    def start_pdos(*_):
        raise ILWrongWorkingCountError(error_msg)

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.stop_pdos")
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.start_pdos",
        new=start_pdos,
    )
    patch_callback = mocker.patch(
        "ingenialink.pdo_network_manager.PDONetworkManager._notify_exceptions"
    )

    net.pdo_manager.subscribe_to_exceptions(patch_callback)
    net.activate_pdos()

    t = time.time()
    timeout = 1
    while not net.pdo_manager._pdo_thread._pd_thread_stop_event.is_set() and (
        (time.time() - t) < timeout
    ):
        pass

    assert net.pdo_manager._pdo_thread._pd_thread_stop_event.is_set()
    patch_callback.assert_called_once()
    assert (
        str(patch_callback.call_args_list[0][0][0])
        == f"Stopping the PDO thread due to the following exception: {error_msg} "
    )
    net.deactivate_pdos()
