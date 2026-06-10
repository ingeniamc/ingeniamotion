import json
import math
import statistics
import warnings
from collections import Counter
from collections.abc import Generator
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pytest
import traceback

from ingeniamotion.wizard_tests.stoppable import StopOpportunityTraceEvent, Stoppable
from tests.outputs import OUTPUTS_DIR

STOPPABLE_GAP_THRESHOLD_SECONDS = 0.5
STOPPABLE_GOOD_ENOUGH_GAP_SECONDS = 0.2
STOPPABLE_REPORT_DIR = OUTPUTS_DIR / "stoppable_opportunities_timing"
STOPPABLE_REPORT_MD = STOPPABLE_REPORT_DIR / "report.md"
STOPPABLE_REPORT_JSON = STOPPABLE_REPORT_DIR / "details.json"
STOPPABLE_REPORT_HISTOGRAM = STOPPABLE_REPORT_DIR / "histogram.png"


@dataclass(frozen=True)
class StopGapRecord:
    """Gap observed between two stop opportunities."""

    previous_timestamp: float
    current_timestamp: float
    gap_seconds: float
    source_file: str
    callsite: str


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


@dataclass(frozen=True)
class GapHotspot:
    """Grouped summary for the most expensive locations."""

    label: str
    total_gap_seconds: float
    gap_count: int
    average_gap_seconds: float
    max_gap_seconds: float


@dataclass(frozen=True)
class StoppableReport:
    """Full stoppable report payload written to disk."""

    generated_at: str
    pytest_root: str
    report_dir: str
    threshold_seconds: float
    opportunities: int
    gap_count: int
    unique_callsites: int
    unique_source_files: int
    statistics: Optional[StopGapStatistics]
    top_gap_records: list[StopGapRecord]
    callsite_hotspots: list[GapHotspot]
    source_file_hotspots: list[GapHotspot]
    gap_records: list[StopGapRecord]
    histogram_written: bool


def _relative_path(rootpath: Path, filename: str) -> str:
    """Return a path relative to the pytest root when possible."""
    path = Path(filename)
    try:
        return str(path.resolve().relative_to(rootpath.resolve()))
    except ValueError:
        return str(path.resolve())


def _stoppable_callsite(traceback_frames: tuple[traceback.FrameSummary, ...]) -> traceback.FrameSummary:
    """Return the most useful non-stoppable frame for reporting."""
    for frame in reversed(traceback_frames):
        if Path(frame.filename).name == "stoppable.py":
            continue
        return frame
    return traceback_frames[-1]


def _traceback_location(
    rootpath: Path, traceback_frames: tuple[traceback.FrameSummary, ...]
) -> tuple[str, str]:
    """Return a displayable source file and callsite string."""
    if not traceback_frames:
        return "<unknown>", "<unknown>"
    frame = _stoppable_callsite(traceback_frames)
    source_file = _relative_path(rootpath, frame.filename)
    return source_file, f"{source_file}:{frame.lineno} in {frame.name}"


def _build_stop_gap_records(
    rootpath: Path, records: list[StopOpportunityTraceEvent]
) -> list[StopGapRecord]:
    """Convert raw stop-opportunity events into gap records."""
    gap_records = []
    for previous, current in zip(records, records[1:]):
        source_file, callsite = _traceback_location(rootpath, current.traceback)
        gap_records.append(
            StopGapRecord(
                previous_timestamp=previous.timestamp,
                current_timestamp=current.timestamp,
                gap_seconds=current.timestamp - previous.timestamp,
                source_file=source_file,
                callsite=callsite,
            )
        )
    return gap_records


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Return a simple percentile from a sorted list."""
    if not sorted_values:
        return 0.0
    index = int(round((len(sorted_values) - 1) * percentile))
    return sorted_values[index]


def _build_gap_statistics(gaps: list[float]) -> Optional[StopGapStatistics]:
    """Build aggregate statistics for a list of gap durations."""
    if not gaps:
        return None
    sorted_gaps = sorted(gaps)
    slow_gap_count = sum(1 for gap in sorted_gaps if gap > STOPPABLE_GAP_THRESHOLD_SECONDS)
    return StopGapStatistics(
        min_gap_seconds=sorted_gaps[0],
        mean_gap_seconds=statistics.fmean(sorted_gaps),
        median_gap_seconds=statistics.median(sorted_gaps),
        p95_gap_seconds=_percentile(sorted_gaps, 0.95),
        max_gap_seconds=sorted_gaps[-1],
        slow_gap_count=slow_gap_count,
        slow_gap_ratio=slow_gap_count / len(sorted_gaps),
    )


def _build_hotspots(
    gap_records: list[StopGapRecord], key_func: Callable[[StopGapRecord], str], limit: int = 10
) -> list[GapHotspot]:
    """Build a ranked summary of the hottest callsites or source files."""
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
            GapHotspot(
                label=label,
                total_gap_seconds=total_gap,
                gap_count=gap_count,
                average_gap_seconds=total_gap / gap_count,
                max_gap_seconds=max_gap_by_label[label],
            )
        )
    return hotspots


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a simple Markdown table."""
    if not rows:
        return ["_(none)_"]

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def format_row(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(values)) + " |"

    lines = [format_row(headers), "| " + " | ".join("-" * width for width in widths) + " |"]
    lines.extend(format_row(row) for row in rows)
    return lines


def _format_seconds(value: float) -> str:
    """Format a duration in seconds for human-readable reports."""
    return f"{value:.6f}s"


def _render_stoppable_report(report: StoppableReport) -> str:
    """Render the stoppable report as Markdown."""
    lines = [
        "# Stoppable gap report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- pytest root: `{report.pytest_root}`",
        f"- report directory: `{report.report_dir}`",
        f"- gap threshold: {_format_seconds(report.threshold_seconds)}",
        f"- good-enough gap cutoff: {_format_seconds(STOPPABLE_GOOD_ENOUGH_GAP_SECONDS)}",
        f"- stop opportunities: {report.opportunities}",
        f"- recorded gaps: {report.gap_count}",
        f"- distinct callsites: {report.unique_callsites}",
        f"- distinct source files: {report.unique_source_files}",
        f"- histogram image: {'written' if report.histogram_written else 'not generated'}",
        "",
    ]

    if report.statistics is None:
        lines.extend([
            "No stoppable gaps were recorded.",
            "",
            "The JSON report still contains the captured stop-opportunity events.",
        ])
    else:
        stats_rows = [
            ["Min", _format_seconds(report.statistics.min_gap_seconds)],
            ["Mean", _format_seconds(report.statistics.mean_gap_seconds)],
            ["Median", _format_seconds(report.statistics.median_gap_seconds)],
            ["p95", _format_seconds(report.statistics.p95_gap_seconds)],
            ["Max", _format_seconds(report.statistics.max_gap_seconds)],
            ["Slow gaps", str(report.statistics.slow_gap_count)],
            ["Slow gap rate", f"{report.statistics.slow_gap_ratio:.1%}"],
        ]
        lines.extend(["## Gap statistics", ""])
        lines.extend(_markdown_table(["Metric", "Value"], stats_rows))
        lines.append("")

        if report.statistics.max_gap_seconds >= STOPPABLE_GOOD_ENOUGH_GAP_SECONDS:
            top_gap_rows = [
                [
                    str(index),
                    _format_seconds(record.gap_seconds),
                    record.callsite,
                    record.source_file,
                ]
                for index, record in enumerate(report.top_gap_records, start=1)
            ]
            lines.extend(["## Worst individual gaps", ""])
            lines.extend(
                _markdown_table(["#", "Gap", "Callsite", "Source file"], top_gap_rows)
            )
            lines.append("")
        else:
            lines.extend([
                "## Worst individual gaps",
                "",
                f"All gaps are below {_format_seconds(STOPPABLE_GOOD_ENOUGH_GAP_SECONDS)}; no gap ranking is shown.",
                "",
            ])

        callsite_rows = [
            [
                str(index),
                hotspot.label,
                _format_seconds(hotspot.total_gap_seconds),
                str(hotspot.gap_count),
                _format_seconds(hotspot.average_gap_seconds),
                _format_seconds(hotspot.max_gap_seconds),
            ]
            for index, hotspot in enumerate(report.callsite_hotspots, start=1)
        ]
        lines.extend(["## Worst callsites by total gap", ""])
        lines.extend(
            _markdown_table(["#", "Callsite", "Total gap", "Count", "Average", "Max"], callsite_rows)
        )
        lines.append("")

        file_rows = [
            [
                str(index),
                hotspot.label,
                _format_seconds(hotspot.total_gap_seconds),
                str(hotspot.gap_count),
                _format_seconds(hotspot.average_gap_seconds),
                _format_seconds(hotspot.max_gap_seconds),
            ]
            for index, hotspot in enumerate(report.source_file_hotspots, start=1)
        ]
        lines.extend(["## Worst source files by total gap", ""])
        lines.extend(
            _markdown_table(["#", "Source file", "Total gap", "Count", "Average", "Max"], file_rows)
        )
        lines.append("")

    lines.extend(
        [
            "## Artifacts",
            "",
            f"- JSON: `{report.report_dir}/details.json`",
            f"- Histogram: `{report.report_dir}/histogram.png`",
        ]
    )
    return "\n".join(lines)


def _write_histogram(gaps: list[float]) -> bool:
    """Write a histogram image for the recorded gaps when possible."""
    if not gaps:
        return False

    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        figure, axis = plt.subplots(figsize=(10, 6))
        bin_count = min(20, max(5, int(math.sqrt(len(gaps)))))
        axis.hist(gaps, bins=bin_count, color="#2b6cb0", edgecolor="black")
        axis.set_title("Stoppable gap distribution")
        axis.set_xlabel("Seconds between stop opportunities")
        axis.set_ylabel("Count")
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        figure.savefig(STOPPABLE_REPORT_HISTOGRAM, dpi=150)
        plt.close(figure)
        return True
    except Exception as exc:  # pragma: no cover - report generation should never fail tests
        warnings.warn(f"Could not write stoppable histogram: {exc}", stacklevel=2)
        return False


def _build_stoppable_report(
    pytestconfig: pytest.Config, records: list[StopOpportunityTraceEvent]
) -> StoppableReport:
    """Build the structured stoppable report payload."""
    now = datetime.now()
    generated_at = now.astimezone().isoformat(timespec="seconds")
    gap_records = _build_stop_gap_records(pytestconfig.rootpath, records)
    gaps = [record.gap_seconds for record in gap_records]
    statistics = _build_gap_statistics(gaps)
    callsite_hotspots = _build_hotspots(gap_records, lambda record: record.callsite)
    source_file_hotspots = _build_hotspots(gap_records, lambda record: record.source_file)
    top_gap_records = sorted(gap_records, key=lambda item: item.gap_seconds, reverse=True)[:10]
    histogram_written = _write_histogram(gaps)

    return StoppableReport(
        generated_at=generated_at,
        pytest_root=str(pytestconfig.rootpath),
        report_dir=str(STOPPABLE_REPORT_DIR),
        threshold_seconds=STOPPABLE_GAP_THRESHOLD_SECONDS,
        opportunities=len(records),
        gap_count=len(gap_records),
        unique_callsites=len({record.callsite for record in gap_records}),
        unique_source_files=len({record.source_file for record in gap_records}),
        statistics=statistics,
        top_gap_records=top_gap_records,
        callsite_hotspots=callsite_hotspots,
        source_file_hotspots=source_file_hotspots,
        gap_records=gap_records,
        histogram_written=histogram_written,
    )


def _write_stoppable_report(
    pytestconfig: pytest.Config, records: list[StopOpportunityTraceEvent]
) -> None:
    """Write the stoppable report files for the current pytest session."""
    STOPPABLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = _build_stoppable_report(pytestconfig, records)

    STOPPABLE_REPORT_MD.write_text(_render_stoppable_report(report), encoding="utf-8")
    STOPPABLE_REPORT_JSON.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def stoppable_session_report(pytestconfig: pytest.Config) -> Generator[None, None, None]:
    """Collect every stop opportunity and write a session report."""

    records: list[StopOpportunityTraceEvent] = []

    def record_call(event: StopOpportunityTraceEvent) -> None:
        records.append(event)

    subscription = Stoppable.subscribe_to_stop_opportunities(record_call, with_event=True)
    try:
        yield
    finally:
        Stoppable.unsubscribe_from_stop_opportunities(subscription)
        try:
            _write_stoppable_report(pytestconfig, records)
        except Exception as exc:  # pragma: no cover - report generation should never fail tests
            warnings.warn(f"Could not write stoppable report: {exc}", stacklevel=2)


@pytest.fixture
def stoppable_trace_recorder(
    request: pytest.FixtureRequest,
) -> Generator[list[StopOpportunityTraceEvent], None, None]:
    """Record stop opportunities so long gaps can be inspected after a test."""

    records: list[StopOpportunityTraceEvent] = []

    def record_call(event: StopOpportunityTraceEvent) -> None:
        records.append(event)

    subscription = Stoppable.subscribe_to_stop_opportunities(record_call, with_event=True)
    try:
        yield records
    finally:
        Stoppable.unsubscribe_from_stop_opportunities(subscription)

    if len(records) > 1:
        gap_pairs = [
            (previous, current, current.timestamp - previous.timestamp)
            for previous, current in zip(records, records[1:])
        ]
        slow_gaps = [
            gap for _previous, _current, gap in gap_pairs if gap > STOPPABLE_GAP_THRESHOLD_SECONDS
        ]
        if slow_gaps:
            formatted_gaps = [
                (previous.timestamp, current.timestamp, gap) for previous, current, gap in gap_pairs
            ]
            pytest.fail(
                f"{request.node.nodeid} has {len(slow_gaps)} stoppable gaps above "
                f"{STOPPABLE_GAP_THRESHOLD_SECONDS} seconds\n"
                f"all gaps: {formatted_gaps}\n"
                f"slow gaps: {slow_gaps}",
            )
