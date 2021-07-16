import json
import pytest

from ingeniamotion import MotionController


def pytest_addoption(parser):
    parser.addoption("--protocol", action="store", default="eoe",
                     help="eoe, soem", choices=['eoe', 'soem'])


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


def connect_soem_eoe(mc, config, alias):
    config_soem = config["soem"]
    mc.communication.connect_servo_ecat_interface_index(
        config_soem["index"], config_soem["dictionary"],
        config_soem["slave"], alias=alias)


@pytest.fixture(scope="session")
def motion_controller(pytestconfig, read_config):
    alias = "test"
    mc = MotionController()
    protocol = pytestconfig.getoption("--protocol")
    if protocol == "eoe":
        connect_eoe(mc, read_config, alias)
    elif protocol == "soem":
        connect_soem_eoe(mc, read_config, alias)
    mc.configuration.load_configuration(
        read_config[protocol]["config_file"], servo=alias)
    return mc, alias


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, read_config):
    yield motion_controller
    protocol = pytestconfig.getoption("--protocol")
    mc, alias = motion_controller
    mc.configuration.load_configuration(
        read_config[protocol]["config_file"], servo=alias)
