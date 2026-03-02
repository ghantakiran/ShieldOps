"""Tests for shieldops.incidents.forensic_timeline_builder — ForensicTimelineBuilder."""

from __future__ import annotations

from shieldops.incidents.forensic_timeline_builder import (
    CorrelationConfidence,
    EventSignificance,
    ForensicTimelineBuilder,
    TimelineAnalysis,
    TimelineRecord,
    TimelineReport,
    TimelineSource,
)


def _engine(**kw) -> ForensicTimelineBuilder:
    return ForensicTimelineBuilder(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_system_log(self):
        assert TimelineSource.SYSTEM_LOG == "system_log"

    def test_source_network_log(self):
        assert TimelineSource.NETWORK_LOG == "network_log"

    def test_source_application_log(self):
        assert TimelineSource.APPLICATION_LOG == "application_log"

    def test_source_security_log(self):
        assert TimelineSource.SECURITY_LOG == "security_log"

    def test_source_cloud_audit(self):
        assert TimelineSource.CLOUD_AUDIT == "cloud_audit"

    def test_significance_critical(self):
        assert EventSignificance.CRITICAL == "critical"

    def test_significance_high(self):
        assert EventSignificance.HIGH == "high"

    def test_significance_medium(self):
        assert EventSignificance.MEDIUM == "medium"

    def test_significance_low(self):
        assert EventSignificance.LOW == "low"

    def test_significance_background(self):
        assert EventSignificance.BACKGROUND == "background"

    def test_confidence_confirmed(self):
        assert CorrelationConfidence.CONFIRMED == "confirmed"

    def test_confidence_high(self):
        assert CorrelationConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert CorrelationConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert CorrelationConfidence.LOW == "low"

    def test_confidence_unconfirmed(self):
        assert CorrelationConfidence.UNCONFIRMED == "unconfirmed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_timeline_record_defaults(self):
        r = TimelineRecord()
        assert r.id
        assert r.event_name == ""
        assert r.timeline_source == TimelineSource.SYSTEM_LOG
        assert r.event_significance == EventSignificance.CRITICAL
        assert r.correlation_confidence == CorrelationConfidence.CONFIRMED
        assert r.accuracy_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_timeline_analysis_defaults(self):
        a = TimelineAnalysis()
        assert a.id
        assert a.event_name == ""
        assert a.timeline_source == TimelineSource.SYSTEM_LOG
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_timeline_report_defaults(self):
        r = TimelineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_accuracy_count == 0
        assert r.avg_accuracy_score == 0.0
        assert r.by_source == {}
        assert r.by_significance == {}
        assert r.by_confidence == {}
        assert r.top_low_accuracy == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_basic(self):
        eng = _engine()
        r = eng.record_event(
            event_name="ssh-login-attempt",
            timeline_source=TimelineSource.SECURITY_LOG,
            event_significance=EventSignificance.HIGH,
            correlation_confidence=CorrelationConfidence.HIGH,
            accuracy_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.event_name == "ssh-login-attempt"
        assert r.timeline_source == TimelineSource.SECURITY_LOG
        assert r.event_significance == EventSignificance.HIGH
        assert r.correlation_confidence == CorrelationConfidence.HIGH
        assert r.accuracy_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_event(event_name=f"EVT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        r = eng.record_event(
            event_name="ssh-login-attempt",
            event_significance=EventSignificance.CRITICAL,
        )
        result = eng.get_event(r.id)
        assert result is not None
        assert result.event_significance == EventSignificance.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_event(event_name="EVT-001")
        eng.record_event(event_name="EVT-002")
        assert len(eng.list_events()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_event(
            event_name="EVT-001",
            timeline_source=TimelineSource.SYSTEM_LOG,
        )
        eng.record_event(
            event_name="EVT-002",
            timeline_source=TimelineSource.NETWORK_LOG,
        )
        results = eng.list_events(timeline_source=TimelineSource.SYSTEM_LOG)
        assert len(results) == 1

    def test_filter_by_significance(self):
        eng = _engine()
        eng.record_event(
            event_name="EVT-001",
            event_significance=EventSignificance.CRITICAL,
        )
        eng.record_event(
            event_name="EVT-002",
            event_significance=EventSignificance.LOW,
        )
        results = eng.list_events(
            event_significance=EventSignificance.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_event(event_name="EVT-001", team="security")
        eng.record_event(event_name="EVT-002", team="platform")
        results = eng.list_events(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_event(event_name=f"EVT-{i}")
        assert len(eng.list_events(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            event_name="ssh-login-attempt",
            timeline_source=TimelineSource.SECURITY_LOG,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="timeline accuracy check",
        )
        assert a.event_name == "ssh-login-attempt"
        assert a.timeline_source == TimelineSource.SECURITY_LOG
        assert a.analysis_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(event_name=f"EVT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_event_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeEventDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_event(
            event_name="EVT-001",
            timeline_source=TimelineSource.SYSTEM_LOG,
            accuracy_score=90.0,
        )
        eng.record_event(
            event_name="EVT-002",
            timeline_source=TimelineSource.SYSTEM_LOG,
            accuracy_score=70.0,
        )
        result = eng.analyze_event_distribution()
        assert "system_log" in result
        assert result["system_log"]["count"] == 2
        assert result["system_log"]["avg_accuracy_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_event_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_accuracy_events
# ---------------------------------------------------------------------------


class TestIdentifyLowAccuracyEvents:
    def test_detects_below_threshold(self):
        eng = _engine(accuracy_threshold=80.0)
        eng.record_event(event_name="EVT-001", accuracy_score=60.0)
        eng.record_event(event_name="EVT-002", accuracy_score=90.0)
        results = eng.identify_low_accuracy_events()
        assert len(results) == 1
        assert results[0]["event_name"] == "EVT-001"

    def test_sorted_ascending(self):
        eng = _engine(accuracy_threshold=80.0)
        eng.record_event(event_name="EVT-001", accuracy_score=50.0)
        eng.record_event(event_name="EVT-002", accuracy_score=30.0)
        results = eng.identify_low_accuracy_events()
        assert len(results) == 2
        assert results[0]["accuracy_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_accuracy_events() == []


# ---------------------------------------------------------------------------
# rank_by_accuracy
# ---------------------------------------------------------------------------


class TestRankByAccuracy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_event(event_name="EVT-001", service="auth-svc", accuracy_score=90.0)
        eng.record_event(event_name="EVT-002", service="api-gw", accuracy_score=50.0)
        results = eng.rank_by_accuracy()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_accuracy_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy() == []


# ---------------------------------------------------------------------------
# detect_timeline_trends
# ---------------------------------------------------------------------------


class TestDetectTimelineTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(event_name="EVT-001", analysis_score=50.0)
        result = eng.detect_timeline_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(event_name="EVT-001", analysis_score=20.0)
        eng.add_analysis(event_name="EVT-002", analysis_score=20.0)
        eng.add_analysis(event_name="EVT-003", analysis_score=80.0)
        eng.add_analysis(event_name="EVT-004", analysis_score=80.0)
        result = eng.detect_timeline_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_timeline_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(accuracy_threshold=80.0)
        eng.record_event(
            event_name="ssh-login-attempt",
            timeline_source=TimelineSource.SECURITY_LOG,
            event_significance=EventSignificance.HIGH,
            correlation_confidence=CorrelationConfidence.HIGH,
            accuracy_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TimelineReport)
        assert report.total_records == 1
        assert report.low_accuracy_count == 1
        assert len(report.top_low_accuracy) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_event(event_name="EVT-001")
        eng.add_analysis(event_name="EVT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_event(
            event_name="EVT-001",
            timeline_source=TimelineSource.SYSTEM_LOG,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "system_log" in stats["source_distribution"]
