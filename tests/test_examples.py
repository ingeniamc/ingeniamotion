import pytest
from ingenialink import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.exceptions import ILFirmwareLoadError

from examples.load_fw_canopen import load_firmware_canopen
from examples.load_save_configuration import main as main_load_save_configuration
from examples.load_save_config_register_changes import main as main_load_save_config_register_changes
from ingeniamotion import MotionController
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.enums import SeverityLevel


@pytest.mark.eoe
def test_disturbance_example(read_config, script_runner):
    script_path = "examples/disturbance_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}")
    assert result.returncode == 0


@pytest.mark.canopen
@pytest.mark.skip(reason="This test fails because the canopen node is already connected")
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
def test_load_save_configuration(mocker):
    connect_servo_ethercat_interface_index = mocker.patch.object(Communication, "connect_servo_ethercat_interface_index")
    disconnect = mocker.patch.object(Communication, "disconnect")
    save_configuration = mocker.patch.object(Configuration, "save_configuration")
    load_configuration = mocker.patch.object(Configuration, "load_configuration")

    main_load_save_configuration()

    connect_servo_ethercat_interface_index.assert_called_once()
    save_configuration.assert_called_once()
    load_configuration.assert_called_once()
    disconnect.assert_called_once()


@pytest.mark.virtual
def test_load_save_configuration_register_changes_success(mocker, capsys):
    mocker.patch.object(Communication, "connect_servo_ethercat_interface_index")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Configuration, "save_configuration")
    mocker.patch.object(Configuration, "load_configuration")
    mocker.patch.object(Configuration, "get_max_velocity", side_effect=[10.0, 10.0, 20.0])
    mocker.patch.object(Configuration, "set_max_velocity")

    main_load_save_config_register_changes()

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")

    assert all_outputs[0] == "The initial configuration is saved."
    assert all_outputs[1] == "The configuration file is saved with the modification."
    assert all_outputs[2] == "Max. velocity register has the initial value."
    assert all_outputs[3] == "Max. velocity register has the new value."


@pytest.mark.virtual
def test_load_save_configuration_register_changes_failed(mocker, capsys):
    mocker.patch.object(Communication, "connect_servo_ethercat_interface_index")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Configuration, "save_configuration")
    mocker.patch.object(Configuration, "load_configuration")
    mocker.patch.object(Configuration, "get_max_velocity", return_value=20.0)
    mocker.patch.object(Configuration, "set_max_velocity")

    main_load_save_config_register_changes()

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")

    assert all_outputs[0] == "The initial configuration is saved."
    assert all_outputs[1] == "This max. velocity value is already set."
