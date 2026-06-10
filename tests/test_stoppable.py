from collections.abc import Generator

import pytest

from ingeniamotion.wizard_tests.stoppable import StopExceptionError, Stoppable


@pytest.fixture(autouse=True)
def clear_stop_queue() -> Generator[None, None, None]:
    """Ensure the shared stop queue is empty before and after each test."""
    stoppable = Stoppable()
    stoppable.reset_stop()
    yield
    stoppable.reset_stop()


class DummyStoppable(Stoppable):
    """Small concrete helper used to exercise stoppable behavior."""

    def __init__(self) -> None:
        self.calls = 0

    @Stoppable.stoppable
    def run(self, value: int) -> int:
        """Return a transformed value while recording that the body ran."""
        self.calls += 1
        return value * 2


def test_stop_raises_stop_exception_on_check_stop() -> None:
    """`stop()` should make `check_stop()` raise the queued exception."""
    stoppable = Stoppable()
    stoppable.stop()
    with pytest.raises(StopExceptionError):
        stoppable.check_stop()


def test_reset_stop_clears_pending_stop_signal() -> None:
    """`reset_stop()` should remove a pending stop request from the queue."""
    stoppable = Stoppable()
    stoppable.stop()
    stoppable.reset_stop()
    stoppable.check_stop()


def test_stoppable_decorator_runs_body_without_stop() -> None:
    """The stoppable decorator should forward the call when no stop is pending."""
    stoppable = DummyStoppable()
    result = stoppable.run(5)
    assert result == 10
    assert stoppable.calls == 1


def test_stoppable_decorator_blocks_body_when_stop_is_pending() -> None:
    """The stoppable decorator should raise before executing the wrapped body."""
    stoppable = DummyStoppable()
    stoppable.stop()
    with pytest.raises(StopExceptionError):
        stoppable.run(5)
    assert stoppable.calls == 0


def test_stoppable_sleep_handles_empty_and_pending_stop_queue() -> None:
    """`stoppable_sleep()` should pass on an empty queue and raise on a stop signal."""
    stoppable = Stoppable()
    stoppable.stoppable_sleep(0.0)
    stoppable.stop()
    with pytest.raises(StopExceptionError):
        stoppable.stoppable_sleep(0.0)
