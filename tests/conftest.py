import json
import pytest

from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE, SensorType
from ingeniamotion import MotionController

ALLOW_PROTOCOLS = ["eoe", "soem", "canopen"]


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
    return contents[protocol][slave]


def connect_eoe(mc, config, alias):
    mc.communication.connect_servo_eoe(config["ip"], config["dictionary"], alias=alias)


def connect_soem(mc, config, alias):
    mc.communication.connect_servo_ecat_interface_index(
        config["index"],
        config["dictionary"],
        config["slave"],
        eoe_comm=config["eoe_comm"],
        alias=alias,
    )


def connect_canopen(mc, config, alias):
    device = CAN_DEVICE(config["device"])
    baudrate = CAN_BAUDRATE(config["baudrate"])
    mc.communication.connect_servo_canopen(
        device,
        config["dictionary"],
        config["eds"],
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
    if protocol == "eoe":
        connect_eoe(mc, read_config, alias)
    elif protocol == "soem":
        connect_soem(mc, read_config, alias)
    elif protocol == "canopen":
        connect_canopen(mc, read_config, alias)
    mc.configuration.load_configuration(read_config["config_file"], servo=alias)
    yield mc, alias
    mc.communication.disconnect(alias)


@pytest.fixture(autouse=True)
def disable_motor_fixture(motion_controller):
    yield
    mc, alias = motion_controller
    mc.motion.motor_disable(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, pytestconfig, read_config):
    yield motion_controller
    mc, alias = motion_controller
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
def commutation_teardown(motion_controller):
    yield
    mc, alias = motion_controller
    mc.tests.commutation(servo=alias)


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
