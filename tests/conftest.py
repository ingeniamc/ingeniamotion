import time
from pathlib import Path

import numpy as np
import pytest
from ingenialink import CanBaudrate, CanDevice
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from tests.tests_toolkit import dynamic_loader
from tests.tests_toolkit.setups.descriptors import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    DriveHwSetup,
    EthercatMultiSlaveSetup,
    SetupDescriptor,
    VirtualDriveSetup,
)
from tests.tests_toolkit.setups.environment_control import (
    ManualUserEnvironmentController,
    RackServiceEnvironmentController,
    VirtualDriveEnvironmentController,
)
from tests.tests_toolkit.setups.specifiers import (
    LocalDriveConfigSpecifier,
    MultiLocalDriveConfigSpecifier,
    MultiRackServiceConfigSpecifier,
    SetupSpecifier,
)

pytest_plugins = [
    "tests.tests_toolkit.pytest_addoptions",
    "tests.tests_toolkit.setup_fixtures",
]

# Pytest runs with importlib import mode, which means that it will run the tests with the installed
# version of the package. Therefore, modules that are not included in the package cannot be imported
# in the tests.
# The issue is solved by dynamically importing them before the tests start. All modules that should
# be imported and ARE NOT part of the package should be specified here
_DYNAMIC_MODULES_IMPORT = ["tests", "examples"]

test_report_key = pytest.StashKey[dict[str, pytest.CollectReport]]()


def pytest_sessionstart(session):
    """Loads the modules that are not part of the package if import mode is importlib.

    Args:
        session: session.
    """
    if session.config.option.importmode != "importlib":
        return
    ingeniamotion_base_path = Path(__file__).parents[1]
    for module_name in _DYNAMIC_MODULES_IMPORT:
        dynamic_loader((ingeniamotion_base_path / module_name).resolve())


def connect_ethernet(mc, config, alias):
    mc.communication.connect_servo_ethernet(config.ip, config.dictionary, alias=alias)


def connect_soem(mc, config: DriveEcatSetup, alias):
    mc.communication.connect_servo_ethercat(
        config.ifname,
        config.slave,
        config.dictionary,
        alias,
    )


def connect_canopen(mc, config: DriveCanOpenSetup, alias):
    device = CanDevice(config.device)
    baudrate = CanBaudrate(config.baudrate)
    mc.communication.connect_servo_canopen(
        device,
        config.dictionary,
        config.node_id,
        baudrate,
        config.channel,
        alias=alias,
    )


def __connect_to_servo_with_protocol(mc, descriptor, alias):
    if isinstance(descriptor, DriveEcatSetup):
        connect_soem(mc, descriptor, alias)
    elif isinstance(descriptor, DriveCanOpenSetup):
        connect_canopen(mc, descriptor, alias)
    elif isinstance(descriptor, DriveEthernetSetup):
        connect_ethernet(mc, descriptor, alias)
    else:
        raise NotImplementedError


@pytest.fixture(scope="session")
def motion_controller(
    setup_specifier: SetupSpecifier, setup_descriptor: SetupDescriptor, pytestconfig, request
):
    alias = "test"
    mc = MotionController()

    if isinstance(setup_descriptor, DriveHwSetup):
        if isinstance(setup_specifier, (LocalDriveConfigSpecifier, MultiLocalDriveConfigSpecifier)):
            environment = ManualUserEnvironmentController(pytestconfig)
        else:
            client = request.getfixturevalue("connect_to_rack_service")
            environment = RackServiceEnvironmentController(
                client.client,
                default_drive_idx=setup_descriptor.rack_drive_idx,
            )

        __connect_to_servo_with_protocol(mc, setup_descriptor, alias)

        if setup_descriptor.config_file is not None:
            mc.configuration.restore_configuration(servo=alias)
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)
        yield mc, alias, environment
        environment.reset()
        mc.communication.disconnect(alias)

    elif isinstance(setup_descriptor, EthercatMultiSlaveSetup):
        if isinstance(setup_specifier, (LocalDriveConfigSpecifier, MultiLocalDriveConfigSpecifier)):
            environment = ManualUserEnvironmentController(pytestconfig)
        else:
            client = request.getfixturevalue("connect_to_rack_service")
            environment = RackServiceEnvironmentController(client.client)

        aliases = []
        for drive in setup_descriptor.drives:
            mc.communication.connect_servo_ethercat(
                interface_name=drive.ifname,
                slave_id=drive.slave,
                dict_path=drive.dictionary,
                alias=drive.identifier,
            )
            aliases.append(drive.identifier)

        yield mc, aliases, environment
        environment.reset()

    elif isinstance(setup_descriptor, VirtualDriveSetup):
        virtual_drive = VirtualDrive(setup_descriptor.port, setup_descriptor.dictionary)
        virtual_drive.start()
        connect_ethernet(mc, setup_descriptor, alias)
        environment = VirtualDriveEnvironmentController(virtual_drive.environment)

        yield mc, alias, environment

        environment.reset()
        virtual_drive.stop()
    else:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def disable_motor_fixture(motion_controller, setup_descriptor):
    yield

    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, setup_descriptor: SetupDescriptor):
    yield motion_controller
    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if setup_descriptor.config_file is not None:
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def disable_monitoring_disturbance(skip_if_monitoring_not_available, motion_controller):  # noqa: ARG001
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
def pytest_runtest_makereport(item):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # store test results for each phase of a call, which can be "setup", "call", "teardown"
    item.stash.setdefault(test_report_key, {})[rep.when] = rep


@pytest.fixture(scope="function", autouse=True)
def load_configuration_if_test_fails(request, motion_controller, setup_descriptor: SetupDescriptor):
    mc, alias, environment = motion_controller
    yield

    report = request.node.stash[test_report_key]

    if isinstance(setup_descriptor, DriveHwSetup) and (
        report["setup"].failed or ("call" not in report) or report["call"].failed
    ):
        if setup_descriptor.config_file is not None:
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)
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
def load_configuration_after_each_module(motion_controller, setup_descriptor: SetupDescriptor):
    yield motion_controller

    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if setup_descriptor.config_file is not None:
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)


def __load_fw_with_protocol(mc, descriptor):
    if isinstance(descriptor, DriveEcatSetup):
        mc.communication.load_firmware_ecat(
            ifname=descriptor.ifname,
            fw_file=descriptor.fw_file,
            slave=descriptor.slave,
            boot_in_app=descriptor.boot_in_app,
        )
    elif isinstance(descriptor, DriveCanOpenSetup):
        mc.communication.load_firmware_canopen(fw_file=descriptor.fw_file)
    elif isinstance(descriptor, DriveEthernetSetup):
        mc.communication.load_firmware_ethernet(ip=descriptor.ip, fw_file=descriptor.fw_file)
    else:
        raise NotImplementedError(
            f"Firmware loading not implemented for descriptor {type(descriptor)}"
        )


@pytest.fixture(scope="session", autouse=True)
def load_firmware(setup_specifier: SetupSpecifier, setup_descriptor: SetupDescriptor, request):
    if isinstance(setup_descriptor, VirtualDriveSetup):
        return

    if isinstance(setup_specifier, (LocalDriveConfigSpecifier, MultiLocalDriveConfigSpecifier)):
        mc = MotionController()
        descriptors = (
            setup_descriptor.drives
            if isinstance(setup_specifier, MultiLocalDriveConfigSpecifier)
            else [setup_descriptor]
        )
        for descriptor in descriptors:
            __load_fw_with_protocol(mc=mc, descriptor=descriptor)
        return

    client = request.getfixturevalue("connect_to_rack_service")
    client.power_cycle()  # Reboot drive

    # Load firmware (if necessary, if it's already loaded it will do nothing)
    descriptors = (
        setup_descriptor.drives
        if isinstance(setup_specifier, MultiRackServiceConfigSpecifier)
        else [setup_descriptor]
    )
    for descriptor in descriptors:
        client.client.firmware_load(
            descriptor.rack_drive_idx,
            descriptor.fw_file.as_posix(),
            descriptor.rack_drive.product_code,
            descriptor.rack_drive.serial_number,
        )
