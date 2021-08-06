import json
import pytest

from ingenialink.canopen import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion import MotionController

ALLOW_PROTOCOLS = ["eoe", "soem", "canopen"]


def pytest_addoption(parser):
    parser.addoption("--protocol", action="store", default="eoe",
                     help="eoe, soem", choices=ALLOW_PROTOCOLS)


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
def read_config():
    config = 'tests/config.json'
    print('current config file:', config)
    with open(config, "r") as fp:
        contents = json.load(fp)
    return contents


def connect_eoe(mc, config, alias):
    config_eoe = config["eoe"]
    mc.communication.connect_servo_eoe(
        config_eoe["ip"], config_eoe["dictionary"], alias=alias)


def connect_soem(mc, config, alias):
    config_soem = config["soem"]
    mc.communication.connect_servo_ecat_interface_index(
        config_soem["index"], config_soem["dictionary"],
        config_soem["slave"], eoe_comm=config_soem["eoe_comm"], alias=alias)


def connect_canopen(mc, config, alias):
    config_canopen = config["canopen"]
    device = CAN_DEVICE(config_canopen["device"])
    baudrate = CAN_BAUDRATE(config_canopen["baudrate"])
    mc.communication.connect_servo_canopen(
        device, config_canopen["dictionary"], config_canopen["eds"],
        config_canopen["node_id"], baudrate, config_canopen["channel"],
        alias=alias)


@pytest.fixture(scope="session")
def motion_controller(pytestconfig, read_config):
    alias = "test"
    mc = MotionController()
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "eoe":
        connect_eoe(mc, read_config, alias)
    elif protocol == "soem":
        connect_soem(mc, read_config, alias)
    elif protocol == "canopen":
        connect_canopen(mc, read_config, alias)
    mc.configuration.load_configuration(
        read_config[protocol]["config_file"], servo=alias)
    yield mc, alias
    if protocol == "canopen":
        mc.communication.disconnect_canopen(alias)


@pytest.fixture(autouse=True)
def disable_motor_fixture(motion_controller):
    yield
    mc, alias = motion_controller
    mc.motion.motor_disable(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, read_config):
    yield motion_controller
    protocol = pytestconfig.getoption("--protocol")
    mc, alias = motion_controller
    mc.configuration.load_configuration(
        read_config[protocol]["config_file"], servo=alias)
