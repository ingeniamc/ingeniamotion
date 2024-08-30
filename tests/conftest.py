import importlib
import time
from typing import Dict

import numpy as np
import pytest
import rpyc
from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from .setups.descriptors import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    DriveHwSetup,
    EthercatMultiSlaveSetup,
    Setup,
    VirtualDriveSetup,
)
from .setups.environment_control import (
    ManualUserEnvironmentController,
    RackServiceEnvironmentController,
    VirtualDriveEnvironmentController,
)

test_report_key = pytest.StashKey[Dict[str, pytest.CollectReport]]()


def pytest_addoption(parser):
    parser.addoption(
        "--setup",
        action="store",
        default="tests.setups.tests_setup.TESTS_SETUP",
        help="Module and location from which to import the setup."
        "It will default to a file that you can create on"
        "tests_setup.py inside of the folder setups with a variable called TESTS_SETUP"
        "This variable must define, or must be assigned to a Setup instance",
    )


@pytest.fixture(scope="session")
def tests_setup(request) -> Setup:
    # Get option from argument and split by dots (modules and last variable name)
    setup_location = request.config.getoption("--setup").split(".")
    # Dynamically import the python module
    setup_module = importlib.import_module(".".join(setup_location[:-1]))
    # Get the variable by variable name
    setup = getattr(setup_module, setup_location[-1])
    return setup


def connect_eoe(mc, config, alias):
    mc.communication.connect_servo_eoe(config.ip, config.dictionary, alias=alias)


def connect_soem(mc, config: DriveEcatSetup, alias):
    mc.communication.connect_servo_ethercat(
        config.ifname,
        config.slave,
        config.dictionary,
        alias,
    )


def connect_canopen(mc, config: DriveCanOpenSetup, alias):
    device = CAN_DEVICE(config.device)
    baudrate = CAN_BAUDRATE(config.baudrate)
    mc.communication.connect_servo_canopen(
        device,
        config.dictionary,
        config.node_id,
        baudrate,
        config.channel,
        alias=alias,
    )


@pytest.fixture(scope="session")
def motion_controller(tests_setup: Setup, pytestconfig):
    alias = "test"
    mc = MotionController()

    if isinstance(tests_setup, DriveHwSetup):
        if tests_setup.use_rack_service:
            environment = RackServiceEnvironmentController()
        else:
            environment = ManualUserEnvironmentController(pytestconfig)

        if isinstance(tests_setup, DriveEcatSetup):
            connect_soem(mc, tests_setup, alias)
        elif isinstance(tests_setup, DriveCanOpenSetup):
            connect_canopen(mc, tests_setup, alias)
        elif isinstance(tests_setup, DriveEthernetSetup):
            connect_eoe(mc, tests_setup, alias)
        else:
            raise NotImplementedError

        mc.configuration.restore_configuration(servo=alias)
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)
        yield mc, alias, environment
        environment.reset()
        mc.communication.disconnect(alias)

    elif isinstance(tests_setup, EthercatMultiSlaveSetup):
        if tests_setup.drives[0].use_rack_service:
            environment = RackServiceEnvironmentController()
        else:
            environment = ManualUserEnvironmentController(pytestconfig)

        aliases = []
        for drive in tests_setup.drives:
            mc.communication.connect_servo_ethercat(
                interface_name=drive.ifname,
                slave_id=drive.slave,
                dict_path=drive.dictionary,
                alias=drive.identifier,
            )
            aliases.append(drive.identifier)

        yield mc, aliases, environment
        environment.reset()
    elif isinstance(tests_setup, VirtualDriveSetup):
        virtual_drive = VirtualDrive(tests_setup.port, tests_setup.dictionary)
        virtual_drive.start()
        connect_eoe(mc, tests_setup, alias)
        environment = VirtualDriveEnvironmentController(virtual_drive)

        yield mc, alias, environment

        environment.reset()
        virtual_drive.stop()
    else:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def disable_motor_fixture(pytestconfig, motion_controller, tests_setup):
    yield

    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, tests_setup: Setup):
    yield motion_controller
    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def disable_monitoring_disturbance(motion_controller):
    yield
    mc, alias, environment = motion_controller
    mc.capture.clean_monitoring_disturbance(servo=alias)


@pytest.fixture(scope="session")
def feedback_list(motion_controller):
    mc, alias, environment = motion_controller
    fdbk_lst = [
        mc.configuration.get_commutation_feedback(servo=alias),
        mc.configuration.get_reference_feedback(servo=alias),
        mc.configuration.get_velocity_feedback(servo=alias),
        mc.configuration.get_position_feedback(servo=alias),
        mc.configuration.get_auxiliar_feedback(servo=alias),
    ]
    return set(fdbk_lst)


@pytest.fixture
def clean_and_restore_feedbacks(motion_controller):
    mc, alias, environment = motion_controller
    comm = mc.configuration.get_commutation_feedback(servo=alias)
    ref = mc.configuration.get_reference_feedback(servo=alias)
    vel = mc.configuration.get_velocity_feedback(servo=alias)
    pos = mc.configuration.get_position_feedback(servo=alias)
    aux = mc.configuration.get_auxiliar_feedback(servo=alias)
    mc.configuration.set_commutation_feedback(SensorType.INTGEN, servo=alias)
    mc.configuration.set_reference_feedback(SensorType.INTGEN, servo=alias)
    mc.configuration.set_velocity_feedback(SensorType.INTGEN, servo=alias)
    mc.configuration.set_position_feedback(SensorType.INTGEN, servo=alias)
    mc.configuration.set_auxiliar_feedback(SensorType.QEI, servo=alias)
    yield
    mc.configuration.set_commutation_feedback(comm, servo=alias)
    mc.configuration.set_reference_feedback(ref, servo=alias)
    mc.configuration.set_velocity_feedback(vel, servo=alias)
    mc.configuration.set_position_feedback(pos, servo=alias)
    mc.configuration.set_auxiliar_feedback(aux, servo=alias)


@pytest.fixture()
def skip_if_monitoring_not_available(motion_controller):
    mc, alias, environment = motion_controller
    try:
        mc.capture._check_version(alias)
    except NotImplementedError:
        pytest.skip("Monitoring is not available")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # store test results for each phase of a call, which can be "setup", "call", "teardown"
    item.stash.setdefault(test_report_key, {})[rep.when] = rep


@pytest.fixture(scope="function", autouse=True)
def load_configuration_if_test_fails(pytestconfig, request, motion_controller, tests_setup: Setup):
    mc, alias, environment = motion_controller
    yield

    report = request.node.stash[test_report_key]

    if isinstance(tests_setup, DriveHwSetup) and (
        report["setup"].failed or ("call" not in report) or report["call"].failed
    ):
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)
        mc.motion.fault_reset(servo=alias)


def mean_actual_velocity_position(mc, servo, velocity=False, n_samples=200, sampling_period=0):
    samples = np.zeros(n_samples)
    get_actual_value_dict = {
        True: mc.motion.get_actual_velocity,
        False: mc.motion.get_actual_position,
    }
    for sample_idx in range(n_samples):
        value = get_actual_value_dict[velocity](servo=servo)
        samples[sample_idx] = value
        time.sleep(sampling_period)
    return np.mean(samples)


@pytest.fixture(scope="module", autouse=True)
def load_configuration_after_each_module(pytestconfig, motion_controller, tests_setup: Setup):
    yield motion_controller

    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)


@pytest.fixture(scope="session")
def connect_to_rack_service():
    rack_service_port = 33810
    client = rpyc.connect("localhost", rack_service_port, config={"sync_request_timeout": None})
    yield client.root
    client.close()


@pytest.fixture(scope="session", autouse=True)
def load_firmware(pytestconfig, tests_setup: Setup, request):
    if not isinstance(tests_setup, DriveHwSetup):
        return

    if not tests_setup.use_rack_service:
        return

    drive_identifier = tests_setup.identifier
    drive_idx = None
    client = request.getfixturevalue("connect_to_rack_service")
    config = client.exposed_get_configuration()
    for idx, drive in enumerate(config.drives):
        if drive_identifier == drive.identifier:
            drive_idx = idx
            break
    if drive_idx is None:
        pytest.fail(f"The drive {drive_identifier} cannot be found on the rack's configuration.")
    drive = config.drives[drive_idx]
    client.exposed_turn_on_ps()
    client.exposed_firmware_load(
        drive_idx, tests_setup.fw_file, drive.product_code, drive.serial_number
    )
