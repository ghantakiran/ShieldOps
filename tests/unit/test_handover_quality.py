"""Tests for shieldops.operations.handover_quality — HandoverQualityTracker."""

from __future__ import annotations

from shieldops.operations.handover_quality import (
    HandoverChecklist,
    HandoverIssue,
    HandoverQuality,
    HandoverQualityReport,
    HandoverQualityTracker,
    HandoverRecord,
    HandoverType,
)


def _engine(**kw) -> HandoverQualityTracker:
    return HandoverQualityTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_shift_change(self):
        assert HandoverType.SHIFT_CHANGE == "shift_change"

    def test_type_escalation(self):
        assert HandoverType.ESCALATION == "escalation"

    def test_type_cross_team(self):
        assert HandoverType.CROSS_TEAM == "cross_team"

    def test_type_incident_transfer(self):
        assert HandoverType.INCIDENT_TRANSFER == "incident_transfer"

    def test_type_maintenance_window(self):
        assert HandoverType.MAINTENANCE_WINDOW == "maintenance_window"

    def test_quality_excellent(self):
        assert HandoverQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert HandoverQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert HandoverQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert HandoverQuality.POOR == "poor"

    def test_quality_failed(self):
        assert HandoverQuality.FAILED == "failed"

    def test_issue_missing_context(self):
        assert HandoverIssue.MISSING_CONTEXT == "missing_context"

    def test_issue_delayed_transfer(self):
        assert HandoverIssue.DELAYED_TRANSFER == "delayed_transfer"

    def test_issue_wrong_recipient(self):
        assert HandoverIssue.WRONG_RECIPIENT == "wrong_recipient"

    def test_issue_incomplete_status(self):
        assert HandoverIssue.INCOMPLETE_STATUS == "incomplete_status"

    def test_issue_no_runbook(self):
        assert HandoverIssue.NO_RUNBOOK == "no_runbook"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_handover_record_defaults(self):
        r = HandoverRecord()
        assert r.id
        assert r.handover_id == ""
        assert r.handover_type == HandoverType.SHIFT_CHANGE
        assert r.handover_quality == HandoverQuality.ADEQUATE
        assert r.handover_issue == HandoverIssue.MISSING_CONTEXT
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_handover_checklist_defaults(self):
        c = HandoverChecklist()
        assert c.id
        assert c.handover_id == ""
        assert c.handover_type == HandoverType.SHIFT_CHANGE
        assert c.value == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_handover_quality_report_defaults(self):
        r = HandoverQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checklists == 0
        assert r.poor_handovers == 0
        assert r.avg_quality_score == 0.0
        assert r.by_type == {}
        assert r.by_quality == {}
        assert r.by_issue == {}
        assert r.top_poor == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_handover
# ---------------------------------------------------------------------------


class TestRecordHandover:
    def test_basic(self):
        eng = _engine()
        r = eng.record_handover(
            handover_id="HO-001",
            handover_type=HandoverType.ESCALATION,
            handover_quality=HandoverQuality.POOR,
            handover_issue=HandoverIssue.DELAYED_TRANSFER,
            quality_score=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.handover_id == "HO-001"
        assert r.handover_type == HandoverType.ESCALATION
        assert r.handover_quality == HandoverQuality.POOR
        assert r.handover_issue == HandoverIssue.DELAYED_TRANSFER
        assert r.quality_score == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_handover(handover_id=f"HO-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_handover
# ---------------------------------------------------------------------------


class TestGetHandover:
    def test_found(self):
        eng = _engine()
        r = eng.record_handover(
            handover_id="HO-001",
            handover_quality=HandoverQuality.FAILED,
        )
        result = eng.get_handover(r.id)
        assert result is not None
        assert result.handover_quality == HandoverQuality.FAILED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_handover("nonexistent") is None


# ---------------------------------------------------------------------------
# list_handovers
# ---------------------------------------------------------------------------


class TestListHandovers:
    def test_list_all(self):
        eng = _engine()
        eng.record_handover(handover_id="HO-001")
        eng.record_handover(handover_id="HO-002")
        assert len(eng.list_handovers()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_type=HandoverType.CROSS_TEAM,
        )
        eng.record_handover(
            handover_id="HO-002",
            handover_type=HandoverType.SHIFT_CHANGE,
        )
        results = eng.list_handovers(htype=HandoverType.CROSS_TEAM)
        assert len(results) == 1

    def test_filter_by_quality(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_quality=HandoverQuality.POOR,
        )
        eng.record_handover(
            handover_id="HO-002",
            handover_quality=HandoverQuality.EXCELLENT,
        )
        results = eng.list_handovers(quality=HandoverQuality.POOR)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_handover(handover_id="HO-001", service="api")
        eng.record_handover(handover_id="HO-002", service="web")
        results = eng.list_handovers(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_handover(handover_id="HO-001", team="sre")
        eng.record_handover(handover_id="HO-002", team="platform")
        results = eng.list_handovers(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_handover(handover_id=f"HO-{i}")
        assert len(eng.list_handovers(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_checklist
# ---------------------------------------------------------------------------


class TestAddChecklist:
    def test_basic(self):
        eng = _engine()
        c = eng.add_checklist(
            handover_id="HO-001",
            handover_type=HandoverType.INCIDENT_TRANSFER,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Context provided",
        )
        assert c.handover_id == "HO-001"
        assert c.handover_type == HandoverType.INCIDENT_TRANSFER
        assert c.value == 75.0
        assert c.threshold == 80.0
        assert c.breached is False
        assert c.description == "Context provided"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_checklist(handover_id=f"HO-{i}")
        assert len(eng._checklists) == 2


# ---------------------------------------------------------------------------
# analyze_handover_quality
# ---------------------------------------------------------------------------


class TestAnalyzeHandoverQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_type=HandoverType.SHIFT_CHANGE,
            quality_score=70.0,
        )
        eng.record_handover(
            handover_id="HO-002",
            handover_type=HandoverType.SHIFT_CHANGE,
            quality_score=90.0,
        )
        result = eng.analyze_handover_quality()
        assert "shift_change" in result
        assert result["shift_change"]["count"] == 2
        assert result["shift_change"]["avg_quality_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_handover_quality() == {}


# ---------------------------------------------------------------------------
# identify_poor_handovers
# ---------------------------------------------------------------------------


class TestIdentifyPoorHandovers:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_quality=HandoverQuality.POOR,
        )
        eng.record_handover(
            handover_id="HO-002",
            handover_quality=HandoverQuality.EXCELLENT,
        )
        results = eng.identify_poor_handovers()
        assert len(results) == 1
        assert results[0]["handover_id"] == "HO-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_handovers() == []


# ---------------------------------------------------------------------------
# rank_by_quality_score
# ---------------------------------------------------------------------------


class TestRankByQualityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_handover(handover_id="HO-001", service="api", quality_score=90.0)
        eng.record_handover(handover_id="HO-002", service="api", quality_score=80.0)
        eng.record_handover(handover_id="HO-003", service="web", quality_score=50.0)
        results = eng.rank_by_quality_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# ---------------------------------------------------------------------------
# detect_handover_issues
# ---------------------------------------------------------------------------


class TestDetectHandoverIssues:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_checklist(handover_id="HO-001", value=val)
        result = eng.detect_handover_issues()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_checklist(handover_id="HO-001", value=val)
        result = eng.detect_handover_issues()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_handover_issues()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_type=HandoverType.SHIFT_CHANGE,
            handover_quality=HandoverQuality.POOR,
            quality_score=40.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, HandoverQualityReport)
        assert report.total_records == 1
        assert report.poor_handovers == 1
        assert report.avg_quality_score == 40.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_handover(handover_id="HO-001")
        eng.add_checklist(handover_id="HO-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checklists) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checklists"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_handover(
            handover_id="HO-001",
            handover_type=HandoverType.CROSS_TEAM,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_handovers"] == 1
        assert "cross_team" in stats["type_distribution"]
