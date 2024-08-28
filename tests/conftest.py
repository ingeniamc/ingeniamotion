import json
import os
import time
from typing import Dict

import numpy as np
import pytest
import rpyc
from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType

from .setup.descriptors import (
    CanOpenSetup,
    Configs,
    EoESetup,
    HwSetup,
    Setup,
    SoemSetup,
    VirtualDriveSetup,
)

ALLOW_PROTOCOLS = ["eoe", "soem", "canopen", "virtual"]

test_report_key = pytest.StashKey[Dict[str, pytest.CollectReport]]()


def pytest_addoption(parser):
    parser.addoption(
        "--protocol", action="store", default="eoe", help="eoe, soem", choices=ALLOW_PROTOCOLS
    )
    parser.addoption("--slave", type="int", default=0, help="Slave index in config.json")


@pytest.fixture(scope="session")
def read_config(request):
    config = "tests/config.json"
    with open(config, "r") as fp:
        contents = json.load(fp)
        data = Configs.from_dict(contents)

    slave = request.config.getoption("--slave")
    protocol = request.config.getoption("--protocol")

    setup = data.protocols[protocol].setups[slave]
    if isinstance(setup, VirtualDriveSetup):
        setup.dictionary = os.path.join(os.path.abspath(os.getcwd()), setup.dictionary)

    return data.protocols[protocol].setups[slave]


def connect_eoe(mc, config, alias):
    mc.communication.connect_servo_eoe(config.ip, config.dictionary, alias=alias)


def connect_soem(mc, config: SoemSetup, alias):
    mc.communication.connect_servo_ethercat(
        config.ifname,
        config.slave,
        config.dictionary,
        alias,
    )


def connect_canopen(mc, config: CanOpenSetup, alias):
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
def motion_controller(read_config: Setup):
    alias = "test"
    mc = MotionController()

    if isinstance(read_config, SoemSetup):
        connect_soem(mc, read_config, alias)
    elif isinstance(read_config, CanOpenSetup):
        connect_canopen(mc, read_config, alias)
    elif isinstance(read_config, VirtualDriveSetup):
        virtual_drive = VirtualDrive(read_config.port, read_config.dictionary)
        virtual_drive.start()
        virtual_drive.set_value_by_id(1, "IO_IN_VALUE", 0xA)
        connect_eoe(mc, read_config, alias)
    elif isinstance(read_config, EoESetup):
        connect_eoe(mc, read_config, alias)
    else:
        raise NotImplementedError

    if isinstance(read_config, HwSetup):
        mc.configuration.restore_configuration(servo=alias)
        mc.configuration.load_configuration(read_config.config_file, servo=alias)
        yield mc, alias
        mc.communication.disconnect(alias)
    elif isinstance(read_config, VirtualDriveSetup):
        yield mc, alias
        virtual_drive.stop()
    else:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def disable_motor_fixture(pytestconfig, motion_controller):
    yield
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "virtual":
        mc, alias = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, read_config: Setup):
    yield motion_controller
    if isinstance(read_config, HwSetup):
        mc, alias = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.configuration.load_configuration(read_config.config_file, servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def disable_monitoring_disturbance(motion_controller):
    yield
    mc, alias = motion_controller
    mc.capture.clean_monitoring_disturbance(servo=alias)


@pytest.fixture(scope="session")
def feedback_list(motion_controller):
    mc, alias = motion_controller
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
    mc, alias = motion_controller
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
    mc, alias = motion_controller
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
def load_configuration_if_test_fails(pytestconfig, request, motion_controller, read_config: Setup):
    mc, alias = motion_controller
    yield

    report = request.node.stash[test_report_key]
    protocol = pytestconfig.getoption("--protocol")
    if isinstance(read_config, HwSetup) and (
        report["setup"].failed or ("call" not in report) or report["call"].failed
    ):
        mc.configuration.load_configuration(read_config.config_file, servo=alias)
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
def load_configuration_after_each_module(pytestconfig, motion_controller, read_config: Setup):
    yield motion_controller

    if isinstance(read_config, HwSetup):
        mc, alias = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.configuration.load_configuration(read_config.config_file, servo=alias)


@pytest.fixture(scope="session")
def connect_to_rack_service():
    rack_service_port = 33810
    client = rpyc.connect("localhost", rack_service_port, config={"sync_request_timeout": None})
    yield client.root
    client.close()


@pytest.fixture(scope="session", autouse=True)
def load_firmware(pytestconfig, read_config: Setup, request):
    if not isinstance(read_config, HwSetup):
        return

    if not read_config.load_firmware_with_rack_service:
        return

    drive_identifier = read_config.identifier
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
        drive_idx, read_config.fw_file, drive.product_code, drive.serial_number
    )
