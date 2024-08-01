import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.dictionary import SubnodeType
from ingenialink.register import REG_ACCESS, REG_DTYPE

from ingeniamotion.information import COMMUNICATION_TYPE
from ingeniamotion.exceptions import IMRegisterNotExist, IMException


@pytest.mark.virtual
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


@pytest.mark.virtual
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


@pytest.mark.virtual
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


@pytest.mark.virtual
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


@pytest.mark.virtual
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


@pytest.mark.virtual
def test_get_product_name(motion_controller, mocker):
    expected_product_name = "VIRTUAL-DRIVE"

    mc, alias = motion_controller
    product_name = mc.info.get_product_name(alias)

    assert product_name == expected_product_name


@pytest.mark.virtual
def test_get_ip(motion_controller):
    expected_ip = "127.0.0.1"

    mc, alias = motion_controller
    ip = mc.info.get_ip(alias)

    assert ip == expected_ip


@pytest.mark.virtual
def test_get_name(motion_controller):
    expected_name = "Drive"

    mc, alias = motion_controller
    name = mc.info.get_name(alias)

    assert name == expected_name


@pytest.mark.smoke
@pytest.mark.parametrize(
    "communication, expected_result, args",
    [
        (EthernetNetwork, COMMUNICATION_TYPE.Ethernet, None),
        (EthercatNetwork, COMMUNICATION_TYPE.Ethercat, "fake_interface_name"),
        (CanopenNetwork, COMMUNICATION_TYPE.Canopen, CAN_DEVICE.PCAN),
    ],
)
@pytest.mark.virtual
def test_get_communication_type(mocker, motion_controller, communication, expected_result, args):
    mc, alias = motion_controller

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)

    if communication != EthernetNetwork:
        mocker.patch.object(mc, "_get_network", return_value=communication(args))

    communication_type = mc.info.get_communication_type(alias)
    assert communication_type == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "communication, expected_result, args",
    [
        (EthernetNetwork, "VIRTUAL-DRIVE - Drive (127.0.0.1)", None),
        (EthercatNetwork, "VIRTUAL-DRIVE - Drive", "fake_interface_name"),
        (CanopenNetwork, "VIRTUAL-DRIVE - Drive", CAN_DEVICE.PCAN),
    ],
)
@pytest.mark.virtual
def test_get_full_name(mocker, motion_controller, communication, expected_result, args):
    mc, alias = motion_controller

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)

    if communication != EthernetNetwork:
        mocker.patch.object(mc, "_get_network", return_value=communication(args))
    full_name = mc.info.get_full_name(alias)
    assert full_name == expected_result


@pytest.mark.virtual
def test_get_subnodes(motion_controller):
    expected_subnodes = 2

    mc, alias = motion_controller
    subnodes = mc.info.get_subnodes(alias)

    assert len(subnodes) == expected_subnodes
    assert subnodes[0] == SubnodeType.COMMUNICATION
    assert subnodes[1] == SubnodeType.MOTION


@pytest.mark.virtual
def test_get_categories(motion_controller):
    expected_number_categories = 19

    mc, alias = motion_controller
    categories = mc.info.get_categories(alias)

    assert len(categories) == expected_number_categories


@pytest.mark.virtual
def test_get_dictionary_file_name(motion_controller):
    expected_dictionary_path = "virtual_drive.xdf"

    mc, alias = motion_controller
    dictionary_file_name = mc.info.get_dictionary_file_name(alias)

    assert dictionary_file_name in expected_dictionary_path


@pytest.mark.virtual
def test_get_encoded_image_from_dictionary(motion_controller):
    expected_type_output = str

    mc, alias = motion_controller
    encoded_image = mc.info.get_encoded_image_from_dictionary(alias)

    assert type(encoded_image) == expected_type_output


@pytest.mark.virtual
def test_register_info_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMRegisterNotExist):
        mc.info.register_info("non_existing_uid", 1, alias)


@pytest.mark.virtual
def test_get_product_name_none(motion_controller):
    mc, alias = motion_controller
    drive = mc._get_drive(alias)
    drive.dictionary.part_number = None
    product_name = mc.info.get_product_name(alias)
    assert product_name is None


@pytest.mark.virtual
def test_get_node_id_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMException):
        mc.info.get_node_id(alias)


@pytest.mark.virtual
def test_get_ip_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(IMException):
        mc.info.get_ip(alias)


@pytest.mark.virtual
def test_get_slave_id_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMException):
        mc.info.get_slave_id(alias)


@pytest.mark.virtual
def test_get_baudrate_success(motion_controller, mocker):
    mc, alias = motion_controller

    fake_device = CAN_DEVICE.PCAN
    fake_channel = 0
    fake_baudrate = CAN_BAUDRATE.Baudrate_1M
    fake_network = CanopenNetwork(fake_device, fake_channel, fake_baudrate)
    mocker.patch.object(mc, "_get_network", return_value=fake_network)

    test_baudrate = mc.info.get_baudrate(alias)

    assert fake_baudrate == test_baudrate


@pytest.mark.virtual
def test_get_baudrate_failed(motion_controller, mocker):
    mc, alias = motion_controller

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(IMException) as imexpeption_info:
        _ = mc.info.get_baudrate(alias)

    expected_message_error = "The servo test is not a CANopen device."
    assert expected_message_error == imexpeption_info.value.args[0]
