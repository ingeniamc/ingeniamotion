import pytest

from ingeniamotion import MotionController


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
