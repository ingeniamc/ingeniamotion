import random
import time

import pytest

from ingenialink.pdo import RPDOMap, TPDOMap, RPDOMapItem, TPDOMapItem
from ingeniamotion.enums import OperationMode
from ingeniamotion.exceptions import IMException


def test_create_rpdo_item(motion_controller):
    mc, alias = motion_controller
    position_set_point_initial_value = 100
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=alias, value=position_set_point_initial_value
    )
    assert isinstance(position_set_point, RPDOMapItem)
    assert position_set_point.value == position_set_point_initial_value


def test_create_tpdo_item(motion_controller):
    mc, alias = motion_controller
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
    assert isinstance(actual_position, TPDOMapItem)


def test_create_rpdo_item_no_initial_value(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(AttributeError):
        mc.capture.pdo.create_pdo_item("CL_POS_SET_POINT_VALUE", servo=alias)


def test_create_empty_rpdo_map(motion_controller):
    mc, alias = motion_controller
    rpdo_map = mc.capture.pdo.create_empty_rpdo_map()
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 0


def test_create_empty_tpdo_map(motion_controller):
    mc, alias = motion_controller
    tpdo_map = mc.capture.pdo.create_empty_tpdo_map()
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 0


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


def test_start_pdos_refresh_rate(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.capture.pdo.start_pdos("interface_name", 5)


def test_start_pdos(motion_controller):
    mc, alias = motion_controller
    interface_name = mc.servo_net[alias]
    initial_operation_mode = mc.motion.get_operation_mode(servo=alias)
    initial_position = mc.motion.get_actual_position(servo=alias)
    op_mode_value = random.choice(
        [op_mode.value for op_mode in OperationMode if op_mode != initial_operation_mode]
    )
    operation_mode = mc.capture.pdo.create_pdo_item("DRV_OP_CMD", servo=alias, value=op_mode_value)
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE", servo=alias)
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps(operation_mode, actual_position)
    mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=alias)
    mc.capture.pdo.start_pdos(interface_name)
    time.sleep(1)
    # Check that TPDO are being received
    assert actual_position.value == initial_position
    # Check that RPDO are being sent
    assert operation_mode.value != initial_operation_mode
    # Try to start the PDO thread once is active
    with pytest.raises(IMException):
        mc.capture.pdo.start_pdos(interface_name)
    # Restore inital operation mode
    mc.motion.set_operation_mode(initial_operation_mode, servo=alias)


def test_stop_pdos_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMException):
        mc.capture.pdo.stop_pdos()
