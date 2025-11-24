import pytest
from ingenialink import CanBaudrate, CanDevice
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.dictionary import SubnodeType
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.register import RegAccess, RegDtype

from ingeniamotion.exceptions import IMError, IMRegisterNotExistError
from ingeniamotion.information import CommunicationType


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
def test_register_info(mc, alias, uid, axis):
    register = mc.info.register_info(uid, axis, alias)
    assert isinstance(register.dtype, RegDtype)
    assert isinstance(register.access, RegAccess)
    assert isinstance(register.range, tuple)


@pytest.mark.virtual
@pytest.mark.parametrize(
    "uid, axis, dtype",
    [
        ("CL_POS_FBK_VALUE", 1, RegDtype.S32),
        ("CL_VEL_SET_POINT_VALUE", 1, RegDtype.FLOAT),
        ("PROF_POS_OPTION_CODE", 1, RegDtype.U16),
        ("PROF_IP_CLEAR_DATA", 1, RegDtype.U16),
    ],
)
def test_register_type(mc, alias, uid, axis, dtype):
    register_dtype = mc.info.register_type(uid, axis, alias)
    assert register_dtype == dtype


@pytest.mark.virtual
@pytest.mark.parametrize(
    "uid, axis, access",
    [
        ("CL_POS_FBK_VALUE", 1, RegAccess.RO),
        ("CL_VEL_SET_POINT_VALUE", 1, RegAccess.RW),
        ("PROF_POS_OPTION_CODE", 1, RegAccess.RW),
        ("PROF_IP_CLEAR_DATA", 1, RegAccess.WO),
    ],
)
def test_register_access(mc, alias, uid, axis, access):
    register_access = mc.info.register_access(uid, axis, alias)
    assert register_access == access


@pytest.mark.virtual
@pytest.mark.parametrize(
    "uid, axis, expected_range",
    [
        ("CL_POS_FBK_VALUE", 1, (-2147483648, 2147483647)),
        ("CL_VEL_SET_POINT_VALUE", 1, (-3.4e38, 3.4e38)),
        ("PROF_POS_OPTION_CODE", 1, (0, 65535)),
        ("PROF_IP_CLEAR_DATA", 1, (0, 65535)),
    ],
)
def test_register_range(mc, alias, uid, axis, expected_range):
    register_range = mc.info.register_range(uid, axis, alias)
    assert tuple(register_range) == expected_range


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
def test_register_exists(mc, alias, uid, axis, exists):
    register_exists = mc.info.register_exists(uid, axis, alias)
    assert register_exists == exists


@pytest.mark.virtual
def test_get_product_name(mc, alias):
    expected_product_name = "VIRTUAL-DRIVE"

    product_name = mc.info.get_product_name(alias)

    assert product_name == expected_product_name


@pytest.mark.virtual
def test_get_ip(mc, alias):
    expected_ip = "127.0.0.1"

    ip = mc.info.get_ip(alias)

    assert ip == expected_ip


@pytest.mark.virtual
def test_get_name(mc, alias):
    expected_name = "Drive"

    name = mc.info.get_name(alias)

    assert name == expected_name


@pytest.mark.parametrize(
    "communication, expected_result, args",
    [
        (EthernetNetwork, CommunicationType.Ethernet, None),
        (EthercatNetwork, CommunicationType.Ethercat, "fake_interface_name"),
        (CanopenNetwork, CommunicationType.Canopen, CanDevice.PCAN),
    ],
)
@pytest.mark.virtual
def test_get_communication_type(mocker, mc, alias, communication, expected_result, args):
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)

    if communication != EthernetNetwork:
        mocker.patch.object(mc, "_get_network", return_value=communication(args))

    communication_type = mc.info.get_communication_type(alias)
    assert communication_type == expected_result


@pytest.mark.parametrize(
    "communication, expected_result, args",
    [
        (EthernetNetwork, "VIRTUAL-DRIVE - Drive (127.0.0.1)", None),
        (EthercatNetwork, "VIRTUAL-DRIVE - Drive", "fake_interface_name"),
        (CanopenNetwork, "VIRTUAL-DRIVE - Drive", CanDevice.PCAN),
    ],
)
@pytest.mark.virtual
def test_get_full_name(mocker, mc, alias, communication, expected_result, args):
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)

    if communication != EthernetNetwork:
        mocker.patch.object(mc, "_get_network", return_value=communication(args))
    full_name = mc.info.get_full_name(alias)
    assert full_name == expected_result


@pytest.mark.virtual
def test_get_subnodes(mc, alias):
    expected_subnodes = 2

    subnodes = mc.info.get_subnodes(alias)

    assert len(subnodes) == expected_subnodes
    assert subnodes[0] == SubnodeType.COMMUNICATION
    assert subnodes[1] == SubnodeType.MOTION


@pytest.mark.virtual
def test_get_categories(mc, alias):
    expected_number_categories = 19

    categories = mc.info.get_categories(alias)

    assert len(categories) == expected_number_categories


@pytest.mark.virtual
def test_get_dictionary_file_name(mc, alias):
    expected_dictionary_path = "virtual_drive_custom_dict.xdf"

    dictionary_file_name = mc.info.get_dictionary_file_name(alias)

    assert dictionary_file_name in expected_dictionary_path


@pytest.mark.virtual
def test_get_encoded_image_from_dictionary(mc, alias):
    encoded_image = mc.info.get_encoded_image_from_dictionary(alias)

    assert isinstance(encoded_image, str)


@pytest.mark.virtual
def test_register_info_exception(mc, alias):
    with pytest.raises(IMRegisterNotExistError):
        mc.info.register_info("non_existing_uid", 1, alias)


@pytest.mark.virtual
def test_get_product_name_none(mc, alias):
    drive = mc._get_drive(alias)
    drive.dictionary.part_number = None
    product_name = mc.info.get_product_name(alias)
    assert product_name is None


@pytest.mark.virtual
def test_get_node_id_exception(mc, alias):
    with pytest.raises(IMError):
        mc.info.get_node_id(alias)


@pytest.mark.virtual
def test_get_ip_exception(mocker, mc, alias):
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(IMError):
        mc.info.get_ip(alias)


@pytest.mark.virtual
def test_get_slave_id_exception(mc, alias):
    with pytest.raises(IMError):
        mc.info.get_slave_id(alias)


@pytest.mark.virtual
def test_get_baudrate_success(mc, alias, mocker):
    fake_device = CanDevice.PCAN
    fake_channel = 0
    fake_baudrate = CanBaudrate.Baudrate_1M
    fake_network = CanopenNetwork(fake_device, fake_channel, fake_baudrate)
    mocker.patch.object(mc, "_get_network", return_value=fake_network)

    test_baudrate = mc.info.get_baudrate(alias)

    assert fake_baudrate == test_baudrate


@pytest.mark.virtual
def test_get_baudrate_failed(mc, alias, mocker):
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(IMError, match=f"The servo {alias} is not a CANopen device."):
        _ = mc.info.get_baudrate(alias)
