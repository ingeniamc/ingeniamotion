import logging
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Union

import numpy as np
import pytest
from ingenialink import Servo
from ingenialink.configuration_file import ConfigurationFile
from ingenialink.dictionary import Interface
from ingenialink.exceptions import ILRegisterNotFoundError
from ingenialink.utils._utils import convert_bytes_to_dtype
from summit_testing_framework import dynamic_loader
from summit_testing_framework.profilers.stoppable_gaps import StoppableProfilerConfig
from summit_testing_framework.pytest_helpers.marker_helper import (
    MarkerHelper,
    apply_firmware_version_markers_to_items,
)

if TYPE_CHECKING:
    from summit_testing_framework.setups.specifiers import SetupSpecifier

    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
    from ingeniamotion.motion_node import MotionNode

logger = logging.getLogger(__name__)

__BISS_C_CONFIG_MARKER: str = "biss_c_flaky"
__ABS1_SLAVE_INDEX = 1
__ABS1_SSI1_RESOLUTION_BITS = 17
__ABS1_SSI1_PROTOCOL = "SSI1"


def not_valid_for_eve_can_ecat_products(func: Callable) -> Callable:
    """Decorator that applies not_valid_for_product markers for CAN and ECAT EVE products.

    Returns:
        The decorated function with the markers applied.
    """
    func = pytest.mark.not_valid_for_product(part_number="EVE-XCR-E", interfaces=[Interface.ECAT])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-XCR-C", interfaces=[Interface.CAN])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-NET-E", interfaces=[Interface.ECAT])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-NET-C", interfaces=[Interface.CAN])(
        func
    )
    return func


def not_valid_for_all_eve_products(func: Callable) -> Callable:
    """Decorator that applies not_valid_for_product markers for all EVE products.

    Returns:
        The decorated function with the markers applied.
    """
    func = pytest.mark.not_valid_for_product(part_number="EVE-XCR-E", interfaces=[Interface.ECAT])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-XCR-C", interfaces=[Interface.CAN])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-XCR-C", interfaces=[Interface.ETH])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-NET-E", interfaces=[Interface.ECAT])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-NET-C", interfaces=[Interface.CAN])(
        func
    )
    func = pytest.mark.not_valid_for_product(part_number="EVE-NET-C", interfaces=[Interface.ETH])(
        func
    )
    return func


pytest_plugins = [
    "summit_testing_framework.pytest_addoptions",
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


def __config_uses_biss_c(config_file: Path) -> bool:
    """Checks if the configuration file uses BISS-C protocol.

    Args:
        config_file: Path to the configuration file.

    Returns:
        bool: True if the configuration file uses BISS-C protocol, False otherwise.
    """

    # Check if absolute encoder is present in feedback sensor
    # CL_VEL_FBK_SENSOR, CL_POS_FBK_SENSOR, COMMU_ANGLE_SENSOR
    position_feedback_registers = ["CL_VEL_FBK_SENSOR", "CL_POS_FBK_SENSOR", "COMMU_ANGLE_SENSOR"]
    encoder_protocol_registers = ["FBK_BISS1_SSI1_PROTOCOL", "FBK_SSI2_PROTOCOL"]
    # Primary Absolute Slave 1: 1, Secondary Absolute Slave 1: 2
    search_registers = dict.fromkeys(position_feedback_registers + encoder_protocol_registers, None)

    xcf_instance = ConfigurationFile.load_from_xcf(config_file)
    for config_register in xcf_instance.registers:
        if config_register.uid in search_registers:
            search_registers[config_register.uid] = (
                convert_bytes_to_dtype(config_register.data, config_register.dtype)
                if config_register.data is not None
                else config_register.storage
            )

        if all(value is not None for value in search_registers.values()):
            break

    for register in position_feedback_registers:
        if search_registers[register] is None:
            continue

        # Primary Absolute Slave 1 selected
        if search_registers[register] == 1:
            if search_registers[encoder_protocol_registers[0]] == 0:
                return True
        # Secondary Absolute Slave 1 selected
        elif (
            search_registers[register] == 7 and search_registers[encoder_protocol_registers[1]] == 0
        ):
            return True
    return False


def apply_configuration_marker_to_items(
    config: "pytest.Config", items: list["pytest.Item"]
) -> None:
    """Applies configuration markers to collected test items.

    There are certain tests that are known to be flaky for BISS-C configuration,
    and should be skipped for certain firmware versions.
    """
    # Check if the setup contains absolute encoder with BISS-C configuration,
    # so that proper tests can be skipped
    marker_helper: MarkerHelper = MarkerHelper(config=config)
    if not marker_helper.is_setup_specified:
        return
    setup_specifier: SetupSpecifier = marker_helper.setup_specifier
    if setup_specifier.config_file is None:
        return

    if not __config_uses_biss_c(setup_specifier.config_file):
        return

    for item in items:
        if not item.get_closest_marker(__BISS_C_CONFIG_MARKER):
            continue

        for skip_product in ["CAP-*", "EVE-*", "EVS-*"]:
            item.add_marker(
                pytest.mark.valid_versions_for_product(part_number=skip_product, max="2.6.0")
            )
            item.add_marker(
                pytest.mark.valid_versions_for_product(part_number=skip_product, min="2.11.0")
            )


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
    # Add valid_versions_for_product markers to tests that have the biss_c_flaky marker,
    # if the setup uses BISS-C configuration
    # This must be done before applying firmware version markers to items,
    # so that the valid_versions_for_product markers are applied first
    apply_configuration_marker_to_items(config=config, items=items)
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


@pytest.fixture(scope="session")
def stoppable_profiler_config() -> StoppableProfilerConfig:
    """Provide the stoppable profiler configuration for ingeniamotion.

    Supplies the gap thresholds required by the stoppable gaps plugin.

    Returns:
        The stoppable profiler configuration.
    """
    return StoppableProfilerConfig(
        gap_threshold_seconds=5.1,  # https://novantamotion.atlassian.net/browse/INGM-768
        good_enough_gap_seconds=2.6,
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


@pytest.fixture()
def configure_abs_encoder(
    rs_client,
    setup_descriptor,
    is_abs_encoder_configurable: bool,
) -> None:
    """Configure ABS1 through the rack service if the encoder is configurable."""
    if not is_abs_encoder_configurable:
        return
    try:
        rs_client.client.exposed_set_abs(
            setup_descriptor.rack_drive_idx,
            __ABS1_SLAVE_INDEX,
            __ABS1_SSI1_RESOLUTION_BITS,
            __ABS1_SSI1_PROTOCOL,
        )

        current_config = rs_client.client.exposed_get_abs(setup_descriptor.rack_drive_idx, 1)
        assert current_config.protocol.name == __ABS1_SSI1_PROTOCOL
        assert current_config.resolution.n == __ABS1_SSI1_RESOLUTION_BITS
    except Exception as exc:
        pytest.fail(f"Unable to configure SIRIUS ABS1 feedback: {exc}", pytrace=False)


@pytest.fixture
def is_abs_encoder_configurable(setup_specifier: "SetupSpecifier") -> bool:
    """Determine if the ABS encoder is configurable based on the setup specifier.

    Returns:
        bool: True if the ABS encoder is configurable, False otherwise.

    """
    return setup_specifier.extra_data.get("is_abs_encoder_configurable", False)
