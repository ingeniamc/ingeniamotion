import pytest

from ingeniamotion import MotionController
from ingeniamotion.enums import SeverityLevel


@pytest.mark.eoe
def test_disturbance_example(read_config, script_runner):
    script_path = "examples/disturbance_example.py"
    ip_address = read_config["ip"]
    dictionary = read_config["dictionary"]
    result = script_runner.run(script_path, f"--ip={ip_address}", f"--dictionary_path={dictionary}")
    assert result.returncode == 0


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
    result = script_runner.run(script_path, mode, dictionary, f"-ip={ip_address}", "-no_wait")
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
