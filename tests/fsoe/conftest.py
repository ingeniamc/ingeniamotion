import dataclasses
from typing import TYPE_CHECKING

import pytest
from summit_testing_framework import ATTFileType
from summit_testing_framework.setups.specifiers import DriveHwConfigSpecifier, FirmwareVersion

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import fsoe_states, mc_with_fsoe_with_sra  # noqa: F401

if TYPE_CHECKING:
    from summit_testing_framework.att import ATTApi

__EXTRA_DATA_ESI_FILE_KEY: str = "esi_file"


@pytest.fixture(scope="session")
def setup_specifier_with_esi(
    setup_specifier: DriveHwConfigSpecifier, request: pytest.FixtureRequest
) -> DriveHwConfigSpecifier:
    """Fixture to provide a setup specifier with ESI file.

    If the ESI file is required to be downloaded from ATT, it will
    download it and include it in the specifier.
    Otherwise, it will just check that the ESI file exists.

    Args:
        setup_specifier: The original setup specifier.
        request: The pytest fixture request.

    Returns:
        A new specifier with the ESI file included.

    Raises:
        ValueError: If the setup specifier does not have an ESI file in its extra data.
        FileNotFoundError: If the ESI file does not exist in the specified path.
    """
    if __EXTRA_DATA_ESI_FILE_KEY not in setup_specifier.extra_data:
        raise ValueError(f"Setup specifier {setup_specifier.identifier} does not have an ESI file.")

    if isinstance(setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY], FirmwareVersion):
        att_client: ATTApi = request.getfixturevalue("att_client")
        esi_file = att_client.download_file(
            part_number=setup_specifier.identifier,
            revision_number=setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY].fw_version,
            file_type=ATTFileType.esi,
        )
    else:
        esi_file = setup_specifier.extra_data[__EXTRA_DATA_ESI_FILE_KEY]
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")

    new_data = setup_specifier.extra_data.copy()
    new_data[__EXTRA_DATA_ESI_FILE_KEY] = esi_file

    return dataclasses.replace(setup_specifier, extra_data=new_data)
