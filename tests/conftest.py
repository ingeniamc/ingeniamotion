import time
from collections.abc import Iterator
from pathlib import Path
from typing import Callable, Optional, Union

import numpy as np
import pytest
from summit_testing_framework import dynamic_loader

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


@pytest.fixture
def disable_monitoring_disturbance(skip_if_monitoring_not_available, mc, alias):  # noqa: ARG001
    yield
    mc.capture.clean_monitoring_disturbance(servo=alias)


@pytest.fixture()
def skip_if_monitoring_not_available(mc, alias):
    try:
        mc.capture._check_version(alias)
    except NotImplementedError:
        pytest.skip("Monitoring is not available")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # store test results for each phase of a call, which can be "setup", "call", "teardown"
    item.stash.setdefault(test_report_key, {})[rep.when] = rep


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
