import traceback
from collections.abc import Generator

import pytest

from ingeniamotion.wizard_tests.stoppable import (
    StopExceptionError,
    StopOpportunityTraceEvent,
    Stoppable,
)
from tests.stoppable_opportunities_timing import (
    StopGapRecord,
    StoppableReport,
    TestStoppableRecorder,
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


def test_stoppable_trace_recorder_captures_stop_opportunities(
    stoppable_trace_recorder,
) -> None:
    """The trace recorder should capture stop opportunities for checks and sleeps."""
    stoppable = DummyStoppable()

    stoppable.check_stop()
    stoppable.stoppable_sleep(0.0)
    stoppable.run(5)

    assert len(stoppable_trace_recorder) == 3
    first_event = stoppable_trace_recorder[0]
    second_event = stoppable_trace_recorder[1]
    third_event = stoppable_trace_recorder[2]

    # timestamps are ordered by call order
    assert first_event.timestamp <= second_event.timestamp <= third_event.timestamp
    assert first_event.traceback
    assert second_event.traceback
    assert third_event.traceback

    assert any(
        frame.name == "test_stoppable_trace_recorder_captures_stop_opportunities"
        for frame in first_event.traceback
    )
    assert any(frame.filename.endswith("stoppable.py") for frame in second_event.traceback)
    assert any(frame.filename.endswith("stoppable.py") for frame in third_event.traceback)


def test_stop_opportunity_subscriptions_can_be_composed(
    stoppable_trace_recorder,
) -> None:
    """Multiple subscriptions should all receive the same stop opportunities."""
    captured_events: list[str] = []

    def extra_recorder() -> None:
        captured_events.append("no_event")

    def event_recorder(event: StopOpportunityTraceEvent) -> None:
        captured_events.append(event.traceback[-1].name)

    no_event_subscription = Stoppable.subscribe_to_stop_opportunities(extra_recorder)
    event_subscription = Stoppable.subscribe_to_stop_opportunities(event_recorder, with_event=True)

    try:
        stoppable = Stoppable()
        stoppable.check_stop()
        stoppable.stoppable_sleep(0.0)
    finally:
        Stoppable.unsubscribe_from_stop_opportunities(no_event_subscription)
        Stoppable.unsubscribe_from_stop_opportunities(event_subscription)

    assert len(stoppable_trace_recorder) == 2
    assert captured_events == ["no_event", "check_stop", "no_event", "stoppable_sleep"]


def test_stoppable_report_counts_gaps_per_test_recorder(pytestconfig: pytest.Config) -> None:
    """The session report should only count gaps within each collected test."""

    def make_event(
        timestamp: float, finish_timestamp: float, filename: str, lineno: int
    ) -> StopOpportunityTraceEvent:
        return StopOpportunityTraceEvent(
            timestamp=timestamp,
            finish_timestamp=finish_timestamp,
            traceback=(traceback.FrameSummary(filename, lineno, "test_call"),),
        )

    recorder_one = TestStoppableRecorder(
        nodeid="tests/test_alpha.py::test_one",
        records=[
            make_event(1.0, 1.2, "tests/test_alpha.py", 10),
            make_event(2.0, 2.1, "tests/test_alpha.py", 20),
        ],
    )
    recorder_two = TestStoppableRecorder(
        nodeid="tests/test_beta.py::test_two",
        records=[make_event(10.0, 10.2, "tests/test_beta.py", 30)],
    )

    report = StoppableReport.from_test_recorders(
        pytestconfig=pytestconfig,
        test_recorders=[recorder_one, recorder_two],
        session_id="session-123",
    )

    expected_source_file = StopGapRecord._relative_path(
        pytestconfig.rootpath, "tests/test_alpha.py"
    )

    assert report.test_count == 2
    assert report.opportunities == 3
    assert report.gap_count == 1
    assert report.gap_count == report.opportunities - report.test_count
    assert report.top_gap_records == [
        StopGapRecord(
            previous_timestamp=1.0,
            current_timestamp=2.0,
            gap_seconds=0.8,
            source_file=expected_source_file,
            callsite=f"{expected_source_file}:20 in test_call",
        )
    ]
