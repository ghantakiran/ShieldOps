"""Tests for shieldops.incidents.response_time — IncidentResponseTimeAnalyzer."""

from __future__ import annotations

from shieldops.incidents.response_time import (
    IncidentResponseTimeAnalyzer,
    PhaseBreakdown,
    ResponsePhase,
    ResponseSpeed,
    ResponseTimeRecord,
    ResponseTimeReport,
    ResponseTrend,
)


def _engine(**kw) -> IncidentResponseTimeAnalyzer:
    return IncidentResponseTimeAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResponsePhase (5)
    def test_phase_detection(self):
        assert ResponsePhase.DETECTION == "detection"

    def test_phase_triage(self):
        assert ResponsePhase.TRIAGE == "triage"

    def test_phase_investigation(self):
        assert ResponsePhase.INVESTIGATION == "investigation"

    def test_phase_mitigation(self):
        assert ResponsePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert ResponsePhase.RESOLUTION == "resolution"

    # ResponseSpeed (5)
    def test_speed_excellent(self):
        assert ResponseSpeed.EXCELLENT == "excellent"

    def test_speed_good(self):
        assert ResponseSpeed.GOOD == "good"

    def test_speed_acceptable(self):
        assert ResponseSpeed.ACCEPTABLE == "acceptable"

    def test_speed_slow(self):
        assert ResponseSpeed.SLOW == "slow"

    def test_speed_critical(self):
        assert ResponseSpeed.CRITICAL == "critical"

    # ResponseTrend (5)
    def test_trend_improving(self):
        assert ResponseTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert ResponseTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert ResponseTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert ResponseTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert ResponseTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_response_time_record_defaults(self):
        r = ResponseTimeRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.phase == ResponsePhase.DETECTION
        assert r.response_minutes == 0.0
        assert r.speed == ResponseSpeed.ACCEPTABLE
        assert r.team == ""
        assert r.service == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_phase_breakdown_defaults(self):
        r = PhaseBreakdown()
        assert r.id
        assert r.incident_id == ""
        assert r.phase == ResponsePhase.DETECTION
        assert r.start_minutes == 0.0
        assert r.end_minutes == 0.0
        assert r.duration_minutes == 0.0
        assert r.created_at > 0

    def test_response_time_report_defaults(self):
        r = ResponseTimeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_breakdowns == 0
        assert r.avg_response_minutes == 0.0
        assert r.by_phase == {}
        assert r.by_speed == {}
        assert r.by_team == []
        assert r.slow_incidents == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_response
# -------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            "inc-1",
            phase=ResponsePhase.TRIAGE,
            speed=ResponseSpeed.GOOD,
        )
        assert r.incident_id == "inc-1"
        assert r.phase == ResponsePhase.TRIAGE

    def test_with_response_minutes(self):
        eng = _engine()
        r = eng.record_response("inc-2", response_minutes=45.0)
        assert r.response_minutes == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(f"inc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_response
# -------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response("inc-1")
        assert eng.get_response(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# -------------------------------------------------------------------
# list_responses
# -------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response("inc-1")
        eng.record_response("inc-2")
        assert len(eng.list_responses()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_response("inc-1", phase=ResponsePhase.TRIAGE)
        eng.record_response("inc-2", phase=ResponsePhase.DETECTION)
        results = eng.list_responses(phase=ResponsePhase.TRIAGE)
        assert len(results) == 1

    def test_filter_by_speed(self):
        eng = _engine()
        eng.record_response("inc-1", speed=ResponseSpeed.SLOW)
        eng.record_response("inc-2", speed=ResponseSpeed.EXCELLENT)
        results = eng.list_responses(speed=ResponseSpeed.SLOW)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_response("inc-1", team="alpha")
        eng.record_response("inc-2", team="beta")
        results = eng.list_responses(team="alpha")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_breakdown
# -------------------------------------------------------------------


class TestAddBreakdown:
    def test_basic(self):
        eng = _engine()
        b = eng.add_breakdown(
            "inc-1",
            phase=ResponsePhase.INVESTIGATION,
            start_minutes=5.0,
            end_minutes=20.0,
            duration_minutes=15.0,
        )
        assert b.incident_id == "inc-1"
        assert b.duration_minutes == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_breakdown(f"inc-{i}")
        assert len(eng._breakdowns) == 2


# -------------------------------------------------------------------
# analyze_response_by_phase
# -------------------------------------------------------------------


class TestAnalyzeResponseByPhase:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-1", phase=ResponsePhase.TRIAGE, response_minutes=10.0)
        eng.record_response("inc-2", phase=ResponsePhase.TRIAGE, response_minutes=20.0)
        eng.record_response("inc-3", phase=ResponsePhase.DETECTION, response_minutes=5.0)
        results = eng.analyze_response_by_phase()
        assert len(results) == 2
        assert results[0]["phase"] == "triage"
        assert results[0]["avg_response_minutes"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_response_by_phase() == []


# -------------------------------------------------------------------
# identify_slow_responses
# -------------------------------------------------------------------


class TestIdentifySlowResponses:
    def test_with_slow(self):
        eng = _engine(max_response_time_minutes=30.0)
        eng.record_response("inc-1", response_minutes=45.0)
        eng.record_response("inc-2", response_minutes=10.0)
        results = eng.identify_slow_responses()
        assert len(results) == 1
        assert results[0]["incident_id"] == "inc-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_responses() == []


# -------------------------------------------------------------------
# rank_by_response_time
# -------------------------------------------------------------------


class TestRankByResponseTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-1", team="alpha", response_minutes=40.0)
        eng.record_response("inc-2", team="alpha", response_minutes=20.0)
        eng.record_response("inc-3", team="beta", response_minutes=5.0)
        results = eng.rank_by_response_time()
        assert results[0]["team"] == "alpha"
        assert results[0]["avg_response_minutes"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# -------------------------------------------------------------------
# detect_response_trends
# -------------------------------------------------------------------


class TestDetectResponseTrends:
    def test_degrading_trend(self):
        eng = _engine()
        eng.record_response("inc-1", team="alpha", response_minutes=5.0)
        eng.record_response("inc-2", team="alpha", response_minutes=6.0)
        eng.record_response("inc-3", team="alpha", response_minutes=20.0)
        eng.record_response("inc-4", team="alpha", response_minutes=25.0)
        results = eng.detect_response_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "degrading"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_response("inc-1", team="alpha", response_minutes=5.0)
        results = eng.detect_response_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        eng.record_response("inc-1", team="alpha", response_minutes=10.0)
        eng.record_response("inc-2", team="alpha", response_minutes=11.0)
        eng.record_response("inc-3", team="alpha", response_minutes=10.0)
        eng.record_response("inc-4", team="alpha", response_minutes=12.0)
        results = eng.detect_response_trends()
        assert results[0]["trend"] == "stable"


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_response("inc-1", phase=ResponsePhase.TRIAGE, response_minutes=10.0)
        eng.record_response("inc-2", phase=ResponsePhase.DETECTION, response_minutes=5.0)
        eng.add_breakdown("inc-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_breakdowns == 1
        assert report.by_phase != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response("inc-1")
        eng.add_breakdown("inc-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._breakdowns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response("inc-1", phase=ResponsePhase.TRIAGE)
        eng.record_response("inc-2", phase=ResponsePhase.DETECTION)
        eng.add_breakdown("inc-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_breakdowns"] == 1
        assert stats["unique_incidents"] == 2
