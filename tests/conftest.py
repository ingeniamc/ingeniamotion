import logging
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union

import numpy as np
import pytest
from ingenialink import Servo
from ingenialink.dictionary import Interface
from ingenialink.exceptions import ILRegisterNotFoundError
from summit_testing_framework import dynamic_loader
from summit_testing_framework.configuration.conditions import RegisterCondition, all_of, any_of
from summit_testing_framework.configuration.feedback_constants import (
    FeedbackSelectorRegisters,
    FeedbackSensorType,
)
from summit_testing_framework.pytest_helpers.marker_helper import (
    apply_firmware_version_markers_to_items,
)
from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    DictionaryVersion,
)

from tests.dictionaries import SAMPLE_SAFE_PH1_XDFV3_DICTIONARY

if TYPE_CHECKING:
    from summit_testing_framework.profilers.stoppable_gaps import StoppableProfilerConfig

    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
    from ingeniamotion.motion_node import MotionNode

logger = logging.getLogger(__name__)


# Fraction of exhaustive test configurations to run in shorter daytime test sessions.
RANDOM_COMBINATIONS_SLICE_KEY: str = "random_combinations_slice"


def forbids_biss_c_configuration(part_number: str) -> pytest.MarkDecorator:
    """Create a marker for tests that are flaky with a BISS-C configuration.

    Args:
        part_number: Part-number pattern to which the marker applies.

    Returns:
        A configuration marker that skips the test for the BISS-C configuration.
    """
    return pytest.mark.forbids_configuration(
        expression=any_of(
            all_of(
                any_of(
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.VELOCITY.value,
                        reg_value=FeedbackSensorType.ABS1,
                    ),
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.POSITION.value,
                        reg_value=FeedbackSensorType.ABS1,
                    ),
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.COMMUTATION.value,
                        reg_value=FeedbackSensorType.ABS1,
                    ),
                ),
                RegisterCondition("FBK_BISS1_SSI1_PROTOCOL", 0),
            ),
            all_of(
                any_of(
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.VELOCITY.value,
                        reg_value=FeedbackSensorType.BISSC2,
                    ),
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.POSITION.value,
                        reg_value=FeedbackSensorType.BISSC2,
                    ),
                    RegisterCondition(
                        reg_uid=FeedbackSelectorRegisters.COMMUTATION.value,
                        reg_value=FeedbackSensorType.BISSC2,
                    ),
                ),
                RegisterCondition("FBK_SSI2_PROTOCOL", 0),
            ),
        ),
        part_number=part_number,
        min="2.6.0",
        max="2.10.0",
        skip_reason="Flaky test for BISS-C configuration, solved in 2.11.0",
    )


pytest_plugins = [
    "summit_testing_framework.pytest_addoptions",
    "summit_testing_framework.pytest_markers",
    "summit_testing_framework.setup_fixtures",
    "summit_testing_framework.profilers.stoppable_gaps",
]

# Pytest runs with importlib import mode, which means that it will run the tests with the installed
# version of the package. Therefore, modules that are not included in the package cannot be imported
# in the tests.
# The issue is solved by dynamically importing them before the tests start. All modules that should
# be imported and ARE NOT part of the package should be specified here
_DYNAMIC_MODULES_IMPORT = ["tests", "examples"]


class SuppressSpecificLogs(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        # Suppress logs containing this specific message
        return (
            "Emergency message received from slave" not in message
            and "Error code 0x0000" not in message
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


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):  # noqa: ARG001
    # https://novantamotion.atlassian.net/browse/INGM-627
    logging.getLogger("ingenialink.ethercat.servo").addFilter(SuppressSpecificLogs())


def pytest_collection_modifyitems(
    session: pytest.Session,  # noqa: ARG001
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Modifies collected tests to skip those that do not meet firmware version restrictions.

    Only runs if --enable_firmware_version_check is passed.

    Args:
        session: pytest session.
        config: pytest configuration.
        items: collected test items.
    """
    # Apply firmware version markers to items, skipping tests that do not meet the requirements
    apply_firmware_version_markers_to_items(config=config, items=items)


@pytest.fixture
def disable_monitoring_disturbance(
    mc: "MotionController",
    alias: str,
) -> Generator[None, None, None]:
    yield
    mc.capture.clean_monitoring_disturbance(servo=alias)


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


@pytest.fixture
def motion_node(mc: "MotionController") -> "MotionNode":
    """Fixture that provides a motion node for testing.

    Returns:
        MotionNode: The motion node to be used for testing.
    """
    return mc._get_motion_node("default")


@pytest.fixture
def axis(motion_node: "MotionNode") -> "Axis":
    """Fixture that provides an axis for testing.

    Raises:
        ValueError: If the motion node has more than one axis,
            since the fixture cannot determine which one to use.

    Returns:
        Axis: The axis of the motion node to be used for testing.
    """
    if len(list(motion_node.axes)) > 1:
        raise ValueError(
            "Motion node has more than one axis, cannot determine which one to use for the fixture."
        )

    return motion_node.get_axis(1)


# https://novantamotion.atlassian.net/browse/CIT-401
def timeout_loop(
    timeout_sec: float, other: Optional[Union[Exception, Callable[[], Exception]]] = None
) -> Iterator[int]:
    """Timeout Loop

    If the timeout is reached, a custom exception can be thrown, from other argument

    Args:
        timeout_sec: Maximum seconds to iterate on the loop
        other: Exception to be thrown if timeout is reached
            Also accepts a function that returns an exception.

    Yields:
        int: The current iteration number.

    Examples:

        .. code-block:: python

            for iteration in timeout_loop(
                timeout_sec=0.5,
                other=AssertionError("Timeout reached")
            ):
                print(f"Iteration {iteration} with timeout")
                sleep(1)
    """
    iteration = 1
    start_time = time.time()
    timeout_time = start_time + timeout_sec

    while True:
        if time.time() > timeout_time:
            if other is not None:
                if isinstance(other, BaseException):
                    raise other
                else:
                    raise other()
            else:
                break

        yield iteration
        iteration += 1


ConfigurationT = TypeVar("ConfigurationT")


def slice_configurations(
    configurations: list[ConfigurationT], setup_specifier
) -> list[ConfigurationT]:
    """Return the configured fraction of test configurations.

    Args:
        configurations: Randomized test configurations.
        setup_specifier: Active test setup specifier.

    Returns:
        All configurations when no slice is configured, otherwise the configured
        fraction with at least one configuration.
    """
    assert configurations, "At least one test configuration is required"
    configuration_slice = setup_specifier.extra_data.get(RANDOM_COMBINATIONS_SLICE_KEY, None)
    if configuration_slice is None:
        return configurations
    return configurations[: max(1, int(len(configurations) * configuration_slice))]


@pytest.fixture(scope="session")
def stoppable_profiler_config() -> "StoppableProfilerConfig":
    """Provide the stoppable profiler configuration for ingeniamotion.

    Supplies the gap thresholds required by the stoppable gaps plugin.

    Returns:
        The stoppable profiler configuration.
    """
    from summit_testing_framework.profilers.stoppable_gaps import (  # noqa: PLC0415
        StoppableProfilerConfig,
    )

    return StoppableProfilerConfig(
        gap_threshold_seconds=5.1,
        good_enough_gap_seconds=0.2,
    )


@contextmanager
def refresh_registers_for_test_rollback(servo: Servo, register_uids: list[str]):
    """Refresh stale registers if drive context manager

    Some mechanisms of the drive might not be detected by the drive context manager
    and the drive might not be rolled back to the initial state after test execution.
    Using this context manager on a test will force a read after test execution
    to avoid any register change leak

    Args:
        servo: Servo instance to read registers from.
        register_uids: List of register UIDs to read after test execution.
    """
    yield
    for register_uid in register_uids:
        try:
            servo.read(register_uid)
        except ILRegisterNotFoundError:  # noqa: PERF203
            logger.warning(
                f"Register {register_uid} not found during refresh after test execution."
            )


@pytest.fixture(scope="session")
def sample_safe_ph1_xdfv3_dictionary() -> Path:
    return Path(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)


@pytest.fixture(scope="session")
def sample_safe_ph2_xdfv3_dictionary(
    product_dictionary: Callable[[str, DictionaryVersion, Optional[Interface]], Path],
) -> Path:
    return product_dictionary(
        "EVS-S-NET-E",
        DictionaryVersion("2.9.1", DictionaryType.XDF_V3),
    )
