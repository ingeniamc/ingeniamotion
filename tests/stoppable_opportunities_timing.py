import json
import statistics
import traceback
from collections import Counter
from collections.abc import Generator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pytest
from jinja2 import Environment

from ingeniamotion.wizard_tests.stoppable import (
    StopOpportunitySubscription,
    StopOpportunityTraceEvent,
    Stoppable,
)
from tests.outputs import OUTPUTS_DIR

# Define unique folder for reports
STOPPABLE_REPORT_DIR = OUTPUTS_DIR / "stoppable_opportunities_timing"

# Stoppable gap thresholds:
# STOPPABLE_GAP_THRESHOLD_SECONDS: Hard limit. Tests fail if any gap exceeds this.
# STOPPABLE_GOOD_ENOUGH_GAP_SECONDS: Soft limit for reporting. If max gap > this,
#   the report shows detailed tables of worst gaps and hotspots. Otherwise,
#   it just notes that all gaps are below the threshold.
STOPPABLE_GAP_THRESHOLD_SECONDS = 5.1  # https://novantamotion.atlassian.net/browse/INGM-768
STOPPABLE_GOOD_ENOUGH_GAP_SECONDS = 2.6


STOPPABLE_REPORT_TEMPLATE = """# Stoppable gap report

- Generated at: {{ generated_at }}
- Tests: {{ test_count }}
- Stop opportunities: {{ opportunities }}
- Recorded gaps: {{ gap_count }}
- Distinct callsites: {{ unique_callsites }}

{% if not statistics %}
No stoppable gaps were recorded.

The JSON report still contains the captured stop-opportunity events.
{% else %}
## Gap statistics

| Metric | Value |
| --- | --- |
| Mean | {{ statistics.mean_gap_seconds | format_seconds }} |
| Median | {{ statistics.median_gap_seconds | format_seconds }} |
| p95 | {{ statistics.p95_gap_seconds | format_seconds }} |
| Max | {{ statistics.max_gap_seconds | format_seconds }} |
| Slow gaps | {{ statistics.slow_gap_count }} |

{% if statistics.max_gap_seconds >= good_enough_cutoff %}
## Worst individual gaps

| # | Gap | Callsite |
| --- | --- | --- |
{% for record in top_gap_records -%}
| {{ loop.index }} | {{ record.gap_seconds | format_seconds }} | {{ record.callsite }} |
{% endfor %}

## Worst callsites by total gap

| # | Callsite | Total gap | Count | Max |
| --- | --- | --- | --- | --- |
{% for h in callsite_hotspots -%}
| {{ loop.index }} | {{ h.label }} | {{ h.total_gap_seconds | format_seconds }} |
{{- h.gap_count }} | {{ h.max_gap_seconds | format_seconds }} |
{% endfor %}
{% else %}
## Worst individual gaps

All gaps are below {{ good_enough_cutoff | format_seconds }}; no gap ranking is shown.
{% endif %}
{% endif %}
"""


@dataclass(frozen=True)
class StopGapRecord:
    """Gap observed between two stop opportunities."""

    previous_timestamp: float
    current_timestamp: float
    gap_seconds: float
    source_file: str
    callsite: str

    @staticmethod
    def _relative_path(rootpath: Path, filename: str) -> str:
        """Return a path relative to the pytest root when possible."""
        path = Path(filename)
        try:
            return str(path.resolve().relative_to(rootpath.resolve()))
        except ValueError:
            return str(path.resolve())

    @staticmethod
    def _stoppable_callsite(
        traceback_frames: tuple[traceback.FrameSummary, ...],
    ) -> traceback.FrameSummary:
        """Return the most useful non-stoppable frame for reporting."""
        for frame in reversed(traceback_frames):
            if Path(frame.filename).name == "stoppable.py":
                continue
            return frame
        return traceback_frames[-1]

    @classmethod
    def _traceback_location(
        cls, rootpath: Path, traceback_frames: tuple[traceback.FrameSummary, ...]
    ) -> tuple[str, str]:
        """Return a displayable source file and callsite string."""
        if not traceback_frames:
            return "<unknown>", "<unknown>"
        frame = cls._stoppable_callsite(traceback_frames)
        source_file = cls._relative_path(rootpath, frame.filename)
        return source_file, f"{source_file}:{frame.lineno} in {frame.name}"

    @classmethod
    def from_trace_events(
        cls, rootpath: Path, records: list[StopOpportunityTraceEvent]
    ) -> list["StopGapRecord"]:
        """Convert raw stop-opportunity events into gap records.

        Returns:
            Gap records.
        """
        gap_records = []
        for previous, current in zip(records, records[1:]):
            source_file, callsite = cls._traceback_location(rootpath, current.traceback)

            previous_finish = previous.finish_timestamp

            gap_records.append(
                cls(
                    previous_timestamp=previous.timestamp,
                    current_timestamp=current.timestamp,
                    gap_seconds=current.timestamp - previous_finish,
                    source_file=source_file,
                    callsite=callsite,
                )
            )
        return gap_records


@dataclass(frozen=True)
class StopGapStatistics:
    """Aggregate statistics for the recorded stop-opportunity gaps."""

    min_gap_seconds: float
    mean_gap_seconds: float
    median_gap_seconds: float
    p95_gap_seconds: float
    max_gap_seconds: float
    slow_gap_count: int
    slow_gap_ratio: float

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        """Return a simple percentile from a sorted list."""
        if not sorted_values:
            return 0.0
        index = int(round((len(sorted_values) - 1) * percentile))
        return sorted_values[index]

    @classmethod
    def from_gaps(cls, gaps: list[float]) -> Optional["StopGapStatistics"]:
        """Build aggregate statistics for a list of gap durations.

        Returns:
            Gap statistics.
        """
        if not gaps:
            return None
        sorted_gaps = sorted(gaps)
        slow_gap_count = sum(1 for gap in sorted_gaps if gap > STOPPABLE_GAP_THRESHOLD_SECONDS)
        return cls(
            min_gap_seconds=sorted_gaps[0],
            mean_gap_seconds=statistics.fmean(sorted_gaps),
            median_gap_seconds=statistics.median(sorted_gaps),
            p95_gap_seconds=cls._percentile(sorted_gaps, 0.95),
            max_gap_seconds=sorted_gaps[-1],
            slow_gap_count=slow_gap_count,
            slow_gap_ratio=slow_gap_count / len(sorted_gaps),
        )


@dataclass(frozen=True)
class GapHotspot:
    """Grouped summary for the most expensive locations."""

    label: str
    total_gap_seconds: float
    gap_count: int
    average_gap_seconds: float
    max_gap_seconds: float

    @classmethod
    def from_gap_records(
        cls,
        gap_records: list[StopGapRecord],
        key_func: Callable[[StopGapRecord], str],
        limit: int = 10,
    ) -> list["GapHotspot"]:
        """Build a ranked summary of the hottest callsites or source files.

        Returns:
            Hotspots.
        """
        total_gap_by_label = Counter()
        count_by_label = Counter()
        max_gap_by_label: dict[str, float] = {}
        for record in gap_records:
            label = key_func(record)
            total_gap_by_label[label] += record.gap_seconds
            count_by_label[label] += 1
            if label not in max_gap_by_label or record.gap_seconds > max_gap_by_label[label]:
                max_gap_by_label[label] = record.gap_seconds

        hotspots = []
        for label, total_gap in total_gap_by_label.most_common(limit):
            gap_count = count_by_label[label]
            hotspots.append(
                cls(
                    label=label,
                    total_gap_seconds=total_gap,
                    gap_count=gap_count,
                    average_gap_seconds=total_gap / gap_count,
                    max_gap_seconds=max_gap_by_label[label],
                )
            )
        return hotspots


@dataclass(frozen=True)
class StoppableReport:
    """Full stoppable report payload written to disk."""

    generated_at: str
    pytest_root: str
    report_dir: str
    session_id: str
    threshold_seconds: float
    test_count: int
    opportunities: int
    gap_count: int
    unique_callsites: int
    unique_source_files: int
    statistics: Optional[StopGapStatistics]
    top_gap_records: list[StopGapRecord]
    callsite_hotspots: list[GapHotspot]
    source_file_hotspots: list[GapHotspot]
    gap_records: list[StopGapRecord]

    @staticmethod
    def _format_seconds(value: float) -> str:
        """Format a duration in seconds for human-readable reports.

        Returns:
            Formatted duration.
        """
        return f"{value:.3f}s"

    def render(self) -> str:
        """Render the stoppable report as Markdown.

        Returns:
            Rendered Markdown.
        """
        # Use a more readable date format
        try:
            dt = datetime.fromisoformat(self.generated_at)
            display_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_date = self.generated_at

        env = Environment()
        env.filters["format_seconds"] = self._format_seconds
        template = env.from_string(STOPPABLE_REPORT_TEMPLATE)

        render_context: dict[str, Any] = asdict(self)
        render_context["generated_at"] = display_date
        render_context["good_enough_cutoff"] = STOPPABLE_GOOD_ENOUGH_GAP_SECONDS

        return template.render(**render_context)

    @classmethod
    def from_test_recorders(
        cls,
        pytestconfig: pytest.Config,
        test_recorders: list["TestStoppableRecorder"],
        session_id: str,
    ) -> "StoppableReport":
        """Build the structured stoppable report payload from completed tests.

        Returns:
            Stoppable report.
        """
        now = datetime.now()
        generated_at = now.astimezone().isoformat(timespec="seconds")
        gap_records: list[StopGapRecord] = []
        opportunities = 0
        for test_recorder in test_recorders:
            opportunities += len(test_recorder.records)
            gap_records.extend(
                StopGapRecord.from_trace_events(pytestconfig.rootpath, test_recorder.records)
            )

        gaps = [record.gap_seconds for record in gap_records]
        statistics = StopGapStatistics.from_gaps(gaps)
        callsite_hotspots = GapHotspot.from_gap_records(gap_records, lambda rec: rec.callsite)
        source_file_hotspots = GapHotspot.from_gap_records(gap_records, lambda rec: rec.source_file)
        top_gap_records = sorted(gap_records, key=lambda item: item.gap_seconds, reverse=True)[:10]

        return cls(
            generated_at=generated_at,
            pytest_root=str(pytestconfig.rootpath),
            report_dir=str(STOPPABLE_REPORT_DIR),
            session_id=session_id,
            threshold_seconds=STOPPABLE_GAP_THRESHOLD_SECONDS,
            test_count=len(test_recorders),
            opportunities=opportunities,
            gap_count=len(gap_records),
            unique_callsites=len({record.callsite for record in gap_records}),
            unique_source_files=len({record.source_file for record in gap_records}),
            statistics=statistics,
            top_gap_records=top_gap_records,
            callsite_hotspots=callsite_hotspots,
            source_file_hotspots=source_file_hotspots,
            gap_records=gap_records,
        )

    @classmethod
    def from_records(
        cls, pytestconfig: pytest.Config, records: list[StopOpportunityTraceEvent], session_id: str
    ) -> "StoppableReport":
        """Build the structured stoppable report payload from a flat event stream.

        Returns:
            Stoppable report.
        """
        recorder = TestStoppableRecorder(nodeid="<session>", records=records)
        return cls.from_test_recorders(pytestconfig, [recorder], session_id)

    @classmethod
    def write(
        cls,
        pytestconfig: pytest.Config,
        test_recorders: list["TestStoppableRecorder"],
        session_id: str,
    ) -> None:
        """Write the stoppable report files for the current pytest session."""
        report_dir = OUTPUTS_DIR / "stoppable_opportunities_timing"
        if session_id:
            report_dir /= session_id

        report_dir.mkdir(parents=True, exist_ok=True)
        report = cls.from_test_recorders(pytestconfig, test_recorders, session_id)

        (report_dir / "report.md").write_text(report.render(), encoding="utf-8")
        (report_dir / "details.json").write_text(
            json.dumps(asdict(report), indent=2), encoding="utf-8"
        )


@dataclass
class TestStoppableRecorder:
    """Individual test stop opportunity recorder."""

    __test__ = False

    nodeid: str
    records: list[StopOpportunityTraceEvent]
    subscription: StopOpportunitySubscription | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        """Subscribe this recorder to stop-opportunity events."""
        self.subscription = Stoppable.subscribe_to_stop_opportunities(
            self.records.append,
            with_event=True,
        )

    def close(self) -> None:
        """Unsubscribe this recorder from stop-opportunity events."""
        if self.subscription is None:
            return
        Stoppable.unsubscribe_from_stop_opportunities(self.subscription)
        self.subscription = None

    def get_gap_pairs(
        self,
    ) -> list[tuple[StopOpportunityTraceEvent, StopOpportunityTraceEvent, float]]:
        """Return a list of (previous, current, gap_seconds) for all recorded events.

        Returns:
            List of gap pairs.
        """
        return [
            (previous, current, current.timestamp - previous.timestamp)
            for previous, current in zip(self.records, self.records[1:])
        ]

    def get_slow_gaps(self, threshold: float) -> list[float]:
        """Return a list of gaps that exceed the specified threshold.

        Returns:
            List of slow gap durations.
        """
        return [gap for _, _, gap in self.get_gap_pairs() if gap > threshold]


@dataclass
class SessionStoppableRecorder:
    """Session-wide stop opportunity recorder."""

    test_recorders: list[TestStoppableRecorder]


@pytest.fixture(scope="session")
def stoppable_session_recorders(
    pytestconfig: pytest.Config, session_id: str
) -> Generator[SessionStoppableRecorder, None, None]:
    """Collect per-test stop-opportunity recorders and write a session report.

    Yields:
        The session-wide recorder.
    """
    recorder = SessionStoppableRecorder(test_recorders=[])
    try:
        yield recorder
    finally:
        StoppableReport.write(pytestconfig, recorder.test_recorders, session_id)


@pytest.fixture
def stoppable_trace_recorder(
    request: pytest.FixtureRequest,
    stoppable_session_recorders: SessionStoppableRecorder,
) -> Generator[list[StopOpportunityTraceEvent], None, None]:
    """Record stop opportunities so long gaps can be inspected after a test.

    Yields:
        Recorded events.
    """
    test_recorder = TestStoppableRecorder(nodeid=request.node.nodeid, records=[])

    stoppable_session_recorders.test_recorders.append(test_recorder)
    try:
        yield test_recorder.records
    finally:
        test_recorder.close()

    slow_gaps = test_recorder.get_slow_gaps(STOPPABLE_GAP_THRESHOLD_SECONDS)
    if slow_gaps:
        pytest.fail(
            f"{test_recorder.nodeid} has {len(slow_gaps)} stoppable gaps above "
            f"{STOPPABLE_GAP_THRESHOLD_SECONDS} seconds\n"
            f"slow gaps: {slow_gaps}",
        )
