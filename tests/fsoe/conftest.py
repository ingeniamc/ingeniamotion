import random
from collections.abc import Generator
from pathlib import Path

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

# https://novantamotion.atlassian.net/browse/INGM-682
from tests.test_fsoe_master import (
    TIMEOUT_FOR_DATA,
    TIMEOUT_FOR_DATA_SRA,
    fsoe_error_monitor,  # noqa: F401
    fsoe_states,  # noqa: F401
    mc_with_fsoe_with_sra,  # noqa: F401
)

if FSOE_MASTER_INSTALLED:
    from tests.fsoe.map_generator import FSoERandomMappingGenerator

FSOE_MAPS_DIR = "fsoe_maps"


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
