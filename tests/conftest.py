import logging
import time
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Union

import numpy as np
import pytest
from ingenialink.dictionary import Interface
from summit_testing_framework import dynamic_loader
from summit_testing_framework.pytest_helpers.marker_helper import (
    apply_firmware_version_markers_to_items,
)

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


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
]

# Pytest runs with importlib import mode, which means that it will run the tests with the installed
# version of the package. Therefore, modules that are not included in the package cannot be imported
# in the tests.
# The issue is solved by dynamically importing them before the tests start. All modules that should
# be imported and ARE NOT part of the package should be specified here
_DYNAMIC_MODULES_IMPORT = ["tests", "examples"]


test_report_key = pytest.StashKey[dict[str, pytest.CollectReport]]()


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
    apply_firmware_version_markers_to_items(config=config, items=items)


@pytest.fixture
def disable_monitoring_disturbance(
    mc: "MotionController",
    alias: str,
) -> Generator[None, None, None]:
    yield
    mc.capture.clean_monitoring_disturbance(servo=alias)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # store test results for each phase of a call, which can be "setup", "call", "teardown"
    item.stash.setdefault(test_report_key, {})[rep.when] = rep

    if call.when == "call":
        callbacks = getattr(item, "_fixture_error_checker", None)
        if callbacks is not None:
            for callback in callbacks:
                success, message = callback()
                if not success:
                    rep.outcome = "failed"
                    rep.longrepr = message


def add_fixture_error_checker(node, callback: Callable[[], tuple[bool, str]]) -> None:
    if not hasattr(node, "_fixture_error_checker"):
        node._fixture_error_checker = []
    node._fixture_error_checker.append(callback)


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
