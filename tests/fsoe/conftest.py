import dataclasses
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

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import fsoe_states, mc_with_fsoe_with_sra  # noqa: F401

if TYPE_CHECKING:
    from summit_testing_framework.att import ATTApi
    from summit_testing_framework.rack_service_client import RackServiceClient
    from summit_testing_framework.setups.descriptors import DriveHwSetup

__EXTRA_DATA_ESI_FILE_KEY: str = "esi_file"


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
