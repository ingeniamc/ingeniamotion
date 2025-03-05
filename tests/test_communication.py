import os
import platform
import re
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass

import pytest
from ingenialink import CanBaudrate, CanDevice
from ingenialink.canopen.network import CanopenNetwork
from ingenialink.canopen.servo import CanopenServo
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.exceptions import ILError
from ingenialink.network import SlaveInfo
from ingenialink.servo import ServoState

import ingeniamotion
from ingeniamotion import MotionController
from ingeniamotion.exceptions import (
    IMFirmwareLoadError,
    IMRegisterNotExistError,
    IMRegisterWrongAccessError,
)

from .setups.descriptors import DriveCanOpenSetup, DriveEcatSetup, EthernetSetup, Setup

TEST_ENSEMBLE_FW_FILE = "tests/resources/example_ensemble_fw.zfu"


class RegisterUpdateTest:
    def __init__(self):
        self.call_count = 0
        self.alias = None
        self.servo = None
        self.register = None
        self.value = None

    def register_update_test(self, alias, servo, register, value):
        self.call_count += 1
        self.alias = alias
        self.servo = servo
        self.register = register
        self.value = value


class EmcyTest:
    def __init__(self):
        self.messages = []

    def emcy_callback(self, alias, emcy_msg):
        self.messages.append((alias, emcy_msg))


@pytest.mark.smoke
@pytest.mark.canopen
@pytest.mark.ethernet
def test_get_network_adapters(mocker, tests_setup: Setup):
    """Tests networks adapters with Windows platform."""
    is_windows = platform.system() != "Windows"
    if not isinstance(tests_setup, DriveEcatSetup):
        pytest.skip(f"Skipping because test setup is {type(tests_setup)}")

    match = re.search(r"\{[^}]*\}", tests_setup.ifname)
    expected_adapter_address = match.group(0) if match else None
    assert expected_adapter_address is not None

    get_adapters_addresses_spy = (
        None
        if not is_windows
        else mocker.spy("ingenialink.get_adapters_addresses.get_adapters_addresses")
    )

    mc = MotionController()
    if get_adapters_addresses_spy is not None:
        assert get_adapters_addresses_spy.call_count == 0
    adapters = mc.communication.get_network_adapters()
    if get_adapters_addresses_spy is not None:
        assert get_adapters_addresses_spy.call_count == 1

    expected_adapter_address_found = False
    for interface_guid in adapters.values():
        if interface_guid == expected_adapter_address:
            expected_adapter_address_found = True
            break
    assert expected_adapter_address_found is True


@pytest.mark.virtual
def test_connect_servo_eoe(tests_setup: EthernetSetup):
    mc = MotionController()
    assert "ethernet_test" not in mc.servos
    assert "ethernet_test" not in mc.net
    mc.communication.connect_servo_eoe(
        tests_setup.ip, tests_setup.dictionary, alias="ethernet_test"
    )
    assert "ethernet_test" in mc.servos and mc.servos["ethernet_test"] is not None
    assert "ethernet_test" in mc.net and mc.net["ethernet_test"] is not None


@pytest.mark.virtual
def test_connect_servo_eoe_no_dictionary_error(tests_setup: EthernetSetup):
    mc = MotionController()
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_eoe(tests_setup.ip, "no_dictionary", alias="ethernet_test")


@pytest.mark.virtual
def test_connect_servo_ethernet(tests_setup: EthernetSetup):
    mc = MotionController()
    assert "ethernet_test" not in mc.servos
    assert "ethernet_test" not in mc.net
    mc.communication.connect_servo_ethernet(
        tests_setup.ip, tests_setup.dictionary, alias="ethernet_test"
    )
    assert "ethernet_test" in mc.servos and mc.servos["ethernet_test"] is not None
    assert "ethernet_test" in mc.net and mc.net["ethernet_test"] is not None


@pytest.mark.virtual
def test_connect_servo_ethernet_no_dictionary_error(tests_setup: EthernetSetup):
    mc = MotionController()
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ethernet(
            tests_setup.ip, "no_dictionary", alias="ethernet_test"
        )


@pytest.mark.smoke
@pytest.mark.ethernet
@pytest.mark.parametrize(
    "coco_dict_path",
    [
        True,
        False,
    ],
)
def test_connect_servo_comkit_no_dictionary_error(coco_dict_path, tests_setup: EthernetSetup):
    mc = MotionController()
    if coco_dict_path:
        coco_dict_path = tests_setup.dictionary
        moco_dict_path = "no_dictionary"
    else:
        coco_dict_path = "no_dictionary"
        moco_dict_path = tests_setup.dictionary
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_comkit(
            tests_setup.ip, coco_dict_path, moco_dict_path, alias="ethernet_test"
        )


@pytest.mark.smoke
@pytest.mark.virtual
def test_get_ifname_from_interface_ip(mocker):
    class MockAdapter:
        @dataclass
        class IP:
            ip = "192.168.2.1"
            is_IPv4 = True  # noqa: N815

        def __init__(self, interface_name):
            self.name = interface_name
            self.nice_name = interface_name
            self.ips = [self.IP()]
            self.index = 1

    name = "eth0" if platform.system() == "Linux" else b"{192D1D2F-C684-467D-A637-EC07BD434A63}"
    mock_adapter = MockAdapter(name)
    mocker.patch("ifaddr.get_adapters", return_value=[mock_adapter])
    mc = MotionController()
    ifname = mc.communication.get_ifname_from_interface_ip("192.168.2.1")
    if platform.system() == "Windows":
        assert ifname == "\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}"
    else:
        assert ifname == name


@pytest.mark.smoke
@pytest.mark.virtual
def test_get_ifname_by_index():
    mc = MotionController()
    interface_name_list = mc.communication.get_interface_name_list()
    assert len(interface_name_list) > 0
    for index, interface_name in enumerate(interface_name_list):
        ifname = mc.communication.get_ifname_by_index(index)
        assert isinstance(ifname, str)
        if platform.system() == "Linux":
            assert ifname == interface_name


@pytest.mark.skip(reason='This test enters in conflict with "disable_motor_fixture"')
@pytest.mark.smoke
@pytest.mark.canopen
def test_connect_servo_canopen(tests_setup: DriveCanOpenSetup):
    mc = MotionController()
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.net
    device = CanDevice(tests_setup.device)
    baudrate = CanBaudrate(tests_setup.baudrate)
    mc.communication.connect_servo_canopen(
        device,
        tests_setup.dictionary,
        tests_setup.node_id,
        baudrate,
        tests_setup.channel,
        alias="canopen_test",
    )
    assert "canopen_test" in mc.servos and mc.servos["canopen_test"] is not None
    assert "canopen_test" in mc.net and mc.net["canopen_test"] is not None
    mc.net["canopen_test"].disconnect()


@pytest.mark.smoke
@pytest.mark.canopen
@pytest.mark.skip
def test_connect_servo_canopen_busy_drive_error(motion_controller, tests_setup: DriveCanOpenSetup):
    mc, alias, environment = motion_controller
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.servo_net
    assert alias in mc.servos
    assert alias in mc.servo_net
    assert mc.servo_net[alias] in mc.net
    device = CanDevice(tests_setup.device)
    baudrate = CanBaudrate(tests_setup.baudrate)
    with pytest.raises(ILError):
        mc.communication.connect_servo_canopen(
            device,
            tests_setup.dictionary,
            tests_setup.node_id,
            baudrate,
            tests_setup.channel,
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
    mc, alias, environment = motion_controller
    drive = mc.servos[alias]
    drive.write(uid, value)
    test_value = mc.communication.get_register(uid, servo=alias)
    assert pytest.approx(test_value) == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_register_wrong_uid(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(IMRegisterNotExistError):
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
    mc, alias, environment = motion_controller
    drive = mc.servos[alias]
    mc.communication.set_register(uid, value, servo=alias)
    test_value = drive.read(uid)
    assert pytest.approx(test_value) == value


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_register_wrong_uid(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(IMRegisterNotExistError):
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
    mc, alias, environment = motion_controller
    if fail:
        with pytest.raises(TypeError):
            mc.communication.set_register(uid, value, servo=alias)
    else:
        mc.communication.set_register(uid, value, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_register_wrong_access(motion_controller):
    mc, alias, environment = motion_controller
    uid = "DRV_STATE_STATUS"
    value = 0
    with pytest.raises(IMRegisterWrongAccessError):
        mc.communication.set_register(uid, value, servo=alias)


def dummy_callback(status, _, axis):
    pass


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_subscribe_servo_status(mocker, motion_controller):
    mc, alias, environment = motion_controller
    axis = 1
    patch_callback = mocker.patch("tests.test_communication.dummy_callback")
    mc.communication.subscribe_servo_status(patch_callback, alias)
    time.sleep(0.5)
    mc.motion.motor_enable(alias, axis)
    time.sleep(0.5)
    mc.motion.motor_disable(alias, axis)
    time.sleep(0.5)
    expected_status = [ServoState.RDY, ServoState.ENABLED, ServoState.DISABLED]
    for index, call in enumerate(patch_callback.call_args_list):
        assert call[0][0] == expected_status[index]
        assert call[0][2] == axis


@pytest.mark.virtual
def test_load_firmware_canopen_exception(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(ValueError):
        mc.communication.load_firmware_canopen("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_boot_mode_and_load_firmware_ethernet_exception(mocker, motion_controller):
    mc, alias, environment = motion_controller

    mocker.patch.object(mc, "_get_network", return_value=object())
    with pytest.raises(ValueError):
        mc.communication.boot_mode_and_load_firmware_ethernet("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_load_firmware_moco_exception(mocker, motion_controller):
    mc, alias, environment = motion_controller
    mocker.patch.object(mc, "_get_network", return_value=object())
    with pytest.raises(ValueError):
        mc.communication.load_firmware_moco("fake_fw_file.lfu", servo=alias)


@pytest.mark.virtual
def test_connect_servo_virtual():
    mc = MotionController()
    mc.communication.connect_servo_virtual(port=1062)
    assert mc.communication._Communication__virtual_drive is not None
    mc.communication.disconnect()
    assert mc.communication._Communication__virtual_drive is None


@pytest.mark.virtual
def test_connect_servo_virtual_custom_dictionary(tests_setup: Setup):
    mc = MotionController()
    mc.communication.connect_servo_virtual(dict_path=tests_setup.dictionary, port=1062)
    assert mc.communication._Communication__virtual_drive is not None
    mc.communication.disconnect()
    assert mc.communication._Communication__virtual_drive is None


@pytest.mark.virtual
def test_scan_servos_canopen_with_info(mocker):
    mc = MotionController()
    detected_slaves = OrderedDict({31: SlaveInfo(1234, 123), 32: SlaveInfo(1234, 123)})
    mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.scan_slaves_info", return_value=detected_slaves
    )
    assert mc.communication.scan_servos_canopen_with_info(CanDevice.KVASER) == detected_slaves


@pytest.mark.virtual
def test_scan_servos_canopen(mocker):
    mc = MotionController()
    detected_slaves = [31, 32]
    mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.scan_slaves", return_value=detected_slaves
    )
    assert mc.communication.scan_servos_canopen(CanDevice.KVASER) == detected_slaves


@pytest.mark.virtual
def test_scan_servos_ethercat_with_info(mocker):
    mc = MotionController()
    detected_slaves = OrderedDict({1: SlaveInfo(1234, 123), 2: SlaveInfo(1234, 123)})
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.scan_slaves_info",
        return_value=detected_slaves,
    )
    assert mc.communication.scan_servos_ethercat_with_info("") == detected_slaves


@pytest.mark.virtual
def test_scan_servos_ethercat(mocker):
    mc = MotionController()
    detected_slaves = [1, 2]
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.scan_slaves",
        return_value=detected_slaves,
    )
    assert mc.communication.scan_servos_ethercat("") == detected_slaves


@pytest.mark.virtual
def test_unzip_ensemble_fw_file():
    mc = MotionController()
    with tempfile.TemporaryDirectory() as ensemble_temp_dir:
        mapping = mc.communication._Communication__unzip_ensemble_fw_file(
            TEST_ENSEMBLE_FW_FILE, ensemble_temp_dir
        )

        assert mapping == {
            0: (os.path.join(ensemble_temp_dir, "cap-net-1-e_2.4.0.lfu"), 123456, 4660),
            1: (os.path.join(ensemble_temp_dir, "cap-net-2-e_2.4.0.lfu"), 123456, 16781876),
        }


@pytest.mark.virtual
def test__check_ensemble():
    mc = MotionController()
    with tempfile.TemporaryDirectory() as ensemble_temp_dir:
        mapping = mc.communication._Communication__unzip_ensemble_fw_file(
            TEST_ENSEMBLE_FW_FILE, ensemble_temp_dir
        )
    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4661),
            2: SlaveInfo(product_code, 16781878),
            4: SlaveInfo(product_code, 4662),
            5: SlaveInfo(product_code, 16781879),
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
    with tempfile.TemporaryDirectory() as ensemble_temp_dir:
        mapping = mc.communication._Communication__unzip_ensemble_fw_file(
            TEST_ENSEMBLE_FW_FILE, ensemble_temp_dir
        )

    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(product_code, 16781876),
            3: SlaveInfo(654321, 1236),
        }
    )

    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 3, mapping)
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The selected drive is not part of the ensemble."
    )

    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4660),
            2: SlaveInfo(654321, 16781876),
        }
    )
    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 1, mapping)
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The slave 2 has wrong product code or revision number."
    )

    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 16781877),
            2: SlaveInfo(product_code, 4661),
        }
    )
    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication._Communication__check_ensemble(slaves, 2, mapping)
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The slave 2 is not detected."
    )


@pytest.mark.virtual
@pytest.mark.parametrize("revision_number,expected_id_offset", [(4660, 0), (16781876, 1)])
def test_check_slave_in_ensemble(revision_number, expected_id_offset):
    mc = MotionController()
    with tempfile.TemporaryDirectory() as ensemble_temp_dir:
        mapping = mc.communication._Communication__unzip_ensemble_fw_file(
            TEST_ENSEMBLE_FW_FILE, ensemble_temp_dir
        )
    product_code = 123456
    slave_info = SlaveInfo(product_code, revision_number)

    slave_id_offset = mc.communication._Communication__check_slave_in_ensemble(slave_info, mapping)

    assert slave_id_offset == expected_id_offset


@pytest.mark.virtual
def test_check_slave_in_ensemble_drive_not_in_ensemble():
    mc = MotionController()
    with tempfile.TemporaryDirectory() as ensemble_temp_dir:
        mapping = mc.communication._Communication__unzip_ensemble_fw_file(
            TEST_ENSEMBLE_FW_FILE, ensemble_temp_dir
        )
    product_code = 654321
    revision_number = 4660
    slave_info = SlaveInfo(product_code, revision_number)

    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication._Communication__check_slave_in_ensemble(slave_info, mapping)
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The selected drive is not part of the ensemble."
    )


@pytest.mark.virtual
def test_load_ensemble_fw_ecat(mocker):
    product_code = 123456
    slaves = OrderedDict(
        {
            1: SlaveInfo(product_code, 4661),
            2: SlaveInfo(product_code, 16781877),
            3: SlaveInfo(product_code, 4662),
            4: SlaveInfo(product_code, 16781878),
            5: SlaveInfo(654321, 1236),
        }
    )

    mc = MotionController()
    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.__init__", return_value=None)
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.scan_slaves_info", return_value=slaves
    )
    for slave in [1, 2]:
        patch_fw_callback = mocker.patch(
            "ingenialink.ethercat.network.EthercatNetwork.load_firmware"
        )
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=slave)
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][0].endswith("cap-net-1-e_2.4.0.lfu")
        assert patch_fw_callback.call_args_list[0][0][1] is False
        assert patch_fw_callback.call_args_list[0][0][2] == 1

        assert patch_fw_callback.call_args_list[1][0][0].endswith("cap-net-2-e_2.4.0.lfu")
        assert patch_fw_callback.call_args_list[1][0][1] is False
        assert patch_fw_callback.call_args_list[1][0][2] == 2

    for slave in [3, 4]:
        patch_fw_callback = mocker.patch(
            "ingenialink.ethercat.network.EthercatNetwork.load_firmware"
        )
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=slave)
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][0].endswith("cap-net-1-e_2.4.0.lfu")
        assert patch_fw_callback.call_args_list[0][0][1] is False
        assert patch_fw_callback.call_args_list[0][0][2] == 3

        assert patch_fw_callback.call_args_list[1][0][0].endswith("cap-net-2-e_2.4.0.lfu")
        assert patch_fw_callback.call_args_list[1][0][1] is False
        assert patch_fw_callback.call_args_list[1][0][2] == 4

    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication.load_firmware_ecat("", TEST_ENSEMBLE_FW_FILE, slave=5)
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The selected drive is not part of the ensemble."
    )


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
    net = CanopenNetwork(CanDevice.KVASER)
    net.servos = list(servos.values())
    mocker.patch("ingeniamotion.motion_controller.MotionController._get_network", return_value=net)
    mocker.patch("ingenialink.canopen.network.CanopenNetwork.connect_to_slave")
    mocker.patch("ingenialink.canopen.network.CanopenNetwork.disconnect_from_slave")
    mc._get_drive = lambda x: servos[x]
    mc.servos = servos

    product_code = 123456
    slaves_info = OrderedDict(
        {
            1: SlaveInfo(product_code, 4661),
            2: SlaveInfo(product_code, 16781877),
            3: SlaveInfo(product_code, 4662),
            4: SlaveInfo(product_code, 16781878),
            5: SlaveInfo(654321, 1236),
        }
    )
    mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.scan_slaves_info", return_value=slaves_info
    )
    for slave in [1, 2]:
        patch_fw_callback = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo=str(slave))
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][0] == 1
        assert patch_fw_callback.call_args_list[0][0][1].endswith("cap-net-1-e_2.4.0.lfu")

        assert patch_fw_callback.call_args_list[1][0][0] == 2
        assert patch_fw_callback.call_args_list[1][0][1].endswith("cap-net-2-e_2.4.0.lfu")

    for slave in [3, 4]:
        patch_fw_callback = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo=str(slave))
        assert len(patch_fw_callback.call_args_list) == 2
        assert patch_fw_callback.call_args_list[0][0][0] == 3
        assert patch_fw_callback.call_args_list[0][0][1].endswith("cap-net-1-e_2.4.0.lfu")

        assert patch_fw_callback.call_args_list[1][0][0] == 4
        assert patch_fw_callback.call_args_list[1][0][1].endswith("cap-net-2-e_2.4.0.lfu")

    with pytest.raises(IMFirmwareLoadError) as exc_info:
        mc.communication.load_firmware_canopen(TEST_ENSEMBLE_FW_FILE, servo="5")
    assert (
        str(exc_info.value) == "The firmware file could not be loaded correctly. "
        "The selected drive is not part of the ensemble."
    )


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "net_types", [[EthernetNetwork, CanopenNetwork], [EthercatNetwork, EthernetNetwork], []]
)
def test_get_available_canopen_devices_check_get_available_devices_call(mocker, net_types):
    mc = ingeniamotion.MotionController()
    test_net = None
    for n, n_type in enumerate(net_types):
        net = mocker.MagicMock(spec=n_type)
        mc.net[n] = net
        if n_type == CanopenNetwork:
            test_net = net
    patch_get_available_devices = mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.get_available_devices"
    )
    mc.communication.get_available_canopen_devices()
    if test_net is not None:
        assert test_net.get_available_devices.call_count == 1
        assert patch_get_available_devices.call_count == 0
    else:
        assert patch_get_available_devices.call_count == 1


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_available_canopen_devices(mocker):
    mc = ingeniamotion.MotionController()
    mocker.patch(
        "ingenialink.canopen.network.CanopenNetwork.get_available_devices",
        return_value=[
            ("pcan", "PCAN_USBBUS1"),
            ("pcan", "PCAN_USBBUS2"),
            ("kvaser", 0),
            ("kvaser", 1),
            ("ixxat", 0),
            ("ixxat", 1),
        ],
    )
    test_output = mc.communication.get_available_canopen_devices()
    expected_ouput = {CanDevice.KVASER: [0, 1], CanDevice.PCAN: [0, 1], CanDevice.IXXAT: [0, 1]}
    assert test_output == expected_ouput


@pytest.mark.virtual
@pytest.mark.smoke
def test_subscribe_register_updates(motion_controller):
    user_over_voltage_uid = "DRV_PROT_USER_OVER_VOLT"
    register_update_callback = RegisterUpdateTest()

    mc, alias, environment = motion_controller
    mc.communication.subscribe_register_update(
        register_update_callback.register_update_test, servo=alias
    )

    previous_reg_value = mc.communication.get_register(user_over_voltage_uid, servo=alias)
    assert register_update_callback.call_count == 1
    assert register_update_callback.alias == alias
    assert register_update_callback.register.identifier == user_over_voltage_uid
    assert register_update_callback.value == previous_reg_value

    new_reg_value = 100
    mc.communication.set_register(user_over_voltage_uid, value=new_reg_value, servo=alias)
    assert register_update_callback.call_count == 2
    assert register_update_callback.alias == alias
    assert register_update_callback.register.identifier == user_over_voltage_uid
    assert register_update_callback.value == new_reg_value

    mc.communication.unsubscribe_register_update(
        register_update_callback.register_update_test, servo=alias
    )

    mc.communication.set_register(user_over_voltage_uid, value=previous_reg_value, servo=alias)

    # The old value has not been propagated after unsubscribing
    assert register_update_callback.value == new_reg_value


@pytest.mark.canopen
@pytest.mark.soem
@pytest.mark.smoke
def test_emcy_callback(motion_controller):
    mc, alias, _ = motion_controller
    emcy_test = EmcyTest()
    mc.communication.subscribe_emergency_message(emcy_test.emcy_callback, servo=alias)
    prev_val = mc.communication.get_register("DRV_PROT_USER_OVER_VOLT", axis=1, servo=alias)
    mc.communication.set_register("DRV_PROT_USER_OVER_VOLT", value=10.0, axis=1, servo=alias)
    with pytest.raises(ILError):
        mc.motion.motor_enable(servo=alias)
    mc.motion.fault_reset(servo=alias)
    assert len(emcy_test.messages) == 2
    servo_alias, first_emcy = emcy_test.messages[0]
    assert servo_alias == alias
    assert first_emcy.error_code == 0x3231
    assert first_emcy.get_desc() == "User Over-voltage detected"
    servo_alias, second_emcy = emcy_test.messages[1]
    assert servo_alias == alias
    assert second_emcy.error_code == 0x0000
    assert second_emcy.get_desc() == "No error"
    mc.communication.set_register("DRV_PROT_USER_OVER_VOLT", value=prev_val, axis=1, servo=alias)
    mc.communication.unsubscribe_emergency_message(emcy_test.emcy_callback, servo=alias)
