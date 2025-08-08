import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import fsoe_states, mc_with_fsoe_with_sra  # noqa: F401

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
