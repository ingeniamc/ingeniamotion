import re
import time
from pathlib import Path

import numpy as np
import pytest
from packaging import version
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.drive_context_manager import DriveContextManager
from tests.tests_toolkit import dynamic_loader
from tests.tests_toolkit.network_utils import connect_ethernet, connect_to_servo_with_protocol
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


# TODO: remove
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

        connect_to_servo_with_protocol(mc, setup_descriptor, alias)

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


@pytest.fixture
def disable_monitoring_disturbance(skip_if_monitoring_not_available, motion_controller):  # noqa: ARG001
    yield
    mc, alias, environment = motion_controller
    mc.capture.clean_monitoring_disturbance(servo=alias)


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


# TODO: remove
def _read_fw_version(alias: str, motion_controller: MotionController):
    _, _, fw_version, _ = motion_controller.configuration.get_drive_info_coco_moco(servo=alias)
    return fw_version


def is_fw_already_uploaded(alias: str, mc: MotionController, firmware_file: Path) -> bool:
    current_fw_version = _read_fw_version(alias=alias, motion_controller=mc)[0]
    match = re.search(r"_(\d+\.\d+\.\d+)", firmware_file.stem)
    if match is None:
        return False
    file_fw_version = match.group(1)
    try:
        return version.parse(file_fw_version) == version.parse(current_fw_version)
    except version.InvalidVersion:
        return False


def __load_fw_with_protocol(mc: MotionController, descriptor: SetupDescriptor, alias: str):
    if is_fw_already_uploaded(alias=alias, mc=mc, firmware_file=descriptor.fw_file):
        return
    if isinstance(descriptor, DriveEcatSetup):
        mc.communication.load_firmware_ecat(
            ifname=descriptor.ifname,
            fw_file=descriptor.fw_file.as_posix(),
            slave=descriptor.slave,
            boot_in_app=descriptor.boot_in_app,
        )
    elif isinstance(descriptor, DriveCanOpenSetup):
        mc.communication.load_firmware_canopen(fw_file=descriptor.fw_file.as_posix(), servo=alias)
    elif isinstance(descriptor, DriveEthernetSetup):
        mc.communication.load_firmware_ethernet(
            ip=descriptor.ip, fw_file=descriptor.fw_file.as_posix()
        )
    else:
        raise NotImplementedError(
            f"Firmware loading not implemented for descriptor {type(descriptor)}"
        )


# TODO: remove
@pytest.fixture(scope="session", autouse=True)
def load_firmware(setup_specifier: SetupSpecifier, setup_descriptor: SetupDescriptor, request):
    if isinstance(setup_descriptor, VirtualDriveSetup):
        return

    if isinstance(setup_specifier, (LocalDriveConfigSpecifier, MultiLocalDriveConfigSpecifier)):
        mc = MotionController()
        if isinstance(setup_specifier, MultiLocalDriveConfigSpecifier):
            descriptors = setup_descriptor.drives
            aliases = [drive.identifier for drive in setup_descriptor.drives]
        else:
            descriptors = [setup_descriptor]
            aliases = ["test"]
        for descriptor, alias in zip(descriptors, aliases):
            connect_to_servo_with_protocol(mc, setup_descriptor, alias)
            __load_fw_with_protocol(mc=mc, descriptor=descriptor, alias=alias)
            mc.communication.disconnect(alias)
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


@pytest.fixture
def drive_context_manager(motion_controller):
    """Drive context manager.

    It is in charge of returning the drive to the values it had before the tests,
    if the test alters it."""
    mc, aliases, _ = motion_controller
    if isinstance(aliases, str):
        aliases = [aliases]

    context_managers = [DriveContextManager(mc, alias) for alias in aliases]
    for context_manager in context_managers:
        context_manager.__enter__()
    yield
    for context_manager in context_managers:
        context_manager.__exit__(None, None, None)
