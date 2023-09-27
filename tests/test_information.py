import pytest

from ingeniamotion.enums import REG_DTYPE, REG_ACCESS
from ingeniamotion.information import COMMUNICATION_TYPE


@pytest.mark.no_connection
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


@pytest.mark.no_connection
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


@pytest.mark.no_connection
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


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "uid, axis, range",
    [
        ("CL_POS_FBK_VALUE", 1, (-2147483648, 2147483647)),
        ("CL_VEL_SET_POINT_VALUE", 1, (-3.4e38, 3.4e38)),
        ("PROF_POS_OPTION_CODE", 1, (0, 65535)),
        ("PROF_IP_CLEAR_DATA", 1, (0, 65535)),
    ],
)
def test_register_range(motion_controller, uid, axis, range):
    mc, alias = motion_controller
    register_range = mc.info.register_range(uid, axis, alias)
    assert tuple(register_range) == range


@pytest.mark.no_connection
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


@pytest.mark.no_connection
def test_get_product_name(motion_controller, mocker):
    expected_product_name = "FAKE_PART_NUMBER"

    mc, alias = motion_controller
    product_name = mc.info.get_product_name(alias)

    assert product_name == expected_product_name


@pytest.mark.no_connection
def test_get_target(motion_controller):
    expected_target = "FAKE_TARGET"

    mc, alias = motion_controller
    target = mc.info.get_target(alias)

    assert target == expected_target


@pytest.mark.no_connection
def test_get_name(motion_controller):
    expected_name = "FAKE_NAME"

    mc, alias = motion_controller
    name = mc.info.get_name(alias)

    assert name == expected_name


@pytest.mark.no_connection
def test_get_communication_type(motion_controller):
    expected_communication_type = COMMUNICATION_TYPE.Ethernet

    mc, alias = motion_controller
    communication_type = mc.info.get_communication_type(alias)

    assert communication_type == expected_communication_type


@pytest.mark.no_connection
def test_get_full_name(motion_controller):
    expected_full_name = "FAKE_PART_NUMBER - FAKE_NAME (FAKE_TARGET)"

    mc, alias = motion_controller
    full_name = mc.info.get_full_name(alias)

    assert full_name == expected_full_name


@pytest.mark.no_connection
def test_get_subnodes(motion_controller):
    expected_subnodes = 5

    mc, alias = motion_controller
    subnodes = mc.info.get_subnodes(alias)

    assert subnodes == expected_subnodes


@pytest.mark.no_connection
def test_get_categories(motion_controller):
    expected_number_categories = 19

    mc, alias = motion_controller
    categories = mc.info.get_categories(alias)

    assert len(categories) == expected_number_categories


@pytest.mark.no_connection
def test_get_dictionary_file_name(motion_controller):
    expected_dictionary_path = "mock_eth.xdf"

    mc, alias = motion_controller
    dictionary_file_name = mc.info.get_dictionary_file_name(alias)

    assert dictionary_file_name in expected_dictionary_path


@pytest.mark.no_connection
def test_get_encoded_image_from_dictionary(motion_controller):
    expected_type_output = str

    mc, alias = motion_controller
    encoded_image = mc.info.get_encoded_image_from_dictionary(alias)

    assert type(encoded_image) == expected_type_output


@pytest.mark.no_connection
def test_get_drive_info_coco_moco(motion_controller):
    expected_product_codes = [12, 21]
    expected_revision_numbers = [123, 321]
    expected_firmware_versions = ["4.3.2", "2.3.4"]
    expected_serial_numbers = [3456, 6543]

    mc, alias = motion_controller
    prod_codes, rev_nums, fw_vers, ser_nums = mc.info.get_drive_info_coco_moco(alias)

    assert prod_codes == expected_product_codes
    assert rev_nums == expected_revision_numbers
    assert fw_vers == expected_firmware_versions
    assert ser_nums == expected_serial_numbers


@pytest.mark.no_connection
def test_get_drive_info(motion_controller):
    expected_prod_code = 21
    expected_rev_number = 321
    expected_fw_version = "_2.3.4"
    expected_serial_number = 6543

    mc, alias = motion_controller
    prod_code, rev_num, fw_ver, ser_num = mc.info.get_drive_info(alias)

    assert prod_code == expected_prod_code
    assert rev_num == expected_rev_number
    assert fw_ver == expected_fw_version
    assert ser_num == expected_serial_number


@pytest.mark.no_connection
def test_get_serial_number(motion_controller):
    expected_serial_number = 6543

    mc, alias = motion_controller
    serial_number = mc.info.get_serial_number(alias)

    assert serial_number == expected_serial_number


@pytest.mark.no_connection
def test_get_fw_version(motion_controller):
    expected_fw_version = "2.3.4"

    mc, alias = motion_controller
    firmware_version = mc.info.get_fw_version(alias)

    assert firmware_version == expected_fw_version
