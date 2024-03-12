import json
import random
import time

import pytest
from ingenialink.pdo import RPDOMap, TPDOMap, RPDOMapItem, TPDOMapItem
from ingenialink.ethercat.network import EthercatNetwork
from packaging import version

from ingeniamotion.enums import OperationMode, COMMUNICATION_TYPE
from ingeniamotion.exceptions import IMException


@pytest.fixture
def connect_to_all_slaves(motion_controller, pytestconfig):
    mc, alias = motion_controller
    aliases = [alias]
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "soem":
        raise AssertionError("Fixture only available for the soem protocol.")
    config = "tests/config.json"
    with open(config, "r") as fp:
        contents = json.load(fp)
    protocol_contents = contents[protocol]
    connected_slave_id = mc.servos[alias].slave_id
    for slave_content in protocol_contents:
        if slave_content["slave"] == connected_slave_id:
            continue
        alias = f"test{slave_content['slave']}"
        aliases.append(alias)
        mc.communication.connect_servo_ethercat_interface_index(
            slave_content["index"],
            slave_content["slave"],
            slave_content["dictionary"],
            alias,
        )
    yield mc, aliases
    aliases.pop(0)
    for alias in aliases:
        mc.communication.disconnect(alias)


@pytest.mark.soem
def test_create_rpdo_item(motion_controller):
    mc, alias = motion_controller
    position_set_point_initial_value = 100
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=alias, value=position_set_point_initial_value
    )
    assert isinstance(position_set_point, RPDOMapItem)
    assert position_set_point.value == position_set_point_initial_value


@pytest.mark.soem
def test_create_tpdo_item(motion_controller):
    mc, alias = motion_controller
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
    assert isinstance(actual_position, TPDOMapItem)


@pytest.mark.soem
def test_create_rpdo_item_no_initial_value(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(AttributeError):
        mc.capture.pdo.create_pdo_item("CL_POS_SET_POINT_VALUE", servo=alias)


@pytest.mark.soem
def test_create_empty_rpdo_map(motion_controller):
    mc, alias = motion_controller
    rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 0


@pytest.mark.soem
def test_create_empty_tpdo_map(motion_controller):
    mc, alias = motion_controller
    tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 0


@pytest.mark.soem
def test_create_pdo_maps_single_item(motion_controller):
    mc, alias = motion_controller
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
def test_create_pdo_maps_list_items(motion_controller):
    mc, alias = motion_controller
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
def test_add_pdo_item_to_map(motion_controller, register, value, pdo_type):
    mc, alias = motion_controller
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
def test_add_pdo_item_to_map_exceptions(motion_controller, register, value, pdo_type):
    mc, alias = motion_controller
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
def test_set_pdo_maps_to_slave_exception(motion_controller, rpdo_maps, tpdo_maps):
    mc, alias = motion_controller
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
def test_pdos_refresh_rate(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos(COMMUNICATION_TYPE.Ethercat, 5)


@pytest.mark.soem
def test_start_pdos(connect_to_all_slaves):
    mc, aliases = connect_to_all_slaves
    pdo_map_items = {}
    initial_operation_modes = {}
    rpdo_values = {}
    tpdo_values = {}
    for alias in aliases:
        rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
        tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
        initial_operation_mode = mc.motion.get_operation_mode(servo=alias)
        operation_mode = mc.capture.pdo.create_pdo_item(
            "DRV_OP_CMD", servo=alias, value=initial_operation_mode.value
        )
        actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
        mc.capture.pdo.add_pdo_item_to_map(operation_mode, rpdo_map)
        mc.capture.pdo.add_pdo_item_to_map(actual_position, tpdo_map)
        mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=alias)
        pdo_map_items[alias] = (operation_mode, actual_position)
        random_op_mode = random.choice(
            [op_mode for op_mode in OperationMode if op_mode != initial_operation_mode]
        )
        initial_operation_modes[alias] = initial_operation_mode
        rpdo_values[alias] = random_op_mode

    def send_callback():
        for alias in aliases:
            rpdo_map_item, _ = pdo_map_items[alias]
            rpdo_map_item.value = rpdo_values[alias].value

    def receive_callback():
        for alias in aliases:
            _, tpdo_map_item = pdo_map_items[alias]
            tpdo_values[alias] = tpdo_map_item.value

    mc.capture.pdo.subscribe_to_send_process_data(send_callback)
    mc.capture.pdo.subscribe_to_receive_process_data(receive_callback)
    refresh_rate = 0.5
    mc.capture.pdo.start_pdos(refresh_rate=refresh_rate)
    time.sleep(2 * refresh_rate)
    mc.capture.pdo.stop_pdos()
    for alias in aliases:
        # Check that RPDO are being sent
        assert rpdo_values[alias] == mc.motion.get_operation_mode(servo=alias)
        # Check that TPDO are being received
        assert pytest.approx(tpdo_values[alias], abs=2) == mc.motion.get_actual_position(
            servo=alias
        )
        # Restore the initial operation mode
        mc.motion.set_operation_mode(initial_operation_modes[alias], servo=alias)


@pytest.mark.soem
def test_stop_pdos_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMException):
        mc.capture.pdo.stop_pdos()


@pytest.mark.soem
def test_start_pdos_not_implemented_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(NotImplementedError):
        mc.capture.pdo.start_pdos(COMMUNICATION_TYPE.Canopen)


@pytest.mark.soem
def test_start_pdos_wrong_network_type_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos("ethernet")


@pytest.mark.soem
def test_start_pdos_number_of_network_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mock_net = {"ifname1": EthercatNetwork("ifname1"), "ifname2": EthercatNetwork("ifname2")}
    mocker.patch.object(mc, "_MotionController__net", mock_net)
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos()
    with pytest.raises(IMException):
        mc.capture.pdo.start_pdos(COMMUNICATION_TYPE.Ethercat)


def skip_if_pdo_padding_is_not_available(mc, alias):
    pdo_poller_fw_version = "2.5.0"
    firmware_version = mc.configuration.get_fw_version(alias, 1)
    if version.parse(firmware_version) < version.parse(pdo_poller_fw_version):
        pytest.skip(
            f"PDO poller is available for firmware version {pdo_poller_fw_version} or higher. "
            f"Firmware version found: {firmware_version}"
        )


@pytest.mark.soem
def test_create_poller(motion_controller):
    mc, alias = motion_controller
    skip_if_pdo_padding_is_not_available(mc, alias)
    registers = [{"name": "CL_POS_FBK_VALUE", "axis": 1}, {"name": "CL_VEL_FBK_VALUE", "axis": 1}]
    sampling_time = 0.25
    sleep_time = 1
    poller = mc.capture.pdo.create_poller(registers, alias, sampling_time)
    time.sleep(sleep_time)
    poller.stop()
    timestamps, data = poller.data
    channel_0_data, channel_1_data = data.values()
    assert len(channel_0_data) == sleep_time / sampling_time
    assert len(channel_0_data) == len(channel_1_data)
    assert len(data) == len(registers)
    assert len(timestamps) == len(channel_0_data)
