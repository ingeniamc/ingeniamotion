from collections import deque
from typing import Dict

import pytest
from ingenialink import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.exceptions import ILFirmwareLoadError

from examples.change_baudrate import change_baudrate
from examples.change_node_id import change_node_id
from examples.connect_ecat_coe import connect_ethercat_coe
from examples.load_fw_canopen import load_firmware_canopen
from examples.pdo_poller_example import main as set_up_pdo_poller
from ingeniamotion import MotionController
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.enums import SeverityLevel
from ingeniamotion.information import Information
from ingeniamotion.pdo import PDONetworkManager, PDOPoller


@pytest.mark.eoe
def test_disturbance_example(read_config, script_runner):
    script_path = "examples/disturbance_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}")
    assert result.returncode == 0


@pytest.mark.usefixtures("setup_for_test_examples", "teardown_for_test_examples")
@pytest.mark.canopen
def test_canopen_example(read_config, script_runner):
    script_path = "examples/canopen_example.py"
    dictionary = read_config["dictionary"]
    node_id = read_config["node_id"]
    can_transceiver = read_config["device"]
    can_baudrate = read_config["baudrate"]
    can_channel = read_config["channel"]
    result = script_runner.run(
        script_path,
        f"--dictionary_path={dictionary}",
        f"--node_id={node_id}",
        f"--can_transceiver={can_transceiver}",
        f"--can_baudrate={can_baudrate}",
        f"--can_channel={can_channel}",
    )
    assert result.returncode == 0


@pytest.mark.eoe
def test_set_get_register_example(read_config, script_runner):
    script_path = "examples/set_get_register.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}")
    assert result.returncode == 0


@pytest.mark.eoe
def test_poller_example(read_config, script_runner):
    script_path = "examples/poller_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(
        script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}", "--close"
    )
    assert result.returncode == 0


@pytest.mark.eoe
@pytest.mark.parametrize(
    "mode",
    ["velocity", "torque"],
)
def test_velocity_torque_ramp_example(read_config, script_runner, mocker, mode):
    script_path = "examples/velocity_torque_ramp.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]

    class MockMotion:
        def wait_for_velocity(self, *args, **kwargs):
            pass

        def set_operation_mode(self, *args, **kwargs):
            pass

        def set_velocity(self, *args, **kwargs):
            pass

        def motor_enable(*args, **kwargs):
            pass

        def motor_disable(*args, **kwargs):
            pass

        def set_current_quadrature(*args, **kwargs):
            pass

    mocker.patch.object(MotionController, "motion", MockMotion)
    mocker.patch("time.sleep", return_value=None)
    result = script_runner.run(
        script_path, mode, dictionary, f"-ip={ip_address}", f"-target_torque={0}"
    )
    assert result.returncode == 0


@pytest.mark.eoe
def test_monitoring_example(read_config, script_runner):
    script_path = "examples/monitoring_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(
        script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}", "--close"
    )
    assert result.returncode == 0


@pytest.mark.eoe
def test_load_fw_ftp(read_config, script_runner, mocker):
    script_path = "examples/load_fw_ftp.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    fw_file = read_config["fw_file"]

    class MockCommunication:
        def boot_mode_and_load_firmware_ethernet(self, *args, **kwargs):
            pass

        def connect_servo_ethernet(self, *args, **kwargs):
            pass

    mocker.patch.object(MotionController, "communication", MockCommunication)
    result = script_runner.run(
        script_path,
        f"--dictionary_path={dictionary}",
        f"--ip={ip_address}",
        f"--firmware_file={fw_file}",
    )
    assert result.returncode == 0


@pytest.mark.soem
def test_load_fw_ecat(read_config, script_runner, mocker):
    script_path = "examples/load_fw_ecat.py"
    interface_index = read_config["index"]
    slave_id = read_config["slave"]
    fw_file = read_config["fw_file"]

    class MockCommunication:
        def load_firmware_ecat_interface_index(self, *args, **kwargs):
            pass

        def get_interface_name_list(*args, **kwargs):
            pass

    mocker.patch.object(MotionController, "communication", MockCommunication)
    result = script_runner.run(
        script_path,
        f"--interface_index={interface_index}",
        f"--slave_id={slave_id}",
        f"--firmware_file={fw_file}",
    )
    assert result.returncode == 0


@pytest.mark.eoe
@pytest.mark.parametrize(
    "feedback",
    ["HALLS", "QEI", "QEI2"],
)
def test_feedback_example(read_config, script_runner, mocker, feedback):
    script_path = "examples/feedback_test.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]

    class MockDriveTests:
        def digital_halls_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

        def incremental_encoder_1_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

        def incremental_encoder_2_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

    mocker.patch.object(MotionController, "tests", MockDriveTests)
    result = script_runner.run(script_path, feedback, dictionary, f"-ip={ip_address}")
    assert result.returncode == 0


@pytest.mark.eoe
def test_commutation_test_example(read_config, script_runner, mocker):
    script_path = "examples/commutation_test.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]

    class MockDriveTests:
        def commutation(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

    mocker.patch.object(MotionController, "tests", MockDriveTests)
    result = script_runner.run(script_path, dictionary, f"-ip={ip_address}")
    assert result.returncode == 0


@pytest.mark.eoe
@pytest.mark.parametrize(
    "override",
    ["disabled", "release", "enable"],
)
def test_brake_config_example(read_config, script_runner, mocker, override):
    script_path = "examples/brake_config.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]

    class MockConfiguration:
        def disable_brake_override(*args, **kwargs):
            pass

        def release_brake(*args, **kwargs):
            pass

        def enable_brake(*args, **kwargs):
            pass

    mocker.patch.object(MotionController, "configuration", MockConfiguration)
    result = script_runner.run(script_path, override, dictionary, f"-ip={ip_address}")
    assert result.returncode == 0


@pytest.mark.virtual
def test_can_bootloader_example_success(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    fw_path = "test_fw.lfu"

    expected_node_list = [node_id]
    status_message = "Mock status message."
    progress_message = "100"

    class MockCommunication:
        def scan_servos_canopen(*args, **kwargs):
            return expected_node_list

        def connect_servo_canopen(*args, **kwargs):
            pass

        def load_firmware_canopen(*args, **kwargs):
            kwargs["status_callback"](status_message)
            kwargs["progress_callback"](progress_message)

        def disconnect(*args, **kwargs):
            pass

    mock_servos = {"default": "my_servo"}

    mocker.patch.object(MotionController, "communication", MockCommunication)
    mocker.patch.object(MotionController, "servos", mock_servos)
    load_firmware_canopen(device, channel, baudrate, node_id, dictionary_path, fw_path)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == f"Found nodes: {expected_node_list}"
    assert all_outputs[1] == "Starts to establish a communication."
    assert all_outputs[2] == "Drive is connected."
    assert all_outputs[3] == "Starts to load the firmware."
    assert all_outputs[4] == f"Load firmware status: {status_message}"
    assert all_outputs[5] == f"Load firmware progress: {progress_message}%"
    assert all_outputs[6] == "Firmware is uploaded successfully."
    assert all_outputs[7] == "Drive is disconnected."


@pytest.mark.virtual
def test_can_bootloader_example_failed(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    fw_path = "test_fw.lfu"

    expected_node_list = [node_id]
    fw_error_message = "An error occurs during the firmware updating."

    class MockCommunication:
        def scan_servos_canopen(*args, **kwargs):
            return expected_node_list

        def connect_servo_canopen(*args, **kwargs):
            pass

        def load_firmware_canopen(*args, **kwargs):
            raise ILFirmwareLoadError(fw_error_message)

        def disconnect(*args, **kwargs):
            pass

    mock_servos = {"default": "my_servo"}

    mocker.patch.object(MotionController, "communication", MockCommunication)
    mocker.patch.object(MotionController, "servos", mock_servos)
    load_firmware_canopen(device, channel, baudrate, node_id, dictionary_path, fw_path)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == f"Found nodes: {expected_node_list}"
    assert all_outputs[1] == "Starts to establish a communication."
    assert all_outputs[2] == "Drive is connected."
    assert all_outputs[3] == "Starts to load the firmware."
    assert all_outputs[4] == f"Firmware loading failed: {fw_error_message}"
    assert all_outputs[5] == "Drive is disconnected."


@pytest.mark.virtual
def test_change_node_id_success(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "test_dictionary.xdf"

    node_id = 20
    test_new_node_id = 32

    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_node_id", side_effect=[node_id, test_new_node_id])
    mocker.patch.object(Configuration, "change_node_id")
    change_node_id(device, channel, node_id, baudrate, dictionary_path, test_new_node_id)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[1] == f"Drive is connected with {node_id} as a node ID."
    assert all_outputs[3] == "Node ID has been changed"
    assert all_outputs[6] == f"Now the drive is connected with {test_new_node_id} as a node ID."


@pytest.mark.virtual
def test_change_node_id_failed(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "test_dictionary.xdf"

    node_id = 20
    test_new_node_id = node_id

    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_node_id", side_effect=[node_id, test_new_node_id])
    mocker.patch.object(Configuration, "change_node_id")
    change_node_id(device, channel, node_id, baudrate, dictionary_path, test_new_node_id)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[1] == f"Drive is connected with {node_id} as a node ID."
    assert all_outputs[3] == f"This drive already has this node ID: {node_id}."


@pytest.mark.virtual
def test_change_baudrate_success(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    test_new_baudrate = CAN_BAUDRATE.Baudrate_125K

    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_baudrate", side_effect=[baudrate])
    mocker.patch.object(Configuration, "change_baudrate")
    change_baudrate(device, channel, node_id, baudrate, dictionary_path, test_new_baudrate)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == f"Drive is connected with {baudrate} baudrate."
    assert all_outputs[2] == f"Baudrate has been changed from {baudrate} to {test_new_baudrate}."
    assert (
        all_outputs[4]
        == f"Perform a power cycle and reconnect to the drive using the new baud rate: {test_new_baudrate}"
    )


@pytest.mark.virtual
def test_change_baudrate_failed(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    test_new_baudrate = baudrate

    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_baudrate", side_effect=[baudrate])
    mocker.patch.object(Configuration, "change_baudrate")
    change_baudrate(device, channel, node_id, baudrate, dictionary_path, test_new_baudrate)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == f"Drive is connected with {baudrate} baudrate."
    assert all_outputs[2] == f"This drive already has this baudrate: {baudrate}."


@pytest.mark.virtual
def test_ecat_coe_connection_example_success(mocker, capsys):
    interface_index = 2
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.4.0\\cap-net-e_eoe_2.4.0.xdf"
    )
    expected_slave_list = [slave_id]
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = f"\\Device\\NPF_real_name_interface_{interface_index}"
    test_alias = "default"
    test_servos: Dict[str, str] = {}

    def scan_servos_ethercat(*args, **kwargs):
        return expected_slave_list

    def get_interface_name_list(*args, **kwargs):
        return expected_interfaces_name_list

    def get_ifname_by_index(*args, **kwargs):
        return expected_real_name_interface

    def connect_servo_ethercat(*args, **kwargs):
        test_servos[test_alias] = "my_servo"

    def disconnect(*args, **kwargs):
        test_servos.pop(test_alias)

    mocker.patch.object(Communication, "scan_servos_ethercat", scan_servos_ethercat)
    mocker.patch.object(Communication, "get_interface_name_list", get_interface_name_list)
    mocker.patch.object(Communication, "get_ifname_by_index", get_ifname_by_index)
    mocker.patch.object(MotionController, "servos", test_servos)
    mocker.patch.object(Communication, "connect_servo_ethercat", connect_servo_ethercat)
    mocker.patch.object(Communication, "disconnect", disconnect)
    connect_ethercat_coe(interface_index, slave_id, dictionary_path)
    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {interface_index}"
    assert all_outputs[6] == f"- Interface identifier: {expected_real_name_interface}"
    assert all_outputs[7] == f"- Interface name: {expected_interfaces_name_list[interface_index]}"
    assert all_outputs[8] == f"Found slaves: {expected_slave_list}"
    assert all_outputs[9] == f"Drive is connected."
    assert all_outputs[10] == f"The drive has been disconnected."


@pytest.mark.virtual
def test_ecat_coe_connection_example_failed(mocker, capsys):
    interface_index = 2
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.4.0\\cap-net-e_eoe_2.4.0.xdf"
    )
    expected_slave_list = []
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = f"\\Device\\NPF_real_name_interface_{interface_index}"
    test_servos: Dict[str, str] = {}

    def scan_servos_ethercat(*args, **kwargs):
        return expected_slave_list

    def get_interface_name_list(*args, **kwargs):
        return expected_interfaces_name_list

    def get_ifname_by_index(*args, **kwargs):
        return expected_real_name_interface

    mocker.patch.object(Communication, "scan_servos_ethercat", scan_servos_ethercat)
    mocker.patch.object(Communication, "get_interface_name_list", get_interface_name_list)
    mocker.patch.object(Communication, "get_ifname_by_index", get_ifname_by_index)
    mocker.patch.object(MotionController, "servos", test_servos)
    connect_ethercat_coe(interface_index, slave_id, dictionary_path)
    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {interface_index}"
    assert all_outputs[6] == f"- Interface identifier: {expected_real_name_interface}"
    assert all_outputs[7] == f"- Interface name: {expected_interfaces_name_list[interface_index]}"
    assert (
        all_outputs[8]
        == f"No slave detected on interface: {expected_interfaces_name_list[interface_index]}"
    )


@pytest.mark.virtual
def test_ecat_coe_connection_example_connection_error(mocker, capsys):
    interface_index = 2
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.4.0\\cap-net-e_eoe_2.4.0.xdf"
    )
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = f"\\Device\\NPF_real_name_interface_{interface_index}"

    def get_interface_name_list(*args, **kwargs):
        return expected_interfaces_name_list

    def get_ifname_by_index(*args, **kwargs):
        return expected_real_name_interface

    mocker.patch.object(Communication, "get_interface_name_list", get_interface_name_list)
    mocker.patch.object(Communication, "get_ifname_by_index", get_ifname_by_index)
    with pytest.raises(ConnectionError) as e:
        connect_ethercat_coe(interface_index, slave_id, dictionary_path)
    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {interface_index}"
    assert all_outputs[6] == f"- Interface identifier: {expected_real_name_interface}"
    assert all_outputs[7] == f"- Interface name: {expected_interfaces_name_list[interface_index]}"
    assert e.value.args[0] == f"could not open interface {expected_real_name_interface}"


@pytest.mark.virtual
def test_pdo_poller_success(mocker):
    connect_servo_ethercat_interface_ip = mocker.patch.object(
        Communication, "connect_servo_ethercat_interface_ip"
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    mock_pdo_poller = PDOPoller(MotionController(), "mock_alias", 0.1, 100)
    create_poller = mocker.patch.object(
        PDONetworkManager, "create_poller", return_value=mock_pdo_poller
    )
    mock_poller_data = (deque([0.1, 0.2]), [deque([1, 2]), deque([0.0, 0.0])])
    data = mocker.patch.object(
        PDOPoller, "data", new_callable=mocker.PropertyMock, return_value=mock_poller_data
    )
    stop = mocker.patch.object(PDOPoller, "stop")

    set_up_pdo_poller()

    connect_servo_ethercat_interface_ip.assert_called_once()
    create_poller.assert_called_once()
    data.assert_called_once()
    stop.assert_called_once()
    disconnect.assert_called_once()
