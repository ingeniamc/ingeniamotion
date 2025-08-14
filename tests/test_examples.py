from collections import deque
from unittest.mock import Mock

import pytest
from ingenialink import CanBaudrate, CanDevice
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILFirmwareLoadError
from ingenialink.pdo import RPDOMap, TPDOMap
from summit_testing_framework.setups.descriptors import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    EthernetSetup,
)

from examples.change_baudrate import change_baudrate
from examples.change_node_id import change_node_id
from examples.commutation_test_encoders import main as main_commutation_test_encoders
from examples.connect_ecat_coe import connect_ethercat_coe
from examples.load_fw_canopen import load_firmware_canopen
from examples.load_save_config_register_changes import (
    main as main_load_save_config_register_changes,
)
from examples.load_save_configuration import main as main_load_save_configuration
from examples.pdo_poller_example import main as set_up_pdo_poller
from examples.position_ramp import main as main_position_ramp
from examples.process_data_object import main as main_process_data_object
from ingeniamotion import MotionController
from ingeniamotion.communication import Communication
from ingeniamotion.configuration import Configuration
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.enums import SeverityLevel
from ingeniamotion.information import Information
from ingeniamotion.motion import Motion
from ingeniamotion.pdo import PDOPoller


@pytest.mark.ethernet
def test_disturbance_example(setup_descriptor: EthernetSetup, script_runner):
    script_path = "examples/disturbance_example.py"
    ip_address = setup_descriptor.ip
    dictionary = setup_descriptor.dictionary
    result = script_runner.run([
        script_path,
        f"--ip={ip_address}",
        f"--dictionary_path={dictionary}",
    ])
    assert result.returncode == 0


@pytest.mark.canopen
@pytest.mark.skip_testing_framework
def test_canopen_example(setup_descriptor: DriveCanOpenSetup, script_runner):
    script_path = "examples/canopen_example.py"

    result = script_runner.run([
        script_path,
        f"--dictionary_path={setup_descriptor.dictionary}",
        f"--node_id={setup_descriptor.node_id}",
        f"--can_transceiver={setup_descriptor.device}",
        f"--can_baudrate={setup_descriptor.baudrate}",
        f"--can_channel={setup_descriptor.channel}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_set_get_register_example(setup_descriptor: DriveEthernetSetup, script_runner):
    script_path = "examples/set_get_register.py"
    result = script_runner.run([
        script_path,
        f"--ip={setup_descriptor.ip}",
        f"--dictionary_path={setup_descriptor.dictionary}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_poller_example(setup_descriptor: DriveEthernetSetup, script_runner):
    script_path = "examples/poller_example.py"

    result = script_runner.run([
        script_path,
        f"--ip={setup_descriptor.ip}",
        f"--dictionary_path={setup_descriptor.dictionary}",
        "--close",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "mode",
    ["velocity", "torque"],
)
def test_velocity_torque_ramp_example(
    setup_descriptor: DriveEthernetSetup, script_runner, mocker, mode
):
    script_path = "examples/velocity_torque_ramp.py"

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
    result = script_runner.run([
        script_path,
        mode,
        setup_descriptor.dictionary,
        f"-ip={setup_descriptor.ip}",
        f"-target_torque={0}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_monitoring_example(setup_descriptor: DriveEthernetSetup, script_runner):
    script_path = "examples/monitoring_example.py"

    result = script_runner.run([
        script_path,
        f"--ip={setup_descriptor.ip}",
        f"--dictionary_path={setup_descriptor.dictionary}",
        "--close",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_load_fw_ftp(setup_descriptor: DriveEthernetSetup, script_runner, mocker):
    script_path = "examples/load_fw_ftp.py"

    class MockCommunication:
        def boot_mode_and_load_firmware_ethernet(self, *args, **kwargs):
            pass

        def connect_servo_ethernet(self, *args, **kwargs):
            pass

    mocker.patch.object(MotionController, "communication", MockCommunication)
    result = script_runner.run([
        script_path,
        f"--dictionary_path={setup_descriptor.dictionary}",
        f"--ip={setup_descriptor.ip}",
        f"--firmware_file={setup_descriptor.fw_data.fw_file}",
    ])
    assert result.returncode == 0


@pytest.mark.soem
def test_load_fw_ecat(setup_descriptor: DriveEcatSetup, script_runner, mocker):
    script_path = "examples/load_fw_ecat.py"
    interface_index = 0
    slave_id = setup_descriptor.slave
    fw_file = setup_descriptor.fw_data.fw_file

    class MockCommunication:
        def load_firmware_ecat_interface_index(self, *args, **kwargs):
            pass

        def get_interface_name_list(*args, **kwargs):
            pass

    mocker.patch.object(MotionController, "communication", MockCommunication)
    result = script_runner.run([
        script_path,
        f"--interface_index={interface_index}",
        f"--slave_id={slave_id}",
        f"--firmware_file={fw_file}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "feedback",
    ["HALLS", "QEI", "QEI2"],
)
def test_feedback_example(setup_descriptor: DriveEthernetSetup, script_runner, mocker, feedback):
    script_path = "examples/feedback_test.py"

    class MockDriveTests:
        def digital_halls_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

        def incremental_encoder_1_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

        def incremental_encoder_2_test(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

    mocker.patch.object(MotionController, "tests", MockDriveTests)
    result = script_runner.run([
        script_path,
        feedback,
        setup_descriptor.dictionary,
        f"-ip={setup_descriptor.ip}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_commutation_test_example(setup_descriptor: DriveEthernetSetup, script_runner, mocker):
    script_path = "examples/commutation_test.py"

    class MockDriveTests:
        def commutation(*args, **kwargs):
            return {"result_message": SeverityLevel.SUCCESS}

    mocker.patch.object(MotionController, "tests", MockDriveTests)
    result = script_runner.run([
        script_path,
        setup_descriptor.dictionary,
        f"-ip={setup_descriptor.ip}",
    ])
    assert result.returncode == 0


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "override",
    ["disabled", "release", "enable"],
)
def test_brake_config_example(
    setup_descriptor: DriveEthernetSetup, script_runner, mocker, override
):
    script_path = "examples/brake_config.py"

    class MockConfiguration:
        def disable_brake_override(*args, **kwargs):
            pass

        def release_brake(*args, **kwargs):
            pass

        def enable_brake(*args, **kwargs):
            pass

    mocker.patch.object(MotionController, "configuration", MockConfiguration)
    result = script_runner.run([
        script_path,
        override,
        setup_descriptor.dictionary,
        f"-ip={setup_descriptor.ip}",
    ])
    assert result.returncode == 0


def test_can_bootloader_example_success(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
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


def test_can_bootloader_example_failed(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
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


def test_change_node_id_success(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
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


def test_change_node_id_failed(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
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


def test_change_baudrate_success(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
    node_id = 32
    dictionary_path = "test_dictionary.xdf"
    test_new_baudrate = CanBaudrate.Baudrate_125K

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
        all_outputs[4] == "Perform a power cycle and reconnect to the drive using the"
        f" new baud rate: {test_new_baudrate}"
    )


def test_change_baudrate_failed(mocker, capsys):
    device = CanDevice.PCAN
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
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
    test_servos: dict[str, str] = {}

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
    assert all_outputs[9] == "Drive is connected."
    assert all_outputs[10] == "The drive has been disconnected."


def test_ecat_coe_connection_example_failed(mocker, capsys):
    interface_index = 2
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.4.0\\cap-net-e_eoe_2.4.0.xdf"
    )
    expected_slave_list = []
    expected_interfaces_name_list = ["Interface 1", "Interface 2", "Interface 3"]
    expected_real_name_interface = f"\\Device\\NPF_real_name_interface_{interface_index}"
    test_servos: dict[str, str] = {}

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

    def scan_servos_ethercat(*args, **kwargs):
        return [1]

    def connect_servo_ethercat(*args, **kwargs):
        raise ConnectionError(f"could not open interface {expected_real_name_interface}")

    def disconnect(*args, **kwargs):
        return None

    mocker.patch.object(Communication, "scan_servos_ethercat", scan_servos_ethercat)
    mocker.patch.object(Communication, "connect_servo_ethercat", connect_servo_ethercat)
    mocker.patch.object(Communication, "disconnect", disconnect)
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


@pytest.mark.soem
def test_pdo_poller_success(mocker):
    connect_servo_ethercat_interface_ip = mocker.patch.object(
        Communication,
        "connect_servo_ethercat_interface_ip",
        return_value=(EthercatNetwork(interface_name="mock_interface"), None),
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    get_drive = mocker.patch.object(MotionController, "_get_drive")
    get_network = mocker.patch.object(MotionController, "_get_network")
    mock_pdo_poller = PDOPoller(MotionController(), "mock_alias", 0.1, None, 100)
    create_poller = mocker.patch.object(PDOPoller, "create_poller", return_value=mock_pdo_poller)
    mock_poller_data = (deque([0.1, 0.2]), [deque([1, 2]), deque([0.0, 0.0])])
    data = mocker.patch.object(
        PDOPoller, "data", new_callable=mocker.PropertyMock, return_value=mock_poller_data
    )
    stop = mocker.patch.object(PDOPoller, "stop")

    set_up_pdo_poller()

    connect_servo_ethercat_interface_ip.assert_called_once()
    create_poller.assert_called_once()
    get_drive.assert_called_once()
    get_network.assert_called_once()
    data.assert_called_once()
    stop.assert_called_once()
    disconnect.assert_called_once()


def test_load_save_configuration(mocker):
    connect_servo_ethercat_interface_index = mocker.patch.object(
        Communication, "connect_servo_ethercat_interface_index"
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    save_configuration = mocker.patch.object(Configuration, "save_configuration")
    load_configuration = mocker.patch.object(Configuration, "load_configuration")

    main_load_save_configuration()

    connect_servo_ethercat_interface_index.assert_called_once()
    save_configuration.assert_called_once()
    load_configuration.assert_called_once()
    disconnect.assert_called_once()


def test_load_save_configuration_register_changes_success(mocker, capsys):
    mocker.patch.object(Communication, "connect_servo_ethercat_interface_index")
    mocker.patch.object(Communication, "disconnect")
    mocker.patch.object(Configuration, "save_configuration")
    mocker.patch.object(Configuration, "load_configuration")
    test_velocities = [10.0, 10.0, 20.0]
    mocker.patch.object(Configuration, "get_max_velocity", side_effect=test_velocities)
    mocker.patch.object(Configuration, "set_max_velocity")

    main_load_save_config_register_changes()

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")

    assert all_outputs[0] == "The initial configuration is saved."
    assert all_outputs[1] == "The configuration file is saved with the modification."
    assert (
        all_outputs[2]
        == f"Max. velocity register should be set to its initial value ({test_velocities[1]}). "
        f"Current value: {test_velocities[1]}"
    )
    assert (
        all_outputs[3]
        == f"Max. velocity register should now be set to the new value ({test_velocities[2]}). "
        f"Current value: {test_velocities[2]}"
    )


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


@pytest.mark.soem
def test_process_data_object(mocker):
    connect_servo_ethercat_interface_ip = mocker.patch.object(
        Communication,
        "connect_servo_ethercat_interface_ip",
        return_value=(EthercatNetwork(interface_name="mock_interface"), None),
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    motor_enable = mocker.patch.object(Motion, "motor_enable")
    motor_disable = mocker.patch.object(Motion, "motor_disable")
    create_pdo_item = mocker.patch("examples.process_data_object.PDONetworkManager.create_pdo_item")
    create_pdo_maps = mocker.patch(
        "examples.process_data_object.PDONetworkManager.create_pdo_maps",
        return_value=(RPDOMap(), TPDOMap),
    )
    set_pdo_maps_to_slave = mocker.patch(
        "examples.process_data_object.PDONetworkManager.set_pdo_maps_to_slave"
    )
    activate_pdos = mocker.patch.object(EthercatNetwork, "activate_pdos")
    deactivate_pdos = mocker.patch.object(EthercatNetwork, "deactivate_pdos")
    mocker.patch.object(Motion, "get_actual_position")
    subscribe_to_receive_process_data = mocker.patch(
        "examples.process_data_object.PDONetworkManager.subscribe_to_receive_process_data"
    )
    subscribe_to_send_process_data = mocker.patch(
        "examples.process_data_object.PDONetworkManager.subscribe_to_send_process_data"
    )

    mocks_to_attach = {
        "connect_servo_ethercat_interface_ip": connect_servo_ethercat_interface_ip,
        "motor_enable": motor_enable,
        "create_pdo_item": create_pdo_item,
        "create_pdo_maps": create_pdo_maps,
        "set_pdo_maps_to_slave": set_pdo_maps_to_slave,
        "subscribe_to_receive_process_data": subscribe_to_receive_process_data,
        "subscribe_to_send_process_data": subscribe_to_send_process_data,
        "activate_pdos": activate_pdos,
        "deactivate_pdos": deactivate_pdos,
        "motor_disable": motor_disable,
        "disconnect": disconnect,
    }
    order_mock = Mock()
    for mock_name, mock in mocks_to_attach.items():
        order_mock.attach_mock(mock, f"{mock_name}")

    assert order_mock.method_calls == []

    main_process_data_object()

    expected_order_execution = [
        "connect_servo_ethercat_interface_ip",
        "motor_enable",
        "create_pdo_item",
        "create_pdo_item",
        "create_pdo_maps",
        "subscribe_to_receive_process_data",
        "subscribe_to_send_process_data",
        "set_pdo_maps_to_slave",
        "activate_pdos",
        "deactivate_pdos",
        "motor_disable",
        "disconnect",
    ]
    for current_function, expected_function_name in enumerate(expected_order_execution):
        assert order_mock.method_calls[current_function][0] == expected_function_name


def test_commutation_test(mocker):
    connect_servo_ethercat_interface_ip = mocker.patch.object(
        Communication, "connect_servo_ethercat_interface_ip"
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    set_auxiliar_feedback = mocker.patch.object(Configuration, "set_auxiliar_feedback")
    set_commutation_feedback = mocker.patch.object(Configuration, "set_commutation_feedback")
    set_position_feedback = mocker.patch.object(Configuration, "set_position_feedback")
    set_velocity_feedback = mocker.patch.object(Configuration, "set_velocity_feedback")
    set_reference_feedback = mocker.patch.object(Configuration, "set_reference_feedback")
    commutation_test = mocker.patch.object(
        DriveTests,
        "commutation",
        return_value={
            "result_message": "Commutation is called",
            "result_severity": SeverityLevel.SUCCESS,
        },
    )

    main_commutation_test_encoders()

    connect_servo_ethercat_interface_ip.assert_called_once()
    set_auxiliar_feedback.assert_called_once()
    set_commutation_feedback.assert_called_once()
    set_position_feedback.assert_called_once()
    set_velocity_feedback.assert_called_once()
    set_reference_feedback.assert_called_once()
    commutation_test.assert_called_once()
    disconnect.assert_called_once()


def test_position_ramp(mocker, capsys):
    connect_servo_ethercat_interface_ip = mocker.patch.object(
        Communication, "connect_servo_ethercat_interface_ip"
    )
    disconnect = mocker.patch.object(Communication, "disconnect")
    set_max_profile_velocity = mocker.patch.object(Configuration, "set_max_profile_velocity")
    set_max_profile_acceleration = mocker.patch.object(
        Configuration, "set_max_profile_acceleration"
    )
    set_max_profile_deceleration = mocker.patch.object(
        Configuration, "set_max_profile_deceleration"
    )
    motor_enable = mocker.patch.object(Motion, "motor_enable")
    motor_disable = mocker.patch.object(Motion, "motor_disable")
    set_operation_mode = mocker.patch.object(Motion, "set_operation_mode")
    move_to_position = mocker.patch.object(Motion, "move_to_position")
    test_actual_values = [1500, 3000, 0]
    get_actual_position = mocker.patch.object(
        Motion, "get_actual_position", side_effect=test_actual_values
    )

    main_position_ramp()

    connect_servo_ethercat_interface_ip.assert_called_once()
    set_operation_mode.assert_called_once()
    set_max_profile_acceleration.assert_called_once()
    set_max_profile_deceleration.assert_called_once()
    set_max_profile_velocity.assert_called_once()
    motor_enable.assert_called_once()
    for current_target in test_actual_values:
        move_to_position.assert_any_call(current_target, blocking=True, timeout=2.0)
    assert move_to_position.call_count == len(test_actual_values)
    assert get_actual_position.call_count == len(test_actual_values)
    motor_disable.assert_called_once()
    disconnect.assert_called_once()

    captured_outputs = capsys.readouterr()
    all_outputs = captured_outputs.out.split("\n")
    for i, expected_actual_value in enumerate(test_actual_values):
        assert all_outputs[i] == f"Actual position: {expected_actual_value}"
