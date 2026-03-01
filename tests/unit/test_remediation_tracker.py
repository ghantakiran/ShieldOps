"""Tests for shieldops.audit.remediation_tracker — AuditRemediationTracker."""

from __future__ import annotations

from shieldops.audit.remediation_tracker import (
    AuditRemediationReport,
    AuditRemediationTracker,
    RemediationMilestone,
    RemediationPriority,
    RemediationRecord,
    RemediationStatus,
    RemediationType,
)


def _engine(**kw) -> AuditRemediationTracker:
    return AuditRemediationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_remediation_priority_critical(self):
        assert RemediationPriority.CRITICAL == "critical"

    def test_remediation_priority_high(self):
        assert RemediationPriority.HIGH == "high"

    def test_remediation_priority_medium(self):
        assert RemediationPriority.MEDIUM == "medium"

    def test_remediation_priority_low(self):
        assert RemediationPriority.LOW == "low"

    def test_remediation_priority_informational(self):
        assert RemediationPriority.INFORMATIONAL == "informational"

    def test_remediation_status_not_started(self):
        assert RemediationStatus.NOT_STARTED == "not_started"

    def test_remediation_status_in_progress(self):
        assert RemediationStatus.IN_PROGRESS == "in_progress"

    def test_remediation_status_completed(self):
        assert RemediationStatus.COMPLETED == "completed"

    def test_remediation_status_overdue(self):
        assert RemediationStatus.OVERDUE == "overdue"

    def test_remediation_status_waived(self):
        assert RemediationStatus.WAIVED == "waived"

    def test_remediation_type_policy_update(self):
        assert RemediationType.POLICY_UPDATE == "policy_update"

    def test_remediation_type_technical_fix(self):
        assert RemediationType.TECHNICAL_FIX == "technical_fix"

    def test_remediation_type_process_change(self):
        assert RemediationType.PROCESS_CHANGE == "process_change"

    def test_remediation_type_training(self):
        assert RemediationType.TRAINING == "training"

    def test_remediation_type_documentation(self):
        assert RemediationType.DOCUMENTATION == "documentation"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_remediation_record_defaults(self):
        r = RemediationRecord()
        assert r.id
        assert r.finding_id == ""
        assert r.remediation_priority == RemediationPriority.MEDIUM
        assert r.remediation_status == RemediationStatus.NOT_STARTED
        assert r.remediation_type == RemediationType.TECHNICAL_FIX
        assert r.completion_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_remediation_milestone_defaults(self):
        m = RemediationMilestone()
        assert m.id
        assert m.milestone_name == ""
        assert m.remediation_priority == RemediationPriority.MEDIUM
        assert m.progress_score == 0.0
        assert m.items_tracked == 0
        assert m.description == ""
        assert m.created_at > 0

    def test_audit_remediation_report_defaults(self):
        r = AuditRemediationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_milestones == 0
        assert r.completed_remediations == 0
        assert r.avg_completion_pct == 0.0
        assert r.by_priority == {}
        assert r.by_status == {}
        assert r.by_type == {}
        assert r.overdue_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_remediation
# ---------------------------------------------------------------------------


class TestRecordRemediation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.CRITICAL,
            remediation_status=RemediationStatus.IN_PROGRESS,
            remediation_type=RemediationType.POLICY_UPDATE,
            completion_pct=45.0,
            team="compliance",
        )
        assert r.finding_id == "FIND-001"
        assert r.remediation_priority == RemediationPriority.CRITICAL
        assert r.remediation_status == RemediationStatus.IN_PROGRESS
        assert r.remediation_type == RemediationType.POLICY_UPDATE
        assert r.completion_pct == 45.0
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_remediation(finding_id=f"FIND-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_remediation
# ---------------------------------------------------------------------------


class TestGetRemediation:
    def test_found(self):
        eng = _engine()
        r = eng.record_remediation(
            finding_id="FIND-001",
            remediation_type=RemediationType.PROCESS_CHANGE,
        )
        result = eng.get_remediation(r.id)
        assert result is not None
        assert result.remediation_type == RemediationType.PROCESS_CHANGE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_remediation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_remediations
# ---------------------------------------------------------------------------


class TestListRemediations:
    def test_list_all(self):
        eng = _engine()
        eng.record_remediation(finding_id="FIND-001")
        eng.record_remediation(finding_id="FIND-002")
        assert len(eng.list_remediations()) == 2

    def test_filter_by_remediation_priority(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.CRITICAL,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_priority=RemediationPriority.LOW,
        )
        results = eng.list_remediations(remediation_priority=RemediationPriority.CRITICAL)
        assert len(results) == 1

    def test_filter_by_remediation_status(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_status=RemediationStatus.COMPLETED,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_status=RemediationStatus.OVERDUE,
        )
        results = eng.list_remediations(remediation_status=RemediationStatus.COMPLETED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_remediation(finding_id="FIND-001", team="compliance")
        eng.record_remediation(finding_id="FIND-002", team="security")
        results = eng.list_remediations(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_remediation(finding_id=f"FIND-{i}")
        assert len(eng.list_remediations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_milestone
# ---------------------------------------------------------------------------


class TestAddMilestone:
    def test_basic(self):
        eng = _engine()
        m = eng.add_milestone(
            milestone_name="phase-1-complete",
            remediation_priority=RemediationPriority.HIGH,
            progress_score=8.5,
            items_tracked=3,
            description="Phase 1 remediation milestone",
        )
        assert m.milestone_name == "phase-1-complete"
        assert m.remediation_priority == RemediationPriority.HIGH
        assert m.progress_score == 8.5
        assert m.items_tracked == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_milestone(milestone_name=f"ms-{i}")
        assert len(eng._milestones) == 2


# ---------------------------------------------------------------------------
# analyze_remediation_progress
# ---------------------------------------------------------------------------


class TestAnalyzeRemediationProgress:
    def test_with_data(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.CRITICAL,
            completion_pct=90.0,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_priority=RemediationPriority.CRITICAL,
            completion_pct=80.0,
        )
        result = eng.analyze_remediation_progress()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_completion_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_remediation_progress() == {}


# ---------------------------------------------------------------------------
# identify_overdue_remediations
# ---------------------------------------------------------------------------


class TestIdentifyOverdueRemediations:
    def test_detects_overdue(self):
        eng = _engine(max_overdue_pct=10.0)
        eng.record_remediation(
            finding_id="FIND-001",
            completion_pct=50.0,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            completion_pct=95.0,
        )
        results = eng.identify_overdue_remediations()
        assert len(results) == 1
        assert results[0]["finding_id"] == "FIND-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_remediations() == []


# ---------------------------------------------------------------------------
# rank_by_priority
# ---------------------------------------------------------------------------


class TestRankByPriority:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_remediation(finding_id="FIND-001", team="compliance", completion_pct=90.0)
        eng.record_remediation(finding_id="FIND-002", team="compliance", completion_pct=80.0)
        eng.record_remediation(finding_id="FIND-003", team="security", completion_pct=50.0)
        results = eng.rank_by_priority()
        assert len(results) == 2
        assert results[0]["team"] == "compliance"
        assert results[0]["total_completion"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_priority() == []


# ---------------------------------------------------------------------------
# detect_remediation_bottlenecks
# ---------------------------------------------------------------------------


class TestDetectRemediationBottlenecks:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_remediation(finding_id="FIND", completion_pct=pct)
        result = eng.detect_remediation_bottlenecks()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_remediation(finding_id="FIND", completion_pct=pct)
        result = eng.detect_remediation_bottlenecks()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_remediation_bottlenecks()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_overdue_pct=10.0)
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.CRITICAL,
            remediation_status=RemediationStatus.IN_PROGRESS,
            completion_pct=50.0,
            team="compliance",
        )
        report = eng.generate_report()
        assert isinstance(report, AuditRemediationReport)
        assert report.total_records == 1
        assert report.avg_completion_pct == 50.0
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
        eng.record_remediation(finding_id="FIND-001")
        eng.add_milestone(milestone_name="ms1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._milestones) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_milestones"] == 0
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.HIGH,
            team="compliance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_findings"] == 1
        assert "high" in stats["priority_distribution"]
