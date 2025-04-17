import importlib
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Optional

import numpy as np
import pytest
from ingenialink import CanBaudrate, CanDevice
from ping3 import ping
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from tests.setups.descriptors import (
    DriveCanOpenSetup,
    DriveEcatSetup,
    DriveEthernetSetup,
    DriveHwSetup,
    EthercatMultiSlaveSetup,
    Setup,
    VirtualDriveSetup,
)
from tests.setups.environment_control import (
    RackServiceEnvironmentController,
    VirtualDriveEnvironmentController,
)
from tests.setups.rack_service_client import RackServiceClient
from tests.setups.specifiers import RackServiceConfigSpecifier

# Pytest runs with importlib import mode, which means that it will run the tests with the installed
# version of the package. Therefore, modules that are not included in the package cannot be imported
# in the tests.
# The issue is solved by dynamically importing them before the tests start. All modules that should
# be imported and ARE NOT part of the package should be specified here
_DYNAMIC_MODULES_IMPORT = ["tests", "examples"]


def import_module_from_local_path(
    module_name: str, module_path: Path, add_to_sys_modules: bool = True
) -> Optional[ModuleType]:
    """Imports a module using a local path.

    Args:
        module_name: name that it will have in `sys.modules`.
        module_path: module path.
        add_to_sys_modules (bool, optional): True to add the module to `sys.modules`,
            False otherwise. Defaults to True.

    Returns:
        imported module, None if it can not be imported.
    """
    # Check if it is already loaded
    module = sys.modules.get(module_name)
    if module is not None and hasattr(module, "__file__") and Path(module.__file__) == module_path:
        return sys.modules[module_name]

    # Load the module and add it to sys modules if required
    if module_path.is_dir():
        module_name = module_path.name
        module_path /= "__init__.py"
        if not module_path.exists():
            return None
    else:
        module_name = module_path.stem

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if add_to_sys_modules:
        sys.modules[module_name] = module
    return module


def dynamic_loader(module_path: Path) -> None:
    """Dynamically loads the modules that are not part of the package.

    Should only be used if import mode is `importlib`.

    Args:
        module_path: path to the module to be loaded.

    Raises:
        RuntimeError: if the provided path is not a directory with a valid `__init__.py` file.
    """
    if not (module_path / "__init__.py").exists():
        raise RuntimeError("Only directories with init path can be added in the dynamic loader")

    import_module_from_local_path(module_name=module_path.name, module_path=module_path)

    # Import all the submodules and files from the indicated module
    for path in module_path.rglob("*"):
        if "__pycache__" in path.parts:
            continue  # Skip __pycache__ and its contents
        elif path.is_dir():
            if not (path / "__init__.py").exists():
                continue  # Ignore directories without init ifle
            sys_module_name = ".".join(path.relative_to(module_path).parts)
        elif path.suffix == ".py":
            if path.name == "__init__.py" or path.name.startswith("test_"):
                continue  # Skip init file and avoid including all tests as modules
            sys_module_name = ".".join(path.relative_to(module_path).with_suffix("").parts)
        else:
            continue

        import_module_from_local_path(module_name=sys_module_name, module_path=path)


test_report_key = pytest.StashKey[dict[str, pytest.CollectReport]]()

SLEEP_BETWEEN_POWER_CYCLE_S = 5


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
    parser.addoption(
        "--job_name",
        action="store",
        default="ingeniamotion - Unknown",
        help="Name of the executing job. Will be set to rack service to have more info of the logs",
    )


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


@pytest.fixture(scope="session")
def tests_setup(request) -> Setup:
    setup_location = Path(request.config.getoption("--setup").replace(".", "/"))
    setup_module = import_module_from_local_path(
        module_name=setup_location.parent.name,
        module_path=setup_location.parent.with_suffix(".py").resolve(),
    )
    specifier = getattr(setup_module, setup_location.name)

    if isinstance(tests_setup, RackServiceConfigSpecifier):
        rack_service_client = request.getfixturevalue("connect_to_rack_service")
        specifier.rack_service_client = rack_service_client
    return specifier.get_descriptor()


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


def __connect_to_servo_with_protocol(mc, tests_setup, alias):
    if isinstance(tests_setup, DriveEcatSetup):
        connect_soem(mc, tests_setup, alias)
    elif isinstance(tests_setup, DriveCanOpenSetup):
        connect_canopen(mc, tests_setup, alias)
    elif isinstance(tests_setup, DriveEthernetSetup):
        connect_ethernet(mc, tests_setup, alias)
    else:
        raise NotImplementedError


@pytest.fixture(scope="session")
def motion_controller(tests_setup: Setup, request):
    alias = "test"
    mc = MotionController()

    if isinstance(tests_setup, DriveHwSetup):
        rack_service_client = request.getfixturevalue("connect_to_rack_service")
        drive_idx, drive = tests_setup.get_rack_drive(rack_service_client)
        environment = RackServiceEnvironmentController(
            rack_service_client, default_drive_idx=drive_idx
        )

        __connect_to_servo_with_protocol(mc, tests_setup, alias)

        if tests_setup.config_file is not None:
            mc.configuration.restore_configuration(servo=alias)
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)
        yield mc, alias, environment
        environment.reset()
        mc.communication.disconnect(alias)

    elif isinstance(tests_setup, EthercatMultiSlaveSetup):
        environment = RackServiceEnvironmentController(
            request.getfixturevalue("connect_to_rack_service")
        )

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
        connect_ethernet(mc, tests_setup, alias)
        environment = VirtualDriveEnvironmentController(virtual_drive.environment)

        yield mc, alias, environment

        environment.reset()
        virtual_drive.stop()
    else:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def disable_motor_fixture(motion_controller, tests_setup):
    yield

    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(motion_controller, tests_setup: Setup):
    yield motion_controller
    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)
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
def load_configuration_if_test_fails(request, motion_controller, tests_setup: Setup):
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
def load_configuration_after_each_module(motion_controller, tests_setup: Setup):
    yield motion_controller

    if isinstance(tests_setup, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if tests_setup.config_file is not None:
            mc.configuration.load_configuration(tests_setup.config_file, servo=alias)


@pytest.fixture(scope="session")
def connect_to_rack_service(request):
    rack_service_client = RackServiceClient(job_name=request.config.getoption("--job_name"))
    yield rack_service_client.client
    rack_service_client.close()


@pytest.fixture(scope="session", autouse=True)
def load_firmware(tests_setup: Setup, request):
    if not isinstance(tests_setup, DriveHwSetup):
        return

    client = request.getfixturevalue("connect_to_rack_service")
    number_of_drives = len(client.configuration.drives)

    # Reboot drive
    client.turn_off_ps()
    time.sleep(SLEEP_BETWEEN_POWER_CYCLE_S)
    client.turn_on_ps()

    # Wait for all drives to turn-on, for 90 seconds
    timeout = 90
    wait_until = time.time() + timeout
    mc = MotionController()
    while True:
        if time.time() >= wait_until:
            raise TimeoutError(f"Could not find drives in {timeout} after rebooting")

        if isinstance(tests_setup, DriveEcatSetup):
            n_found = len(mc.communication.scan_servos_ethercat(tests_setup.ifname))
            if n_found == number_of_drives:
                break
        elif isinstance(tests_setup, DriveCanOpenSetup):
            # Temporal workaround
            # Canopen transceiver setup generates BUS-off errors when scanning servos
            # Until the transceiver is not changed or a better method is implemented on rack service
            # it will wait for some time and assume they are connected
            time.sleep(60)
            break
        elif isinstance(tests_setup, DriveEthernetSetup):
            ping_result = ping(dest_addr=tests_setup.ip)
            # The response delay in seconds/milliseconds, False on error and None on timeout.
            if isinstance(ping_result, float):
                break
        else:
            raise NotImplementedError

    # Load firmware (if necessary, if it's already loaded it will do nothing)
    drive_idx, drive = tests_setup.get_rack_drive(client)
    client.firmware_load(drive_idx, tests_setup.fw_file, drive.product_code, drive.serial_number)
