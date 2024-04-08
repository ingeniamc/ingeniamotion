import pytest
from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from examples.change_baudrate import change_baudrate
from examples.change_node_id import change_node_id
from ingeniamotion import MotionController
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.enums import SeverityLevel
from ingeniamotion.information import Information


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
def test_change_node_id_success(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "test_dictionary.xdf"

    node_id = 20
    new_node_id = 20

    mocker.patch.object(
        Communication, "scan_servos_canopen", side_effect=[[node_id], [new_node_id]]
    )
    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_node_id", side_effect=[node_id, new_node_id])
    mocker.patch.object(Configuration, "change_node_id")
    change_node_id(device, channel, baudrate, dictionary_path, new_node_id, node_id)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "Finding the available nodes..."
    assert all_outputs[1] == f"Found nodes: [{node_id}]"
    assert all_outputs[4] == f"Drive is connected with {node_id} as a node ID."
    assert all_outputs[6] == "Node ID has been changed"
    assert all_outputs[9] == "Finding the available nodes..."
    assert all_outputs[10] == f"Found nodes: [{new_node_id}]"
    assert all_outputs[13] == f"Drive is connected with {new_node_id} as a node ID."


@pytest.mark.virtual
def test_change_node_id_failed(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "test_dictionary.xdf"

    node_id = 20
    new_node_id = node_id

    mocker.patch.object(
        Communication, "scan_servos_canopen", side_effect=[[node_id], [new_node_id]]
    )
    mocker.patch.object(Communication, "connect_servo_canopen")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Information, "get_node_id", side_effect=[node_id, new_node_id])
    mocker.patch.object(Configuration, "change_node_id")
    change_node_id(device, channel, baudrate, dictionary_path, new_node_id, node_id)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "Finding the available nodes..."
    assert all_outputs[1] == f"Found nodes: [{node_id}]"
    assert all_outputs[4] == f"Drive is connected with {node_id} as a node ID."
    assert all_outputs[6] == f"This drive already has this node ID: {node_id}."


@pytest.mark.virtual
def test_change_baudrate(mocker, capsys):
    device = CAN_DEVICE.PCAN
    channel = 0
    baudrate = CAN_BAUDRATE.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    new_baudrate = CAN_BAUDRATE.Baudrate_125K

    expected_node_list = [node_id]

    class MockCommunication:
        def scan_servos_canopen(*args, **kwargs):
            return expected_node_list

        def connect_servo_canopen(*args, **kwargs):
            pass

        def disconnect(*args, **kwargs):
            pass

    def mock_get_baudrate(*args, **kwargs):
        return baudrate

    def mock_change_baudrate(*args, **kwargs):
        pass

    mocker.patch.object(MotionController, "communication", MockCommunication)
    mocker.patch.object(Information, "get_baudrate", mock_get_baudrate)
    mocker.patch.object(Configuration, "change_baudrate", mock_change_baudrate)
    change_baudrate(device, channel, baudrate, dictionary_path, new_baudrate, node_id)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[4] == f"Drive is connected with {baudrate} baudrate."
    assert all_outputs[6] == f"Baudrate has been changed from {baudrate} to {new_baudrate}."
    assert (
        all_outputs[8]
        == f"Make a power-cycle on your drive and connect it again using the new baudrate {new_baudrate}"
    )
