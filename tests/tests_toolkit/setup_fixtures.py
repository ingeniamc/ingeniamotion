from pathlib import Path

import pytest
from virtual_drive.core import VirtualDrive

from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from tests.tests_toolkit import import_module_from_local_path
from tests.tests_toolkit.network_utils import (
    connect_ethernet,
    connect_to_servo_with_protocol,
    load_firmware_with_protocol,
)
from tests.tests_toolkit.rack_service_client import RackServiceClient
from tests.tests_toolkit.setups import (
    DriveHwSetup,
    EthercatMultiSlaveSetup,
    LocalDriveConfigSpecifier,
    MultiLocalDriveConfigSpecifier,
    MultiRackServiceConfigSpecifier,
    RackServiceConfigSpecifier,
    SetupDescriptor,
    SetupSpecifier,
    VirtualDriveSetup,
    descriptor_from_specifier,
)
from tests.tests_toolkit.setups.environment_control import (
    ManualUserEnvironmentController,
    RackServiceEnvironmentController,
    VirtualDriveEnvironmentController,
)


@pytest.fixture(scope="session")
def connect_to_rack_service(request):
    rack_service_client = RackServiceClient(job_name=request.config.getoption("--job_name"))
    yield rack_service_client
    rack_service_client.teardown()


@pytest.fixture(scope="session")
def setup_specifier(request) -> SetupSpecifier:
    setup_location = Path(request.config.getoption("--setup").replace(".", "/"))
    setup_module = import_module_from_local_path(
        module_name=setup_location.parent.name,
        module_path=setup_location.parent.with_suffix(".py").resolve(),
    )
    return getattr(setup_module, setup_location.name)


@pytest.fixture(scope="session")
def setup_descriptor(setup_specifier, request) -> SetupSpecifier:
    if isinstance(setup_specifier, (RackServiceConfigSpecifier, MultiRackServiceConfigSpecifier)):
        rack_service_client = request.getfixturevalue("connect_to_rack_service")
    else:
        rack_service_client = None

    return descriptor_from_specifier(
        specifier=setup_specifier, rack_service_client=rack_service_client
    )


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


@pytest.fixture(autouse=True)
def disable_motor_fixture(motion_controller: MotionController, setup_descriptor: SetupDescriptor):
    yield

    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        mc.motion.fault_reset(servo=alias)


@pytest.fixture
def motion_controller_teardown(
    motion_controller: MotionController, setup_descriptor: SetupDescriptor
):
    yield motion_controller
    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if setup_descriptor.config_file is not None:
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)
        mc.motion.fault_reset(servo=alias)


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


@pytest.fixture(scope="module", autouse=True)
def load_configuration_after_each_module(motion_controller, setup_descriptor: SetupDescriptor):
    yield motion_controller

    if isinstance(setup_descriptor, DriveHwSetup):
        mc, alias, environment = motion_controller
        mc.motion.motor_disable(servo=alias)
        if setup_descriptor.config_file is not None:
            mc.configuration.load_configuration(setup_descriptor.config_file, servo=alias)


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
            load_firmware_with_protocol(mc=mc, descriptor=descriptor, alias=alias)
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
        load_firmware_args = {
            "drive_idx": descriptor.rack_drive_idx,
            "product_code": descriptor.rack_drive.product_code,
            "serial_number": descriptor.rack_drive.serial_number,
        }
        if isinstance(descriptor.fw_file, Path):
            load_firmware_args["file"] = descriptor.fw_file.as_posix()
        else:
            load_firmware_args["revision_number"] = descriptor.fw_file
        client.client.firmware_load(**load_firmware_args)
