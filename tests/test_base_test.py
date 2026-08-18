from collections.abc import Iterator

import pytest

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase
from ingeniamotion.wizard_tests.stoppable import StopExceptionError


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
