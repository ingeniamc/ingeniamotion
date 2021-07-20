import json
import pytest

from ingeniamotion import MotionController


def pytest_addoption(parser):
    parser.addoption("--protocol", action="store", default="eoe",
                     help="eoe, soem")


@pytest.fixture(autouse=True)
def read_config():
    config = 'tests/config.json'
    print('current config file:', config)
    with open(config, "r") as fp:
        contents = json.load(fp)
    pytest.config = contents


@pytest.fixture
def motion_controller():
    return MotionController()


def connect_eoe(mc, alias=None):
    config = pytest.config["eoe"]
    if alias is None:
        mc.communication.connect_servo_eoe(
            config["ip"], config["dictionary"])
    else:
        mc.communication.connect_servo_eoe(
            config["ip"], config["dictionary"], alias="test")


def connect_soem_eoe(mc, alias=None):
    config = pytest.config["soem"]
    if alias is None:
        mc.communication.connect_servo_ecat_interface_index(
            config["index"], config["dictionary"], config["slave"])
    else:
        mc.communication.connect_servo_ecat_interface_index(
            config["index"], config["dictionary"],
            config["slave"], alias="test")


@pytest.fixture
def servo_default(motion_controller, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "eoe":
        connect_eoe(motion_controller)
    elif protocol == "soem":
        connect_soem_eoe(motion_controller)
    return motion_controller


@pytest.fixture
def servo_test_name(motion_controller, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "eoe":
        connect_eoe(motion_controller, "test")
    elif protocol == "soem":
        connect_soem_eoe(motion_controller, "test")
    return motion_controller
