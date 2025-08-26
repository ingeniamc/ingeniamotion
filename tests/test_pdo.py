import random
import time

import pytest
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILWrongWorkingCountError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from packaging import version
from summit_testing_framework.setups.descriptors import EthercatMultiSlaveSetup

from ingeniamotion.enums import CommunicationType, OperationMode
from ingeniamotion.exceptions import IMError


@pytest.mark.soem
def test_create_rpdo_item(mc, alias):
    position_set_point_initial_value = 100
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=alias, value=position_set_point_initial_value
    )
    assert isinstance(position_set_point, RPDOMapItem)
    assert position_set_point.value == position_set_point_initial_value


@pytest.mark.soem
def test_create_tpdo_item(mc, alias):
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
    assert isinstance(actual_position, TPDOMapItem)


@pytest.mark.soem
def test_create_rpdo_item_no_initial_value(mc, alias):
    with pytest.raises(AttributeError):
        mc.capture.pdo.create_pdo_item("CL_POS_SET_POINT_VALUE", servo=alias)


@pytest.mark.soem
def test_create_empty_rpdo_map(mc):
    rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 0


@pytest.mark.soem
def test_create_empty_tpdo_map(mc):
    tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 0


@pytest.mark.soem
def test_create_pdo_maps_single_item(mc, alias):
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=alias, value=0
    )
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps(position_set_point, actual_position)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 1
    assert position_set_point in rpdo_map.items
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 1
    assert actual_position in tpdo_map.items


@pytest.mark.soem
def test_create_pdo_maps_list_items(mc, alias):
    rpdo_regs = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    tpdo_regs = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
    rpdo_items = [
        mc.capture.pdo.create_pdo_item(rpdo_reg, servo=alias, value=0) for rpdo_reg in rpdo_regs
    ]
    tpdo_items = [mc.capture.pdo.create_pdo_item(tpdo_reg, servo=alias) for tpdo_reg in tpdo_regs]
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps(rpdo_items, tpdo_items)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == len(rpdo_items)
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == len(tpdo_items)


@pytest.mark.soem
@pytest.mark.parametrize(
    "register, value, pdo_type",
    [
        ("CL_POS_FBK_VALUE", None, "tpdo"),
        ("CL_VEL_SET_POINT_VALUE", 0, "rpdo"),
    ],
)
def test_add_pdo_item_to_map(mc, alias, register, value, pdo_type):
    if pdo_type == "rpdo":
        pdo_map = mc.capture.pdo.create_empty_rpdo_map()
    else:
        pdo_map = mc.capture.pdo.create_empty_tpdo_map()
    pdo_map_item = mc.capture.pdo.create_pdo_item(register, servo=alias, value=value)
    mc.capture.pdo.add_pdo_item_to_map(pdo_map_item, pdo_map)
    assert len(pdo_map.items) == 1
    assert pdo_map_item in pdo_map.items


@pytest.mark.soem
@pytest.mark.parametrize(
    "register, value, pdo_type",
    [
        ("CL_POS_FBK_VALUE", None, "tpdo"),
        ("CL_VEL_SET_POINT_VALUE", 0, "rpdo"),
    ],
)
def test_add_pdo_item_to_map_exceptions(mc, alias, register, value, pdo_type):
    if pdo_type == "tpdo":
        pdo_map = mc.capture.pdo.create_empty_rpdo_map()
    else:
        pdo_map = mc.capture.pdo.create_empty_tpdo_map()
    pdo_map_item = mc.capture.pdo.create_pdo_item(register, servo=alias, value=value)
    with pytest.raises(ValueError):
        mc.capture.pdo.add_pdo_item_to_map(pdo_map_item, pdo_map)


@pytest.mark.soem
@pytest.mark.parametrize(
    "rpdo_maps, tpdo_maps",
    [
        [["rpdo", "rpdo"], ["rpdo", "tpdo"]],
        [["rpdo", "tpdo"], ["tpdo", "tpdo"]],
    ],
)
def test_set_pdo_maps_to_slave_exception(mc, alias, rpdo_maps, tpdo_maps):
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
        mc.capture.pdo.set_pdo_maps_to_slave(rx_maps, tx_maps, alias)


@pytest.mark.soem
def test_pdos_min_refresh_rate(mc):
    refresh_rate = 0.0001
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos(CommunicationType.Ethercat, refresh_rate)


@pytest.mark.soem
def test_pdos_watchdog_exception_auto(mc):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    refresh_rate = 3.5
    mc.capture.pdo.subscribe_to_exceptions(exception_callback)
    mc.capture.pdo.start_pdos(CommunicationType.Ethercat, refresh_rate)
    time.sleep(1)
    mc.capture.pdo.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert str(exception) == "The sampling time is too high. The max sampling time is 3276.75 ms."


@pytest.mark.soem
def test_pdos_watchdog_exception_manual(mc):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    watchdog_timeout = 7
    mc.capture.pdo.subscribe_to_exceptions(exception_callback)
    mc.capture.pdo.start_pdos(CommunicationType.Ethercat, watchdog_timeout=watchdog_timeout)
    time.sleep(1)
    mc.capture.pdo.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert (
        str(exception) == "The watchdog timeout is too high. The max watchdog timeout is 6553.5 ms."
    )


@pytest.mark.soem_multislave
def test_start_pdos(mc, alias, setup_descriptor):
    if not isinstance(setup_descriptor, EthercatMultiSlaveSetup):
        raise ValueError("Invalid setup config for test")

    pdo_map_items = {}
    initial_operation_modes = {}
    rpdo_values = {}
    tpdo_values = {}
    for a in alias:
        rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
        tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
        initial_operation_mode = mc.motion.get_operation_mode(servo=a)
        operation_mode = mc.capture.pdo.create_pdo_item(
            "DRV_OP_CMD", servo=a, value=initial_operation_mode.value
        )
        actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=a)
        mc.capture.pdo.add_pdo_item_to_map(operation_mode, rpdo_map)
        mc.capture.pdo.add_pdo_item_to_map(actual_position, tpdo_map)
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

    mc.capture.pdo.subscribe_to_send_process_data(send_callback)
    mc.capture.pdo.subscribe_to_receive_process_data(receive_callback)
    assert not mc.capture.pdo.is_active
    refresh_rate = 0.5
    mc.capture.pdo.start_pdos(refresh_rate=refresh_rate)
    assert mc.capture.pdo.is_active
    time.sleep(2 * refresh_rate)
    mc.capture.pdo.stop_pdos()
    assert not mc.capture.pdo.is_active
    for a in alias:
        # Check that RPDO are being sent
        assert rpdo_values[a] == mc.motion.get_operation_mode(servo=a)
        # Check that TPDO are being received
        assert pytest.approx(tpdo_values[a], abs=2) == mc.motion.get_actual_position(servo=a)
        # Restore the initial operation mode
        mc.motion.set_operation_mode(initial_operation_modes[a], servo=a)
        mc.capture.pdo.clear_pdo_mapping(a)


@pytest.mark.soem
def test_stop_pdos_exception(mc):
    with pytest.raises(IMError):
        mc.capture.pdo.stop_pdos()


@pytest.mark.soem
def test_start_pdos_not_implemented_exception(mc):
    with pytest.raises(NotImplementedError):
        mc.capture.pdo.start_pdos(CommunicationType.Canopen)


@pytest.mark.soem
def test_start_pdos_wrong_network_type_exception(mc):
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos("ethernet")


@pytest.mark.soem
def test_start_pdos_number_of_network_exception(mocker, mc):
    mock_net = {"ifname1": EthercatNetwork("ifname1"), "ifname2": EthercatNetwork("ifname2")}
    mocker.patch.object(mc, "_MotionController__net", mock_net)
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos()
    with pytest.raises(IMError):
        mc.capture.pdo.start_pdos(CommunicationType.Ethercat)


def skip_if_pdo_padding_is_not_available(mc, alias):
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
def test_create_poller(mc, alias):
    skip_if_pdo_padding_is_not_available(mc, alias)
    registers = [{"name": "CL_POS_FBK_VALUE", "axis": 1}, {"name": "CL_VEL_FBK_VALUE", "axis": 1}]
    sampling_time = 0.25
    samples_target = 4
    sleep_time = (samples_target - 0.5) * sampling_time
    poller = mc.capture.pdo.create_poller(registers, alias, sampling_time)
    time.sleep(sleep_time)
    poller.stop()
    timestamps, data = poller.data
    channel_0_data, channel_1_data = data
    assert len(channel_0_data) == samples_target
    assert len(channel_1_data) == samples_target
    assert len(data) == len(registers)
    assert len(timestamps) == len(channel_0_data)


@pytest.mark.soem
def test_subscribe_exceptions(mc, mocker):
    error_msg = "Test error"

    def start_pdos(*_):
        raise ILWrongWorkingCountError(error_msg)

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.stop_pdos")
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.start_pdos",
        new=start_pdos,
    )
    patch_callback = mocker.patch("ingeniamotion.pdo.PDONetworkManager._notify_exceptions")

    mc.capture.pdo.subscribe_to_exceptions(patch_callback)
    mc.capture.pdo.start_pdos()

    t = time.time()
    timeout = 1
    while not mc.capture.pdo._pdo_thread._pd_thread_stop_event.is_set() and (
        (time.time() - t) < timeout
    ):
        pass

    assert mc.capture.pdo._pdo_thread._pd_thread_stop_event.is_set()
    patch_callback.assert_called_once()
    assert (
        str(patch_callback.call_args_list[0][0][0])
        == f"Stopping the PDO thread due to the following exception: {error_msg} "
    )
    mc.capture.pdo.stop_pdos()
