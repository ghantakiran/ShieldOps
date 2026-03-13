"""Tests for AvailabilityPatternEngine."""

from __future__ import annotations

from shieldops.sla.availability_pattern_engine import (
    AvailabilityPatternEngine,
    AvailabilityTrend,
    PatternType,
    TimeWindow,
)


def _engine(**kw) -> AvailabilityPatternEngine:
    return AvailabilityPatternEngine(**kw)


class TestEnums:
    def test_time_window_values(self):
        for v in TimeWindow:
            assert isinstance(v.value, str)

    def test_availability_trend_values(self):
        for v in AvailabilityTrend:
            assert isinstance(v.value, str)

    def test_pattern_type_values(self):
        for v in PatternType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service_id="s1")
        assert r.service_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service_id=f"s-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            time_window=TimeWindow.MAINTENANCE,
            pattern_type=PatternType.PERIODIC,
            availability_pct=98.5,
            outage_minutes=15.0,
            occurrences=3,
        )
        assert r.availability_pct == 98.5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", availability_pct=99.5)
        a = eng.process(r.id)
        assert hasattr(a, "service_id")
        assert a.service_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_recurring_detected(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            pattern_type=PatternType.PERIODIC,
        )
        a = eng.process(r.id)
        assert a.recurring is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeTemporalAvailabilityPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", availability_pct=99.5, outage_minutes=5.0)
        result = eng.compute_temporal_availability_patterns()
        assert len(result) == 1
        assert result[0]["service_id"] == "s1"

    def test_empty(self):
        assert _engine().compute_temporal_availability_patterns() == []


class TestDetectRecurringUnavailability:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_id="s1",
            pattern_type=PatternType.PERIODIC,
            outage_minutes=10.0,
            occurrences=5,
        )
        result = eng.detect_recurring_unavailability()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_recurring_unavailability() == []


class TestRankTimeWindowsByOutageRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_id="s1",
            time_window=TimeWindow.PEAK_HOURS,
            outage_minutes=20.0,
        )
        eng.add_record(
            service_id="s2",
            time_window=TimeWindow.OFF_HOURS,
            outage_minutes=5.0,
        )
        result = eng.rank_time_windows_by_outage_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_time_windows_by_outage_risk() == []
