import dataclasses
import random
from collections.abc import Generator
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

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import (
    TIMEOUT_FOR_DATA,
    TIMEOUT_FOR_DATA_SRA,
    fsoe_error_monitor,  # noqa: F401
    fsoe_states,  # noqa: F401
    mc_with_fsoe,  # noqa: F401
    mc_with_fsoe_with_sra,  # noqa: F401
)

if FSOE_MASTER_INSTALLED:
    from tests.fsoe.map_generator import FSoERandomMappingGenerator


if TYPE_CHECKING:
    from summit_testing_framework.att import ATTApi
    from summit_testing_framework.rack_service_client import RackServiceClient
    from summit_testing_framework.setups.descriptors import DriveHwSetup

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


# https://novantamotion.atlassian.net/browse/INGM-682
"""
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Let pytest run the test and generate the report first
    outcome = yield
    report = outcome.get_result()

    if call.when == "call":
        check_error = getattr(item, "_check_error", None)
        if check_error:
            check_error()
        error_message = getattr(item, "_error_message", None)
        if error_message:
            report.outcome = "failed"
            report.longrepr = error_message
"""


@pytest.fixture(scope="module")
def fsoe_maps_dir(request: pytest.FixtureRequest) -> Generator[Path, None, None]:
    """Returns the directory where FSoE maps are stored.

    This directory is created if it does not exist.
    If the directory is empty after the tests, it will be removed.

    Yields:
        Path to the FSoE maps directory.
    """
    directory = Path(request.config.rootdir).resolve() / FSOE_MAPS_DIR
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
def map_generator() -> Generator["FSoERandomMappingGenerator", None, None]:
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
