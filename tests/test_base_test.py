from collections.abc import Iterator
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from ingenialink.drive_context_manager import DriveContextManager

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests import base_test as base_test_module
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase
from ingeniamotion.wizard_tests.stoppable import StopExceptionError

if TYPE_CHECKING:
    from ingeniamotion import MotionController
    from ingeniamotion.axis import Axis


class TeardownFailureTest(BaseTest[ReportBase]):
    """Concrete BaseTest whose teardown fails after the test body succeeds."""

    def __init__(self, mc: "MotionController") -> None:
        super().__init__()
        self.mc = mc
        self.restored = False

    def setup(self) -> None:
        pass

    def loop(self) -> None:
        pass

    def teardown(self) -> None:
        raise RuntimeError("teardown failed")

    def _restore_configuration(self, _context: DriveContextManager) -> None:
        self.restored = True

    def get_result_msg(self, _output: object) -> str:
        return ""

    def get_result_severity(self, _output: object) -> SeverityLevel:
        return SeverityLevel.SUCCESS


class ConcreteBaseTest(BaseTest[ReportBase]):
    """Minimal concrete test used to exercise base test behavior."""

    def setup(self) -> None:
        pass

    def loop(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def get_result_msg(self, output: object) -> str:
        return str(output)

    def get_result_severity(self, _output: object) -> SeverityLevel:
        return SeverityLevel.SUCCESS


def test_run_context_creates_report_after_context_body(mocker) -> None:
    """The context API should create its report after the caller leaves the context."""
    context_manager = mocker.patch.object(base_test_module, "DriveContextManager")
    context_manager.return_value.__enter__.return_value = context_manager.return_value
    test = ConcreteBaseTest()
    test.mc = Mock()
    test.mc._get_drive.return_value = Mock()

    with test.run_context() as output:
        assert output is None
        assert test.report is None

    assert test.report is not None
    assert context_manager.return_value.__exit__.call_count == 1


@pytest.mark.virtual
def test_base_test_restores_configuration_when_teardown_fails(
    mc: "MotionController", alias: str, axis: "Axis"
) -> None:
    """Configuration restoration must run even when teardown raises."""
    test = TeardownFailureTest(mc)
    test.servo = alias
    test.axis = axis.axis_number

    with pytest.raises(RuntimeError) as exc_info:
        test.run()

    assert str(exc_info.value) == "teardown failed"
    assert test.restored


@pytest.mark.virtual
def test_base_test_caches_target_motion_node_axis_and_feedbacks(
    mc: "MotionController", alias: str, axis: "Axis"
) -> None:
    """BaseTest resolves the selected axis feedback container once."""
    test = TeardownFailureTest(mc)
    test.servo = alias
    test.axis = axis.axis_number

    assert test._motion_node is test._motion_node
    assert test._axis is test._axis
    assert test._axis_feedbacks is test._axis.feedbacks


@pytest.fixture
def base_test() -> Iterator[ConcreteBaseTest]:
    """Provide a concrete base test with a clean stop state.

    Yields:
        A concrete base test instance.
    """
    test = ConcreteBaseTest()
    test.reset_stop()
    yield test
    test.reset_stop()


def test_timeout_loop_yields_iterations_until_timeout(
    base_test: ConcreteBaseTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loop should yield each iteration before ending when no timeout error is configured."""
    monotonic_values = iter((100.0, 100.0, 101.0))
    monkeypatch.setattr(
        "ingeniamotion.wizard_tests.base_test.time.monotonic",
        lambda: next(monotonic_values),
    )

    assert list(base_test._timeout_loop(timeout_sec=1.0, timeout=None)) == [1]


@pytest.mark.parametrize("timeout_sec, sleep_sec", [(-1.0, 0.0), (0.0, -1.0)])
def test_timeout_loop_rejects_negative_durations(
    base_test: ConcreteBaseTest, timeout_sec: float, sleep_sec: float
) -> None:
    """The loop should reject negative timeout and sleep durations."""
    with pytest.raises(ValueError):
        next(base_test._timeout_loop(timeout_sec=timeout_sec, sleep_sec=sleep_sec))


def test_timeout_loop_raises_default_timeout_error(
    base_test: ConcreteBaseTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loop should raise the default timeout error after the deadline expires."""
    monotonic_values = iter((100.0, 100.0, 101.0))
    monkeypatch.setattr(
        "ingeniamotion.wizard_tests.base_test.time.monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(TimeoutError, match="Test timed out"):
        list(base_test._timeout_loop(timeout_sec=1.0))


def test_timeout_loop_raises_custom_timeout_error(
    base_test: ConcreteBaseTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loop should raise the exception returned by a custom timeout factory."""
    monotonic_values = iter((100.0, 100.0, 101.0))
    monkeypatch.setattr(
        "ingeniamotion.wizard_tests.base_test.time.monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(RuntimeError, match="custom timeout"):
        list(
            base_test._timeout_loop(
                timeout_sec=1.0,
                timeout=lambda: RuntimeError("custom timeout"),
            )
        )


def test_timeout_loop_stops_when_stop_is_requested(base_test: ConcreteBaseTest) -> None:
    """The loop should propagate a stop request at its next stop opportunity."""
    base_test.stop()

    with pytest.raises(StopExceptionError):
        next(base_test._timeout_loop(timeout_sec=1.0))
