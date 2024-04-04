from typing import Dict

import pytest

from examples.connect_ecat_coe import connect_ethercat_coe
from ingeniamotion import MotionController
from ingeniamotion.communication import Communication
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
def test_ecat_coe_connection_example_success(mocker, capsys):
    ecat_coe_conf = {
        "interface_index": 2,
        "slave_id": 1,
        "dictionary": "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.5.1\\cap-net-e_eoe_2.5.1.xdf",
    }

    expected_slave_list = [ecat_coe_conf["slave_id"]]
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = (
        f"\\Device\\NPF_real_name_interface_{ecat_coe_conf['interface_index']}"
    )
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

    connect_ethercat_coe(ecat_coe_conf)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces - Human-readable format:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {ecat_coe_conf['interface_index']}"
    assert all_outputs[6] == f"- Real name: {expected_real_name_interface}"
    assert (
        all_outputs[7]
        == f"- Human-readable format name: {expected_interfaces_name_list[ecat_coe_conf['interface_index']]}"
    )
    assert all_outputs[8] == f"Found slaves: {expected_slave_list}"
    assert all_outputs[9] == f"Drive is connected."
    assert all_outputs[10] == f"The drive has been disconnected."


@pytest.mark.virtual
def test_ecat_coe_connection_example_failed(mocker, capsys):
    ecat_coe_conf = {
        "interface_index": 2,
        "slave_id": 1,
        "dictionary": "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.5.1\\cap-net-e_eoe_2.5.1.xdf",
    }

    expected_slave_list = [ecat_coe_conf["slave_id"]]
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = (
        f"\\Device\\NPF_real_name_interface_{ecat_coe_conf['interface_index']}"
    )
    test_servos: Dict[str, str] = {}

    def scan_servos_ethercat(*args, **kwargs):
        return expected_slave_list

    def get_interface_name_list(*args, **kwargs):
        return expected_interfaces_name_list

    def get_ifname_by_index(*args, **kwargs):
        return expected_real_name_interface

    def connect_servo_ethercat(*args, **kwargs):
        test_servos = {}

    mocker.patch.object(Communication, "scan_servos_ethercat", scan_servos_ethercat)
    mocker.patch.object(Communication, "get_interface_name_list", get_interface_name_list)
    mocker.patch.object(Communication, "get_ifname_by_index", get_ifname_by_index)
    mocker.patch.object(MotionController, "servos", test_servos)
    mocker.patch.object(Communication, "connect_servo_ethercat", connect_servo_ethercat)

    connect_ethercat_coe(ecat_coe_conf)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces - Human-readable format:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {ecat_coe_conf['interface_index']}"
    assert all_outputs[6] == f"- Real name: {expected_real_name_interface}"
    assert (
        all_outputs[7]
        == f"- Human-readable format name: {expected_interfaces_name_list[ecat_coe_conf['interface_index']]}"
    )
    assert all_outputs[8] == f"Found slaves: {expected_slave_list}"
    assert all_outputs[9] == f"Drive is not connected."


@pytest.mark.virtual
def test_ecat_coe_connection_example_connection_error(mocker, capsys):
    ecat_coe_conf = {
        "interface_index": 2,
        "slave_id": 1,
        "dictionary": "my_dictionary.xdf",
    }

    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = (
        f"\\Device\\NPF_real_name_interface_{ecat_coe_conf['interface_index']}"
    )

    def get_interface_name_list(*args, **kwargs):
        return expected_interfaces_name_list

    def get_ifname_by_index(*args, **kwargs):
        return expected_real_name_interface

    mocker.patch.object(Communication, "get_interface_name_list", get_interface_name_list)
    mocker.patch.object(Communication, "get_ifname_by_index", get_ifname_by_index)

    with pytest.raises(ConnectionError) as e:
        connect_ethercat_coe(ecat_coe_conf)

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    assert all_outputs[0] == "List of interfaces - Human-readable format:"
    assert all_outputs[1] == "0: Interface 1"
    assert all_outputs[2] == "1: Interface 2"
    assert all_outputs[3] == "2: Interface 3"
    assert all_outputs[4] == "Interface selected:"
    assert all_outputs[5] == f"- Index interface: {ecat_coe_conf['interface_index']}"
    assert all_outputs[6] == f"- Real name: {expected_real_name_interface}"
    assert (
        all_outputs[7]
        == f"- Human-readable format name: {expected_interfaces_name_list[ecat_coe_conf['interface_index']]}"
    )

    assert e.value.args[0] == f"could not open interface {expected_real_name_interface}"
