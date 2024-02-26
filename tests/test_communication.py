import os
import time
from collections import OrderedDict

import pytest
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.canopen.servo import CanopenServo
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILError
from ingenialink.network import SlaveInfo
from ingenialink.servo import SERVO_STATE

from ingeniamotion import MotionController
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE
from ingeniamotion.exceptions import IMException, IMRegisterNotExist, IMRegisterWrongAccess

TEST_ENSEMBLE_FW_FILE = "tests/resources/example_ensemble_fw.kfu"


@pytest.mark.virtual
def test_connect_servo_eoe(read_config):
    mc = MotionController()
    assert "eoe_test" not in mc.servos
    assert "eoe_test" not in mc.net
    mc.communication.connect_servo_eoe(
        read_config["ip"], read_config["dictionary"], alias="eoe_test"
    )
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "eoe_test" in mc.net and mc.net["eoe_test"] is not None


@pytest.mark.virtual
def test_connect_servo_eoe_no_dictionary_error(read_config):
    mc = MotionController()
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_eoe(read_config["ip"], "no_dictionary", alias="eoe_test")


@pytest.mark.virtual
def test_connect_servo_ethernet(read_config):
    mc = MotionController()
    assert "eoe_test" not in mc.servos
    assert "eoe_test" not in mc.net
    mc.communication.connect_servo_ethernet(
        read_config["ip"], read_config["dictionary"], alias="eoe_test"
    )
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "eoe_test" in mc.net and mc.net["eoe_test"] is not None


@pytest.mark.virtual
def test_connect_servo_ethernet_no_dictionary_error(read_config):
    mc = MotionController()
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ethernet(
            read_config["ip"], "no_dictionary", alias="eoe_test"
        )


@pytest.mark.smoke
@pytest.mark.eoe
@pytest.mark.parametrize(
    "coco_dict_path",
    [
        True,
        False,
    ],
)
def test_connect_servo_comkit_no_dictionary_error(coco_dict_path, read_config):
    mc = MotionController()
    if coco_dict_path:
        coco_dict_path = read_config["dictionary"]
        moco_dict_path = "no_dictionary"
    else:
        coco_dict_path = "no_dictionary"
        moco_dict_path = read_config["dictionary"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_comkit(
            read_config["ip"], coco_dict_path, moco_dict_path, alias="eoe_test"
        )


@pytest.mark.smoke
@pytest.mark.soem
def test_get_ifname_from_interface_ip(mocker):
    ip = type("IP", (object,), {"ip": "192.168.2.1", "is_IPv4": True})
    adapter = type(
        "Adapter", (object,), {"ips": [ip], "name": b"{192D1D2F-C684-467D-A637-EC07BD434A63}"}
    )
    mocker.patch("ifaddr.get_adapters", return_value=[adapter])
    mc = MotionController()
    ifname = mc.communication.get_ifname_from_interface_ip("192.168.2.1")
    assert ifname == "\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}"


@pytest.mark.skip(reason='This test enters in conflict with "disable_motor_fixture"')
@pytest.mark.smoke
@pytest.mark.canopen
def test_connect_servo_canopen(read_config):
    mc = MotionController()
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.net
    device = CAN_DEVICE(read_config["device"])
    baudrate = CAN_BAUDRATE(read_config["baudrate"])
    mc.communication.connect_servo_canopen(
        device,
        read_config["dictionary"],
        read_config["node_id"],
        baudrate,
        read_config["channel"],
        alias="canopen_test",
    )
    assert "canopen_test" in mc.servos and mc.servos["canopen_test"] is not None
    assert "canopen_test" in mc.net and mc.net["canopen_test"] is not None
    mc.net["canopen_test"].disconnect()


@pytest.mark.smoke
@pytest.mark.canopen
@pytest.mark.skip
def test_connect_servo_canopen_busy_drive_error(motion_controller, read_config):
    mc, alias = motion_controller
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.servo_net
    assert alias in mc.servos
    assert alias in mc.servo_net
    assert mc.servo_net[alias] in mc.net
    device = CAN_DEVICE(read_config["device"])
    baudrate = CAN_BAUDRATE(read_config["baudrate"])
    with pytest.raises(ILError):
        mc.communication.connect_servo_canopen(
            device,
            read_config["dictionary"],
            read_config["node_id"],
            baudrate,
            read_config["channel"],
            alias="canopen_test",
        )


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "uid, value",
    [
        ("CL_VOL_Q_SET_POINT", 0.34),
        ("CL_POS_SET_POINT_VALUE", -923),
        ("PROF_POS_OPTION_CODE", 1),
    ],
)
def test_get_register(motion_controller, uid, value):
    mc, alias = motion_controller
    drive = mc.servos[alias]
    drive.write(uid, value)
    test_value = mc.communication.get_register(uid, servo=alias)
    assert pytest.approx(test_value) == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_register_wrong_uid(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMRegisterNotExist):
        mc.communication.get_register("WRONG_UID", servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "uid, value",
    [
        ("CL_VOL_Q_SET_POINT", -234),
        ("CL_POS_SET_POINT_VALUE", 23),
        ("PROF_POS_OPTION_CODE", 54),
    ],
)
def test_set_register(motion_controller, uid, value):
    mc, alias = motion_controller
    drive = mc.servos[alias]
    mc.communication.set_register(uid, value, servo=alias)
    test_value = drive.read(uid)
    assert pytest.approx(test_value) == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_register_wrong_uid(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMRegisterNotExist):
        mc.communication.set_register("WRONG_UID", 2, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "uid, value, fail",
    [
        ("CL_VOL_Q_SET_POINT", -234, False),
        ("CL_VOL_Q_SET_POINT", "I'm not a number", True),
        ("CL_VOL_Q_SET_POINT", 234.4, False),
        ("CL_POS_SET_POINT_VALUE", 1245, False),
        ("CL_POS_SET_POINT_VALUE", -1245, False),
        ("CL_POS_SET_POINT_VALUE", 1245.5421, True),
        ("PROF_POS_OPTION_CODE", -54, True),
        ("PROF_POS_OPTION_CODE", 54, False),
        ("PROF_POS_OPTION_CODE", "54", True),
    ],
)
def test_set_register_wrong_value_type(motion_controller, uid, value, fail):
    mc, alias = motion_controller
    if fail:
        with pytest.raises(TypeError):
            mc.communication.set_register(uid, value, servo=alias)
    else:
        mc.communication.set_register(uid, value, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_register_wrong_access(motion_controller):
    mc, alias = motion_controller
    uid = "DRV_STATE_STATUS"
    value = 0
    with pytest.raises(IMRegisterWrongAccess):
        mc.communication.set_register(uid, value, servo=alias)


def dummy_callback(status, _, axis):
    pass


@pytest.mark.smoke
def test_subscribe_servo_status(mocker, motion_controller):
    mc, alias = motion_controller
    axis = 1
    patch_callback = mocker.patch("tests.test_communication.dummy_callback")
    mc.communication.subscribe_servo_status(patch_callback, alias)
    time.sleep(0.5)
    mc.motion.motor_enable(alias, axis)
    time.sleep(0.5)
    mc.motion.motor_disable(alias, axis)
    time.sleep(0.5)
    expected_status = [SERVO_STATE.RDY, SERVO_STATE.ENABLED, SERVO_STATE.DISABLED]
    for index, call in enumerate(patch_callback.call_args_list):
        assert call[0][0] == expected_status[index]
        assert call[0][2] == axis


@pytest.mark.virtual
def test_load_firmware_canopen_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.communication.load_firmware_canopen("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_boot_mode_and_load_firmware_ethernet_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(ValueError):
        mc.communication.boot_mode_and_load_firmware_ethernet("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_load_firmware_moco_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch.object(mc, "_get_network", return_value=EthercatNetwork("fake_interface_name"))
    with pytest.raises(ValueError):
        mc.communication.load_firmware_moco("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_connect_servo_virtual():
    mc = MotionController()
    mc.communication.connect_servo_virtual()
    assert mc.communication._Communication__virtual_drive is not None
    mc.communication.disconnect()
    assert mc.communication._Communication__virtual_drive is None


@pytest.mark.virtual
def test_connect_servo_virtual_custom_dictionary(read_config):
    mc = MotionController()
    mc.communication.connect_servo_virtual(dict_path=read_config["dictionary"])
    assert mc.communication._Communication__virtual_drive is not None
    mc.communication.disconnect()
    assert mc.communication._Communication__virtual_drive is None


@pytest.mark.virtual
def test_unzip_ensemble_fw_file():
    mc = MotionController()
    mapping = mc.communication._Communication__unzip_ensemble_fw_file(TEST_ENSEMBLE_FW_FILE)
    path = os.path.abspath("ensemble_temp")
    assert mapping == {
        0: (os.path.join(path, "cap-net-1-e_2.4.0.lfu"), 123456, 4660),
        1: (os.path.join(path, "cap-net-2-e_2.4.0.lfu"), 123456, 16781876),
    }


@pytest.mark.virtual
def test__check_ensemble():
    mc = MotionController()
    mapping = mc.communication._Communication__unzip_ensemble_fw_file(TEST_ENSEMBLE_FW_FILE)
    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(product_code, 16781876),
            4: SlaveInfo(product_code, 4660),
            5: SlaveInfo(product_code, 16781876),
            7: SlaveInfo(654321, 1236),
        }
    )
    for slave_id in [1, 2]:
        assert mc.communication._Communication__check_ensemble(slaves, slave_id, mapping) == 1

    for slave_id in [4, 5]:
        assert mc.communication._Communication__check_ensemble(slaves, slave_id, mapping) == 4


@pytest.mark.virtual
def test__check_ensemble_wrong():
    mc = MotionController()
    mapping = mc.communication._Communication__unzip_ensemble_fw_file(TEST_ENSEMBLE_FW_FILE)
    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(product_code, 16781876),
            3: SlaveInfo(654321, 1236),
        }
    )
    with pytest.raises(IMException) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 4, mapping)
    assert str(exc_info.value) == "Slave 4 was not detected."

    with pytest.raises(IMException) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 3, mapping)
    assert str(exc_info.value) == "The selected drive is not part of the ensemble."

    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(654321, 16781876),
        }
    )
    with pytest.raises(IMException) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 1, mapping)
    assert (
        str(exc_info.value)
        == "Wrong ensemble. The slave 2 has wrong product code or revision number."
    )

    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 16781876),
            2: SlaveInfo(product_code, 4660),
        }
    )
    with pytest.raises(IMException) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 2, mapping)
    assert (
        str(exc_info.value)
        == "Wrong ensemble. The slave 2 has wrong product code or revision number."
    )


@pytest.mark.virtual
@pytest.mark.parametrize("revision_number,expected_id_offset", [(4660, 0), (16781876, 1)])
def test_check_slave_in_ensemble(revision_number, expected_id_offset):
    mc = MotionController()
    mapping = mc.communication._Communication__unzip_ensemble_fw_file(TEST_ENSEMBLE_FW_FILE)
    product_code = 123456
    slave_info = SlaveInfo(product_code, revision_number)

    slave_id_offset = mc.communication._Communication__check_slave_in_ensemble(slave_info, mapping)

    assert slave_id_offset == expected_id_offset


@pytest.mark.virtual
def test_check_slave_in_ensemble_drive_not_in_ensemble():
    mc = MotionController()
    mapping = mc.communication._Communication__unzip_ensemble_fw_file(TEST_ENSEMBLE_FW_FILE)
    product_code = 654321
    revision_number = 4660
    slave_info = SlaveInfo(product_code, revision_number)

    with pytest.raises(IMException) as exc_info:
        mc.communication._Communication__check_slave_in_ensemble(slave_info, mapping)
    assert str(exc_info.value) == "The selected drive is not part of the ensemble."


@pytest.mark.virtual
def test_load_ensemble_fw_ecat(mocker):
    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(product_code, 16781876),
            3: SlaveInfo(product_code, 4660),
            4: SlaveInfo(product_code, 16781876),
            5: SlaveInfo(654321, 1236),
        }
    )
    temp_path = os.path.abspath("ensemble_temp")
    fw_file1 = os.path.join(temp_path, "cap-net-1-e_2.4.0.lfu")
    fw_file2 = os.path.join(temp_path, "cap-net-2-e_2.4.0.lfu")
    mc = MotionController()
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.scan_slaves_info", return_value=slaves
    )
    for slave in [1, 2]:
        patch_fw_callback = mocker.patch(
            "ingenialink.ethercat.network.EthercatNetwork.load_firmware"
        )
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=slave)
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0] == (fw_file1, 1)
        assert patch_fw_callback.call_args_list[1][0] == (fw_file2, 2)

    for slave in [3, 4]:
        patch_fw_callback = mocker.patch(
            "ingenialink.ethercat.network.EthercatNetwork.load_firmware"
        )
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=slave)
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0] == (fw_file1, 3)
        assert patch_fw_callback.call_args_list[1][0] == (fw_file2, 4)

    with pytest.raises(IMException) as exc_info:
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=5)
    assert str(exc_info.value) == "The selected drive is not part of the ensemble."


@pytest.mark.virtual
def test_load_ensemble_fw_canopen(mocker):
    class MockDictionary:
        def __init__(self) -> None:
            self.path = "path_to_dictionary"

    class MockCanopenServo(CanopenServo):
        def __init__(self, node_id) -> None:
            self.target = node_id
            self._dictionary = MockDictionary()

    servos = {}
    for node_id in range(1, 6):
        servos[str(node_id)] = MockCanopenServo(node_id)

    mc = MotionController()
    net = CanopenNetwork(CAN_DEVICE.KVASER)
    net.servos = list(servos.values())
    mocker.patch("ingeniamotion.motion_controller.MotionController._get_network", return_value=net)
    mocker.patch("ingenialink.canopen.network.CanopenNetwork.connect_to_slave")
    mocker.patch("ingenialink.canopen.network.CanopenNetwork.disconnect_from_slave")
    mc._get_drive = lambda x: servos[x]
    mc.servos = servos

    product_code = 123456
    slaves_info = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(product_code, 16781876),
            3: SlaveInfo(product_code, 4660),
            4: SlaveInfo(product_code, 16781876),
            5: SlaveInfo(654321, 1236),
        }
    )
    temp_path = os.path.abspath("ensemble_temp")
    fw_file1 = os.path.join(temp_path, "cap-net-1-e_2.4.0.lfu")
    fw_file2 = os.path.join(temp_path, "cap-net-2-e_2.4.0.lfu")
    mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.scan_slaves_info", return_value=slaves_info
    )
    for slave in [1, 2]:
        patch_fw_callback = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo=str(slave))
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][:2] == (1, fw_file1)
        assert patch_fw_callback.call_args_list[1][0][:2] == (2, fw_file2)

    for slave in [3, 4]:
        patch_fw_callback = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo=str(slave))
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][:2] == (3, fw_file1)
        assert patch_fw_callback.call_args_list[1][0][:2] == (4, fw_file2)

    with pytest.raises(IMException) as exc_info:
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo="5")
    assert str(exc_info.value) == "The selected drive is not part of the ensemble."
