import json
import os
import time
from typing import Dict

import numpy as np
import pytest
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE, SensorType

ALLOW_PROTOCOLS = ["eoe", "soem", "canopen", "virtual"]

test_report_key = pytest.StashKey[Dict[str, pytest.CollectReport]]()


def pytest_addoption(parser):
    parser.addoption(
        "--protocol", action="store", default="eoe", help="eoe, soem", choices=ALLOW_PROTOCOLS
    )
    parser.addoption("--slave", type="int", default=0, help="Slave index in config.json")


def pytest_collection_modifyitems(config, items):
    protocol = config.getoption("--protocol")
    negate_protocols = [x for x in ALLOW_PROTOCOLS if x != protocol]
    skip_by_protocol = pytest.mark.skip(reason="Protocol does not match")
    for item in items:
        if protocol in item.keywords:
            continue
        for not_protocol in negate_protocols:
            if not_protocol in item.keywords:
                item.add_marker(skip_by_protocol)


@pytest.fixture(scope="session")
def read_config(request):
    slave = request.config.getoption("--slave")
    protocol = request.config.getoption("--protocol")
    config = "tests/config.json"
    with open(config, "r") as fp:
        contents = json.load(fp)
    relative_path = contents["virtual"][0]["dictionary"]
    absolute_path = os.path.join(os.path.abspath(os.getcwd()), relative_path)
    contents["virtual"][0]["dictionary"] = absolute_path
    return contents[protocol][slave]


def connect_eoe(mc, config, alias):
    mc.communication.connect_servo_eoe(config["ip"], config["dictionary"], alias=alias)


def connect_soem(mc, config, alias):
    mc.communication.connect_servo_ethercat_interface_index(
        config["index"],
        config["slave"],
        config["dictionary"],
        alias,
    )


def connect_canopen(mc, config, alias):
    device = CAN_DEVICE(config["device"])
    baudrate = CAN_BAUDRATE(config["baudrate"])
    mc.communication.connect_servo_canopen(
        device,
        config["dictionary"],
        config["node_id"],
        baudrate,
        config["channel"],
        alias=alias,
    )


@pytest.fixture(scope="session")
def motion_controller(pytestconfig, read_config):
    alias = "test"
    mc = MotionController()
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "soem":
        connect_soem(mc, read_config, alias)
    elif protocol == "canopen":
        connect_canopen(mc, read_config, alias)
    elif protocol == "virtual":
        virtual_drive = VirtualDrive(read_config["port"], read_config["dictionary"])
        virtual_drive.start()
        connect_eoe(mc, read_config, alias)
    else:
        connect_eoe(mc, read_config, alias)

    if protocol != "virtual":
        mc.configuration.load_configuration(read_config["config_file"], servo=alias)
        yield mc, alias
        mc.communication.disconnect(alias)
    else:
        yield mc, alias
        virtual_drive.stop()


@pytest.fixture(autouse=True)
def disable_motor_fixture(pytestconfig, motion_controller):
    yield
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "virtual":
        mc, alias = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, read_config):
    yield motion_controller
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "virtual":
        return
    mc, alias = motion_controller
    mc.motion.motor_disable(servo=alias)
    mc.configuration.load_configuration(read_config["config_file"], servo=alias)
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
def load_configuration_if_test_fails(pytestconfig, request, motion_controller, read_config):
    mc, alias = motion_controller
    yield

    report = request.node.stash[test_report_key]
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "virtual" and (
        report["setup"].failed or ("call" not in report) or report["call"].failed
    ):
        mc.configuration.load_configuration(read_config["config_file"], servo=alias)
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
def load_configuration_after_each_module(pytestconfig, motion_controller, read_config):
    yield motion_controller
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "virtual":
        mc, alias = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.configuration.load_configuration(read_config["config_file"], servo=alias)
