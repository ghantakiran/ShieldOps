"""Tests for shieldops.incidents.incident_debrief — IncidentDebriefTracker."""

from __future__ import annotations

from shieldops.incidents.incident_debrief import (
    ActionItemStatus,
    DebriefMetric,
    DebriefQuality,
    DebriefRecord,
    DebriefStatus,
    IncidentDebriefReport,
    IncidentDebriefTracker,
)


def _engine(**kw) -> IncidentDebriefTracker:
    return IncidentDebriefTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_scheduled(self):
        assert DebriefStatus.SCHEDULED == "scheduled"

    def test_status_in_progress(self):
        assert DebriefStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert DebriefStatus.COMPLETED == "completed"

    def test_status_skipped(self):
        assert DebriefStatus.SKIPPED == "skipped"

    def test_status_overdue(self):
        assert DebriefStatus.OVERDUE == "overdue"

    def test_quality_excellent(self):
        assert DebriefQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert DebriefQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert DebriefQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert DebriefQuality.POOR == "poor"

    def test_quality_missing(self):
        assert DebriefQuality.MISSING == "missing"

    def test_action_open(self):
        assert ActionItemStatus.OPEN == "open"

    def test_action_in_progress(self):
        assert ActionItemStatus.IN_PROGRESS == "in_progress"

    def test_action_completed(self):
        assert ActionItemStatus.COMPLETED == "completed"

    def test_action_blocked(self):
        assert ActionItemStatus.BLOCKED == "blocked"

    def test_action_cancelled(self):
        assert ActionItemStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_debrief_record_defaults(self):
        r = DebriefRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.debrief_status == DebriefStatus.SCHEDULED
        assert r.debrief_quality == DebriefQuality.ADEQUATE
        assert r.action_item_status == ActionItemStatus.OPEN
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_debrief_metric_defaults(self):
        m = DebriefMetric()
        assert m.id
        assert m.incident_id == ""
        assert m.debrief_status == DebriefStatus.SCHEDULED
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_incident_debrief_report_defaults(self):
        r = IncidentDebriefReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.low_quality_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_status == {}
        assert r.by_quality == {}
        assert r.by_action_status == {}
        assert r.top_low_quality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_debrief
# ---------------------------------------------------------------------------


class TestRecordDebrief:
    def test_basic(self):
        eng = _engine()
        r = eng.record_debrief(
            incident_id="INC-001",
            debrief_status=DebriefStatus.COMPLETED,
            debrief_quality=DebriefQuality.EXCELLENT,
            action_item_status=ActionItemStatus.COMPLETED,
            quality_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.debrief_status == DebriefStatus.COMPLETED
        assert r.debrief_quality == DebriefQuality.EXCELLENT
        assert r.action_item_status == ActionItemStatus.COMPLETED
        assert r.quality_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_debrief(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_debrief
# ---------------------------------------------------------------------------


class TestGetDebrief:
    def test_found(self):
        eng = _engine()
        r = eng.record_debrief(
            incident_id="INC-001",
            debrief_quality=DebriefQuality.POOR,
        )
        result = eng.get_debrief(r.id)
        assert result is not None
        assert result.debrief_quality == DebriefQuality.POOR

    def test_not_found(self):
        eng = _engine()
        assert eng.get_debrief("nonexistent") is None


# ---------------------------------------------------------------------------
# list_debriefs
# ---------------------------------------------------------------------------


class TestListDebriefs:
    def test_list_all(self):
        eng = _engine()
        eng.record_debrief(incident_id="INC-001")
        eng.record_debrief(incident_id="INC-002")
        assert len(eng.list_debriefs()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_status=DebriefStatus.COMPLETED,
        )
        eng.record_debrief(
            incident_id="INC-002",
            debrief_status=DebriefStatus.SKIPPED,
        )
        results = eng.list_debriefs(
            status=DebriefStatus.COMPLETED,
        )
        assert len(results) == 1

    def test_filter_by_quality(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_quality=DebriefQuality.EXCELLENT,
        )
        eng.record_debrief(
            incident_id="INC-002",
            debrief_quality=DebriefQuality.POOR,
        )
        results = eng.list_debriefs(
            quality=DebriefQuality.EXCELLENT,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_debrief(incident_id="INC-001", service="api-gateway")
        eng.record_debrief(incident_id="INC-002", service="auth-svc")
        results = eng.list_debriefs(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_debrief(incident_id="INC-001", team="sre")
        eng.record_debrief(incident_id="INC-002", team="platform")
        results = eng.list_debriefs(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_debrief(incident_id=f"INC-{i}")
        assert len(eng.list_debriefs(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            incident_id="INC-001",
            debrief_status=DebriefStatus.COMPLETED,
            metric_score=85.0,
            threshold=90.0,
            breached=True,
            description="Debrief quality below threshold",
        )
        assert m.incident_id == "INC-001"
        assert m.debrief_status == DebriefStatus.COMPLETED
        assert m.metric_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Debrief quality below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(incident_id=f"INC-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_debrief_quality
# ---------------------------------------------------------------------------


class TestAnalyzeDebriefQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_quality=DebriefQuality.EXCELLENT,
            quality_score=90.0,
        )
        eng.record_debrief(
            incident_id="INC-002",
            debrief_quality=DebriefQuality.EXCELLENT,
            quality_score=80.0,
        )
        result = eng.analyze_debrief_quality()
        assert "excellent" in result
        assert result["excellent"]["count"] == 2
        assert result["excellent"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_debrief_quality() == {}


# ---------------------------------------------------------------------------
# identify_low_quality_debriefs
# ---------------------------------------------------------------------------


class TestIdentifyLowQualityDebriefs:
    def test_detects_low_quality(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_quality=DebriefQuality.POOR,
        )
        eng.record_debrief(
            incident_id="INC-002",
            debrief_quality=DebriefQuality.EXCELLENT,
        )
        results = eng.identify_low_quality_debriefs()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_quality_debriefs() == []


# ---------------------------------------------------------------------------
# rank_by_quality_score
# ---------------------------------------------------------------------------


class TestRankByQualityScore:
    def test_ranked(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            service="api-gateway",
            quality_score=95.0,
        )
        eng.record_debrief(
            incident_id="INC-002",
            service="api-gateway",
            quality_score=85.0,
        )
        eng.record_debrief(
            incident_id="INC-003",
            service="auth-svc",
            quality_score=70.0,
        )
        results = eng.rank_by_quality_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_quality_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# ---------------------------------------------------------------------------
# detect_quality_trends
# ---------------------------------------------------------------------------


class TestDetectQualityTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_metric(incident_id="INC-1", metric_score=val)
        result = eng.detect_quality_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_metric(incident_id="INC-1", metric_score=val)
        result = eng.detect_quality_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_quality_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_status=DebriefStatus.COMPLETED,
            debrief_quality=DebriefQuality.POOR,
            action_item_status=ActionItemStatus.OPEN,
            quality_score=30.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentDebriefReport)
        assert report.total_records == 1
        assert report.low_quality_count == 1
        assert len(report.top_low_quality) >= 1
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
        eng.record_debrief(incident_id="INC-001")
        eng.add_metric(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_debrief(
            incident_id="INC-001",
            debrief_status=DebriefStatus.COMPLETED,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "completed" in stats["status_distribution"]
