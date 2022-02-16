import pytest

from ingeniamotion.enums import REG_DTYPE, REG_ACCESS


@pytest.mark.parametrize("uid, axis, dtype, access, reg_range", [
    ("CL_POS_FBK_VALUE", 1, REG_DTYPE.S32, REG_ACCESS.RO, (-2147483648, 2147483647)),
    ("CL_VEL_SET_POINT_VALUE", 1, REG_DTYPE.FLOAT, REG_ACCESS.RW,
     (-2147483648, 2147483647)),
    ("PROF_POS_OPTION_CODE", 1, REG_DTYPE.U16, REG_ACCESS.RW, (0, 65535)),
    ("PROF_IP_CLEAR_DATA", 1, REG_DTYPE.U16, REG_ACCESS.WO, (0, 65535))
])
def test_register_info(motion_controller, uid, axis, dtype, access, reg_range):
    mc, alias = motion_controller
    register = mc.info.register_info(uid, axis, alias)
    assert register.dtype == dtype
    assert register.access == access
    assert register.range == reg_range


@pytest.mark.parametrize("uid, axis, dtype", [
    ("CL_POS_FBK_VALUE", 1, REG_DTYPE.S32),
    ("CL_VEL_SET_POINT_VALUE", 1, REG_DTYPE.FLOAT),
    ("PROF_POS_OPTION_CODE", 1, REG_DTYPE.U16),
    ("PROF_IP_CLEAR_DATA", 1, REG_DTYPE.U16)
])
def test_register_type(motion_controller, uid, axis, dtype):
    mc, alias = motion_controller
    register_dtype = mc.info.register_type(uid, axis, alias)
    assert register_dtype == dtype


@pytest.mark.parametrize("uid, axis, access", [
    ("CL_POS_FBK_VALUE", 1, REG_ACCESS.RO),
    ("CL_VEL_SET_POINT_VALUE", 1, REG_ACCESS.RW),
    ("PROF_POS_OPTION_CODE", 1, REG_ACCESS.RW),
    ("PROF_IP_CLEAR_DATA", 1, REG_ACCESS.WO)
])
def test_register_access(motion_controller, uid, axis, access):
    mc, alias = motion_controller
    register_access = mc.info.register_access(uid, axis, alias)
    assert register_access == access


@pytest.mark.parametrize("uid, axis, range", [
    ("CL_POS_FBK_VALUE", 1, (-2147483648, 2147483647)),
    ("CL_VEL_SET_POINT_VALUE", 1, (-2147483648, 2147483647)),
    ("PROF_POS_OPTION_CODE", 1, (0, 65535)),
    ("PROF_IP_CLEAR_DATA", 1, (0, 65535))
])
def test_register_range(motion_controller, uid, axis, range):
    mc, alias = motion_controller
    register_range = mc.info.register_range(uid, axis, alias)
    assert tuple(register_range) == range


@pytest.mark.parametrize("uid, axis, exists", [
    ("CL_POS_FBK_VALUE", 1, True),
    ("CL_VEL_SET_POINT_VALUE", 1, True),
    ("PROF_POS_OPTION_CODE", 1, True),
    ("PROF_IP_CLEAR_DATA", 1, True),
    ("DRV_AXIS_NUMBER", 0, True),
    ("WRONG_UID", 1, False),
    ("drv_axis_number", 0, False)
])
def test_register_exists(motion_controller, uid, axis, exists):
    mc, alias = motion_controller
    register_exists = mc.info.register_exists(uid, axis, alias)
    assert register_exists == exists
