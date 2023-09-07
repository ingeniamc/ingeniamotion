import pytest

from ingeniamotion.enums import REG_DTYPE, REG_ACCESS
from tests.conftest import PROTOCOL


@pytest.mark.parametrize(
    "uid, axis",
    [
        ("CL_POS_FBK_VALUE", 1),
        ("CL_VEL_SET_POINT_VALUE", 1),
        ("PROF_POS_OPTION_CODE", 1),
        ("PROF_IP_CLEAR_DATA", 1),
    ],
)
def test_register_info(motion_controller, uid, axis):
    mc, alias = motion_controller
    register = mc.info.register_info(uid, axis, alias)
    assert isinstance(register.dtype, REG_DTYPE)
    assert isinstance(register.access, REG_ACCESS)
    assert isinstance(register.range, tuple)


@pytest.mark.parametrize(
    "uid, axis, dtype",
    [
        ("CL_POS_FBK_VALUE", 1, REG_DTYPE.S32),
        ("CL_VEL_SET_POINT_VALUE", 1, REG_DTYPE.FLOAT),
        ("PROF_POS_OPTION_CODE", 1, REG_DTYPE.U16),
        ("PROF_IP_CLEAR_DATA", 1, REG_DTYPE.U16),
    ],
)
def test_register_type(motion_controller, uid, axis, dtype):
    mc, alias = motion_controller
    register_dtype = mc.info.register_type(uid, axis, alias)
    assert register_dtype == dtype


@pytest.mark.parametrize(
    "uid, axis, access",
    [
        ("CL_POS_FBK_VALUE", 1, REG_ACCESS.RO),
        ("CL_VEL_SET_POINT_VALUE", 1, REG_ACCESS.RW),
        ("PROF_POS_OPTION_CODE", 1, REG_ACCESS.RW),
        ("PROF_IP_CLEAR_DATA", 1, REG_ACCESS.WO),
    ],
)
def test_register_access(motion_controller, uid, axis, access):
    mc, alias = motion_controller
    register_access = mc.info.register_access(uid, axis, alias)
    assert register_access == access


@pytest.mark.canopen
@pytest.mark.eoe
@pytest.mark.parametrize(
    "uid, axis, range",
    [
        ("CL_POS_FBK_VALUE", 1, (-2147483648, 2147483647)),
        ("CL_VEL_SET_POINT_VALUE", 1, (-2147483648, 2147483647)),
        ("PROF_POS_OPTION_CODE", 1, (0, 65535)),
        ("PROF_IP_CLEAR_DATA", 1, (0, 65535)),
    ],
)
def test_register_range(motion_controller, uid, axis, range):
    mc, alias = motion_controller
    register_range = mc.info.register_range(uid, axis, alias)
    assert tuple(register_range) == range


@pytest.mark.parametrize(
    "uid, axis, exists",
    [
        ("CL_POS_FBK_VALUE", 1, True),
        ("CL_VEL_SET_POINT_VALUE", 1, True),
        ("PROF_POS_OPTION_CODE", 1, True),
        ("PROF_IP_CLEAR_DATA", 1, True),
        ("DRV_AXIS_NUMBER", 0, True),
        ("WRONG_UID", 1, False),
        ("drv_axis_number", 0, False),
    ],
)
def test_register_exists(motion_controller, uid, axis, exists):
    mc, alias = motion_controller
    register_exists = mc.info.register_exists(uid, axis, alias)
    assert register_exists == exists


def test_get_product_name(motion_controller, config):
    protocol = config.getoption("--protocol")
    slave = config.getoption("--slave")
    product_names_slave_0 = {PROTOCOL.CANOPEN: "EVE-XCR-C", PROTOCOL.EOE: "EVE-XCR-C", PROTOCOL.SOEM: "EVE-XCR-E"}
    product_names_slave_1 = {PROTOCOL.CANOPEN: "CAP-XCR-C", PROTOCOL.EOE: "CAP-XCR-C", PROTOCOL.SOEM: "CAP-XCR-E"}
    product_names_options = {"0": product_names_slave_0, "1": product_names_slave_1}
    expected_product_name = product_names_options[slave][protocol]

    mc, alias = motion_controller
    product_name = mc.info.get_product_name(alias)

    assert product_name == expected_product_name

def test_get_target(motion_controller, config):
    protocol = config.getoption("--protocol")

    if protocol == PROTOCOL.CANOPEN:
        expected_target = config["node_id"]
    else:
        expected_target = config["ip"]

    mc, alias = motion_controller
    target = mc.info.get_target(alias)

    assert target == expected_target

def test_get_name(motion_controller):
    expected_name = "Drive"

    mc, alias = motion_controller
    name = mc.info.get_name(alias)

    assert name == expected_name

def test_get_communication_type(motion_controller, config):
    protocol = config.getoption("--protocol")
    communication_type_options = {PROTOCOL.CANOPEN: "CANopen", PROTOCOL.EOE: "Ethernet", PROTOCOL.SOEM: "EtherCAT"}
    expected_communication_type = communication_type_options[protocol]

    mc, alias = motion_controller
    communication_type = mc.info.get_communication_type(alias)

    assert communication_type == expected_communication_type

def test_get_full_name(motion_controller, config):
    protocol = config.getoption("--protocol")
    slave = config.getoption("--slave")

    if protocol == PROTOCOL.EOE:
        target = config['ip']
    else:
        target = ""
    canopen_full_names = ["EVE-XCR-C - Drive", "CAP-XCR-C - Drive"]
    eoe_full_names = [f"EVE-XCR-C - Drive ({target})", f"CAP-XCR-C - Drive ({target})"]
    soem_full_names = ["EVE-XCR-E - Drive", "CAP-XCR-E - Drive"]
    full_names_options = {PROTOCOL.CANOPEN: canopen_full_names, PROTOCOL.EOE: eoe_full_names, PROTOCOL.SOEM: soem_full_names}
    expected_full_name = full_names_options[protocol][slave]

    mc, alias = motion_controller
    full_name = mc.info.get_full_name(alias)

    assert full_name == expected_full_name
