import dataclasses
import random
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from summit_testing_framework import ATTFileType
from summit_testing_framework.setups.specifiers import (
    DriveHwConfigSpecifier,
    FirmwareVersion,
    LocalDriveConfigSpecifier,
    RackServiceConfigSpecifier,
)

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from tests.outputs import OUTPUTS_DIR

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import (
    TIMEOUT_FOR_DATA,
    TIMEOUT_FOR_DATA_SRA,
    fsoe_error_monitor,  # noqa: F401
    fsoe_states,  # noqa: F401
    mc_with_fsoe,  # noqa: F401
    mc_with_fsoe_factory,  # noqa: F401
    mc_with_fsoe_with_sra,  # noqa: F401
    mcu_error_queue_a,  # noqa: F401
    mcu_error_queue_b,  # noqa: F401
)

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.errors import (
        MCUA_ERROR_QUEUE,
        MCUB_ERROR_QUEUE,
        ServoErrorQueue,
    )
    from tests.fsoe.map_generator import FSoERandomMappingGenerator

if TYPE_CHECKING:
    from ingenialink import Servo
    from summit_testing_framework.att import ATTApi
    from summit_testing_framework.rack_service_client import RackServiceClient
    from summit_testing_framework.setups.descriptors import DriveHwSetup

    from ingeniamotion.motion_controller import MotionController

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

__EXTRA_DATA_ESI_FILE_KEY: str = "esi_file"
FSOE_MAPS_DIR = "fsoe_maps"


@pytest.fixture(scope="session")
def setup_specifier_with_esi(
    setup_specifier: DriveHwConfigSpecifier, request: pytest.FixtureRequest, att_resources_dir: Path
) -> DriveHwConfigSpecifier:
    """Fixture to provide a setup specifier with ESI file.

    If the ESI file is required to be downloaded from ATT, it will
    download it and include it in the specifier.
    Otherwise, it will just check that the ESI file exists.

    Args:
        setup_specifier: The original setup specifier.
        request: The pytest fixture request.
        att_resources_dir: Directory to save the ESI file if downloaded.

    Returns:
        A new specifier with the ESI file included.

    Raises:
        ValueError: If the setup specifier does not have an ESI file in its extra data.
        ValueError: If the setup specifier does not support ESI file download.
        FileNotFoundError: If the ESI file does not exist in the specified path.
    """
    if __EXTRA_DATA_ESI_FILE_KEY not in setup_specifier.extra_data:
        raise ValueError(f"Setup specifier {setup_specifier.identifier} does not have an ESI file.")

    if isinstance(setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY], FirmwareVersion):
        # Download using local ATT key
        if isinstance(setup_specifier, LocalDriveConfigSpecifier):
            att_client: ATTApi = request.getfixturevalue("att_client")
            esi_file = att_client.download_file(
                part_number=setup_specifier.identifier,
                revision_number=setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY].fw_version,
                file_type=ATTFileType.esi,
            )
        # Download using rack service ATT credentials
        elif isinstance(setup_specifier, RackServiceConfigSpecifier):
            rs_client: RackServiceClient = request.getfixturevalue("rs_client")
            setup_descriptor: DriveHwSetup = request.getfixturevalue("setup_descriptor")
            esi_file = rs_client.get_att_file(
                rack_drive_idx=setup_descriptor.rack_drive_idx,
                firmware_version=setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY].fw_version,
                file_type=ATTFileType.esi,
                directory=att_resources_dir.resolve(),
            )
        else:
            raise ValueError(
                f"Setup specifier {setup_specifier.identifier} does not support ESI file download."
            )
    else:
        esi_file = setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY]
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")

    new_data = setup_specifier.extra_data.copy()
    new_data[__EXTRA_DATA_ESI_FILE_KEY] = esi_file

    return dataclasses.replace(setup_specifier, extra_data=new_data)


@pytest.fixture
def mc_with_fsoe_with_sra_and_feedback_scenario(
    request: pytest.FixtureRequest,
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    """Fixture to provide a MotionController with FSoE and SRA configured with feedback scenario 4.

    Feedback Scenario 4:
        * Main feedback: Incremental Encoder.
        * Redundant feedback: Digital Halls.

    Yields:
        A tuple with the MotionController and the FSoEMasterHandler.
    """
    # Do not use getfixture
    # https://novantamotion.atlassian.net/browse/INGM-682
    mc, handler = request.getfixturevalue("mc_with_fsoe_with_sra")

    mc.communication.set_register(
        "CL_AUX_FBK_SENSOR", 5
    )  # Digital Halls as auxiliar sensor in Comoco
    handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").set(4)

    yield mc, handler

    # Should be in mc_with_fsoe_factory
    # https://novantamotion.atlassian.net/browse/INGM-682
    # If there has been a failure and it tries to remove the PDO maps, it may fail
    # if the servo is not in preop state
    try:
        if mc.capture.pdo.is_active:
            mc.fsoe.stop_master(stop_pdos=True)
    except Exception:
        pass


@pytest.fixture(scope="module")
def fsoe_maps_dir() -> Iterator[Path]:
    """Returns the directory where FSoE maps are stored.

    This directory is created if it does not exist.
    If the directory is empty after the tests, it will be removed.

    Yields:
        Path to the FSoE maps directory.
    """
    directory = OUTPUTS_DIR / FSOE_MAPS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    yield directory
    if not any(directory.iterdir()):
        directory.rmdir()


@pytest.fixture
def random_seed() -> int:
    """Returns a fixed random seed for reproducibility."""
    return random.randint(0, 1000)


@pytest.fixture
def random_paddings() -> bool:
    """Returns a random boolean for testing random paddings."""
    return random.choice([True, False])


@pytest.fixture
def random_max_items() -> int:
    """Returns a random integer for testing max items."""
    return random.randint(1, 10)


@pytest.fixture
def map_generator() -> Iterator["FSoERandomMappingGenerator"]:
    """Fixture to provide a random mapping generator.

    Yields:
        FSoERandomMappingGenerator instance.
    """
    yield FSoERandomMappingGenerator


@pytest.fixture(scope="session")
def timeout_for_data() -> float:
    """Returns the timeout value for the Data state for handler without SRA."""
    return TIMEOUT_FOR_DATA


@pytest.fixture(scope="session")
def timeout_for_data_sra() -> float:
    """Returns the timeout value for the Data state for handler using SRA."""
    return TIMEOUT_FOR_DATA_SRA


@pytest.fixture
def mcu_error_queue_a(servo: "Servo") -> "ServoErrorQueue":
    return ServoErrorQueue(MCUA_ERROR_QUEUE, servo)


@pytest.fixture
def mcu_error_queue_b(servo: "Servo") -> "ServoErrorQueue":
    return ServoErrorQueue(MCUB_ERROR_QUEUE, servo)
