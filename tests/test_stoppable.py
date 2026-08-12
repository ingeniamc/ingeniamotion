from collections.abc import Generator

import pytest

from ingeniamotion.wizard_tests.stoppable import (
    StopExceptionError,
    StopOpportunityTraceEvent,
    Stoppable,
)


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
        super().__init__()
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


def test_instance_creation_subscription_receives_new_stoppable_instances() -> None:
    """A creation subscription should receive each newly created stoppable instance."""
    instances: list[Stoppable] = []
    Stoppable.subscribe_to_instance_creations(instances.append)
    try:
        stoppable = DummyStoppable()
    finally:
        Stoppable.unsubscribe_to_instance_creations(instances.append)

    assert instances == [stoppable]


def test_instance_creation_unsubscription_stops_notifications() -> None:
    """Unsubscribing from creations should prevent future instance notifications."""
    instances: list[Stoppable] = []

    def recorder(stoppable: Stoppable) -> None:
        instances.append(stoppable)

    Stoppable.subscribe_to_instance_creations(recorder)
    Stoppable.unsubscribe_to_instance_creations(recorder)

    Stoppable()

    assert instances == []


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


def test_subscription_captures_stop_opportunities_with_tracebacks() -> None:
    """A subscription records an event with a traceback for each stop opportunity."""
    events: list[StopOpportunityTraceEvent] = []
    subscription = Stoppable.subscribe_to_stop_opportunities(events.append, with_event=True)
    try:
        stoppable = DummyStoppable()
        stoppable.check_stop()
        stoppable.stoppable_sleep(0.0)
        stoppable.run(5)
    finally:
        Stoppable.unsubscribe_from_stop_opportunities(subscription)

    assert len(events) == 3
    assert events[0].timestamp <= events[1].timestamp <= events[2].timestamp
    assert all(event.traceback for event in events)
    assert any(
        frame.name == "test_subscription_captures_stop_opportunities_with_tracebacks"
        for frame in events[0].traceback
    )
    assert any(frame.filename.endswith("stoppable.py") for frame in events[1].traceback)


def test_stop_opportunity_subscriptions_can_be_composed() -> None:
    """Every subscription receives each stop opportunity, in subscription order."""
    notifications: list[str] = []
    received_events: list[StopOpportunityTraceEvent] = []

    def plain_recorder() -> None:
        notifications.append("plain")

    def event_recorder(event: StopOpportunityTraceEvent) -> None:
        notifications.append("event")
        received_events.append(event)

    plain_subscription = Stoppable.subscribe_to_stop_opportunities(plain_recorder)
    event_subscription = Stoppable.subscribe_to_stop_opportunities(event_recorder, with_event=True)
    try:
        stoppable = Stoppable()
        stoppable.check_stop()
        stoppable.stoppable_sleep(0.0)
    finally:
        Stoppable.unsubscribe_from_stop_opportunities(plain_subscription)
        Stoppable.unsubscribe_from_stop_opportunities(event_subscription)

    # Both subscriptions fire for each of the two opportunities, plain before event.
    assert notifications == ["plain", "event", "plain", "event"]
    assert len(received_events) == 2
    assert all(event.traceback for event in received_events)
