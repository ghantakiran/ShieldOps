"""Tests for shieldops.analytics.temporal_patterns -- TemporalPatternEngine."""

from __future__ import annotations

from datetime import UTC, datetime

from shieldops.analytics.temporal_patterns import (
    IncidentEvent,
    PatternConfidence,
    PatternSummary,
    PatternType,
    TemporalPattern,
    TemporalPatternEngine,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _engine(**kwargs) -> TemporalPatternEngine:
    return TemporalPatternEngine(**kwargs)


def _ts(year: int = 2026, month: int = 1, day: int = 6, hour: int = 14, minute: int = 0) -> float:
    """Return a UTC timestamp for a specific datetime.

    Default: Tuesday 2026-01-06 14:00 UTC (weekday=1).
    """
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=UTC,
    ).timestamp()


def _populate_hourly(
    eng: TemporalPatternEngine,
    service: str,
    hour: int,
    count: int,
) -> None:
    """Add *count* events all at the same hour on different days."""
    for day_offset in range(count):
        ts = _ts(day=6 + day_offset, hour=hour)
        eng.record_event(
            service=service,
            incident_type="latency",
            timestamp=ts,
        )


def _populate_daily(
    eng: TemporalPatternEngine,
    service: str,
    weekday: int,
    count: int,
) -> None:
    """Add *count* events on the same weekday across weeks.

    weekday: 0=Monday. 2026-01-05 is a Monday.
    """
    base_day = 5 + weekday  # 5=Monday Jan 5
    for week in range(count):
        ts = _ts(day=base_day + week * 7, hour=10)
        eng.record_event(
            service=service,
            incident_type="cpu-spike",
            timestamp=ts,
        )


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_pattern_type_hourly(self):
        assert PatternType.HOURLY == "hourly"

    def test_pattern_type_daily(self):
        assert PatternType.DAILY == "daily"

    def test_pattern_type_weekly(self):
        assert PatternType.WEEKLY == "weekly"

    def test_pattern_type_seasonal(self):
        assert PatternType.SEASONAL == "seasonal"

    def test_confidence_low(self):
        assert PatternConfidence.LOW == "low"

    def test_confidence_medium(self):
        assert PatternConfidence.MEDIUM == "medium"

    def test_confidence_high(self):
        assert PatternConfidence.HIGH == "high"

    def test_confidence_very_high(self):
        assert PatternConfidence.VERY_HIGH == "very_high"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_incident_event_defaults(self):
        e = IncidentEvent(
            service="api",
            incident_type="latency",
        )
        assert e.id
        assert e.severity == "warning"
        assert e.timestamp > 0
        assert e.metadata == {}
        assert e.recorded_at > 0

    def test_temporal_pattern_defaults(self):
        p = TemporalPattern(
            service="api",
            pattern_type=PatternType.HOURLY,
            description="test",
        )
        assert p.id
        assert p.occurrences == 0
        assert p.confidence == PatternConfidence.LOW
        assert p.peak_hour is None
        assert p.peak_day is None
        assert p.recommendation == ""
        assert p.detected_at > 0

    def test_pattern_summary_defaults(self):
        s = PatternSummary(service="api")
        assert s.total_events == 0
        assert s.patterns_found == 0
        assert s.top_pattern == ""
        assert s.risk_windows == []


# -------------------------------------------------------------------
# Record event
# -------------------------------------------------------------------


class TestRecordEvent:
    def test_record_basic(self):
        eng = _engine()
        e = eng.record_event(
            service="api",
            incident_type="latency",
        )
        assert e.service == "api"
        assert e.incident_type == "latency"
        assert e.id

    def test_record_with_timestamp(self):
        eng = _engine()
        ts = _ts(hour=14)
        e = eng.record_event(
            service="api",
            incident_type="latency",
            timestamp=ts,
        )
        assert e.timestamp == ts
        assert e.hour_of_day == 14

    def test_record_derives_day_of_week(self):
        eng = _engine()
        # 2026-01-06 is a Tuesday (weekday=1)
        ts = _ts(day=6)
        e = eng.record_event(
            service="api",
            incident_type="latency",
            timestamp=ts,
        )
        assert e.day_of_week == 1

    def test_record_with_severity(self):
        eng = _engine()
        e = eng.record_event(
            service="api",
            incident_type="crash",
            severity="critical",
        )
        assert e.severity == "critical"

    def test_record_with_metadata(self):
        eng = _engine()
        e = eng.record_event(
            service="api",
            incident_type="latency",
            metadata={"region": "us-east-1"},
        )
        assert e.metadata["region"] == "us-east-1"

    def test_record_trims_to_max(self):
        eng = _engine(max_events=3)
        for i in range(5):
            eng.record_event(
                service="api",
                incident_type=f"type-{i}",
            )
        events = eng.list_events(limit=100)
        assert len(events) == 3
        # Oldest trimmed; remaining are type-2, type-3, type-4
        assert events[0].incident_type == "type-2"


# -------------------------------------------------------------------
# Detect patterns - hourly
# -------------------------------------------------------------------


class TestDetectHourlyPatterns:
    def test_hourly_pattern_detected(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY]
        assert len(hourly) >= 1
        match = [p for p in hourly if p.peak_hour == 14]
        assert len(match) == 1
        assert match[0].occurrences == 5

    def test_hourly_below_threshold_not_detected(self):
        eng = _engine(min_occurrences=5)
        _populate_hourly(eng, "api", hour=14, count=3)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY]
        assert len(hourly) == 0

    def test_hourly_description_includes_hour(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=9, count=4)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY and p.peak_hour == 9]
        assert "09:00" in hourly[0].description

    def test_hourly_recommendation_present(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=3, count=4)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY]
        assert hourly[0].recommendation != ""


# -------------------------------------------------------------------
# Detect patterns - daily
# -------------------------------------------------------------------


class TestDetectDailyPatterns:
    def test_daily_pattern_detected(self):
        eng = _engine(min_occurrences=3)
        # Monday = weekday 0
        _populate_daily(eng, "api", weekday=0, count=4)
        patterns = eng.detect_patterns(service="api")
        daily = [p for p in patterns if p.pattern_type == PatternType.DAILY and p.peak_day == 0]
        assert len(daily) == 1
        assert daily[0].occurrences == 4

    def test_daily_description_includes_day_name(self):
        eng = _engine(min_occurrences=3)
        _populate_daily(eng, "api", weekday=4, count=3)
        patterns = eng.detect_patterns(service="api")
        daily = [p for p in patterns if p.pattern_type == PatternType.DAILY and p.peak_day == 4]
        assert "Friday" in daily[0].description

    def test_daily_below_threshold_not_detected(self):
        eng = _engine(min_occurrences=5)
        _populate_daily(eng, "api", weekday=0, count=2)
        patterns = eng.detect_patterns(service="api")
        daily = [p for p in patterns if p.pattern_type == PatternType.DAILY]
        assert len(daily) == 0


# -------------------------------------------------------------------
# Confidence levels
# -------------------------------------------------------------------


class TestConfidenceLevels:
    def test_low_confidence(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=10, count=3)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY]
        assert hourly[0].confidence == PatternConfidence.LOW

    def test_medium_confidence(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=10, count=5)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY and p.peak_hour == 10]
        assert hourly[0].confidence == PatternConfidence.MEDIUM

    def test_high_confidence(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=10, count=10)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY and p.peak_hour == 10]
        assert hourly[0].confidence == PatternConfidence.HIGH

    def test_very_high_confidence(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=10, count=20)
        patterns = eng.detect_patterns(service="api")
        hourly = [p for p in patterns if p.pattern_type == PatternType.HOURLY and p.peak_hour == 10]
        assert hourly[0].confidence == PatternConfidence.VERY_HIGH


# -------------------------------------------------------------------
# Service summary
# -------------------------------------------------------------------


class TestServiceSummary:
    def test_summary_basic(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        s = eng.get_service_summary("api")
        assert s.service == "api"
        assert s.total_events == 5
        assert s.patterns_found >= 1

    def test_summary_top_pattern(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        s = eng.get_service_summary("api")
        assert s.top_pattern != ""

    def test_summary_no_events(self):
        eng = _engine()
        s = eng.get_service_summary("unknown")
        assert s.total_events == 0
        assert s.patterns_found == 0
        assert s.top_pattern == ""

    def test_summary_risk_windows(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=2, count=5)
        s = eng.get_service_summary("api")
        assert len(s.risk_windows) >= 1
        assert any("02:00" in w for w in s.risk_windows)


# -------------------------------------------------------------------
# Risk windows
# -------------------------------------------------------------------


class TestRiskWindows:
    def test_risk_windows_returned(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        windows = eng.get_risk_windows("api")
        assert len(windows) >= 1
        assert windows[0]["hour"] == 14
        assert windows[0]["incident_count"] == 5
        assert windows[0]["service"] == "api"

    def test_risk_windows_label_format(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=23, count=4)
        windows = eng.get_risk_windows("api")
        w = [x for x in windows if x["hour"] == 23]
        assert w[0]["label"] == "23:00-00:00 UTC"

    def test_risk_windows_no_events(self):
        eng = _engine()
        assert eng.get_risk_windows("unknown") == []

    def test_risk_windows_below_threshold(self):
        eng = _engine(min_occurrences=5)
        _populate_hourly(eng, "api", hour=14, count=2)
        windows = eng.get_risk_windows("api")
        assert len(windows) == 0

    def test_risk_windows_top_5_only(self):
        eng = _engine(min_occurrences=1)
        # Create events at 8 different hours
        for h in range(8):
            _populate_hourly(eng, "api", hour=h, count=2)
        windows = eng.get_risk_windows("api")
        assert len(windows) <= 5


# -------------------------------------------------------------------
# Clear events
# -------------------------------------------------------------------


class TestClearEvents:
    def test_clear_all(self):
        eng = _engine()
        eng.record_event("api", "latency")
        eng.record_event("api", "latency")
        removed = eng.clear_events()
        assert removed == 2
        assert eng.list_events() == []

    def test_clear_before_timestamp(self):
        eng = _engine()
        ts_old = _ts(day=6, hour=10)
        ts_new = _ts(day=8, hour=10)
        eng.record_event("api", "latency", timestamp=ts_old)
        eng.record_event("api", "latency", timestamp=ts_new)
        cutoff = _ts(day=7, hour=0)
        removed = eng.clear_events(before_timestamp=cutoff)
        assert removed == 1
        remaining = eng.list_events()
        assert len(remaining) == 1
        assert remaining[0].timestamp == ts_new

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_events() == 0

    def test_clear_before_keeps_all_when_none_older(self):
        eng = _engine()
        ts_new = _ts(day=10, hour=10)
        eng.record_event("api", "latency", timestamp=ts_new)
        cutoff = _ts(day=5, hour=0)
        removed = eng.clear_events(before_timestamp=cutoff)
        assert removed == 0
        assert len(eng.list_events()) == 1


# -------------------------------------------------------------------
# Multi-service detection
# -------------------------------------------------------------------


class TestMultiService:
    def test_detect_across_services(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=4)
        _populate_hourly(eng, "web", hour=9, count=3)
        patterns = eng.detect_patterns()
        services = {p.service for p in patterns}
        assert "api" in services
        assert "web" in services

    def test_filter_by_service(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=4)
        _populate_hourly(eng, "web", hour=9, count=3)
        patterns = eng.detect_patterns(service="api")
        assert all(p.service == "api" for p in patterns)

    def test_get_patterns_filter_by_type(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        _populate_daily(eng, "api", weekday=0, count=4)
        hourly = eng.get_patterns(
            service="api",
            pattern_type=PatternType.HOURLY,
        )
        assert all(p.pattern_type == PatternType.HOURLY for p in hourly)


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        eng = _engine()
        s = eng.get_stats()
        assert s["total_events"] == 0
        assert s["services"] == 0
        assert s["patterns_detected"] == 0

    def test_stats_with_data(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=5)
        s = eng.get_stats()
        assert s["total_events"] == 5
        assert s["services"] == 1
        assert s["patterns_detected"] >= 1

    def test_stats_multiple_services(self):
        eng = _engine(min_occurrences=3)
        _populate_hourly(eng, "api", hour=14, count=4)
        _populate_hourly(eng, "web", hour=9, count=3)
        s = eng.get_stats()
        assert s["services"] == 2
