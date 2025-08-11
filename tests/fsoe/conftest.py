import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import (
    TIMEOUT_FOR_DATA,
    TIMEOUT_FOR_DATA_SRA,
    fsoe_states,  # noqa: F401
    mc_with_fsoe_with_sra,  # noqa: F401
)

if FSOE_MASTER_INSTALLED:
    from tests.fsoe.map_generator import FSoERandomMappingGenerator


@pytest.fixture
def temp_mapping_file() -> Generator[Path, None, None]:
    """Creates an empty mapping file.

    Yields:
        mapping file path.
    """
    with tempfile.NamedTemporaryFile(suffix=".lfu", delete=False) as tmp:
        temp_path = Path(tmp.name)
    yield temp_path
    temp_path.unlink


@pytest.fixture
def map_generator() -> Generator[FSoERandomMappingGenerator, None, None]:
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
