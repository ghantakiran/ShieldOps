"""Tests for shieldops.audit.audit_remediation_tracker — AuditRemediationTracker."""

from __future__ import annotations

from shieldops.audit.audit_remediation_tracker import (
    AuditRemediationReport,
    AuditRemediationTracker,
    FindingSource,
    RemediationAssessment,
    RemediationPriority,
    RemediationRecord,
    RemediationState,
)


def _engine(**kw) -> AuditRemediationTracker:
    return AuditRemediationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_priority_critical(self):
        assert RemediationPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert RemediationPriority.HIGH == "high"

    def test_priority_medium(self):
        assert RemediationPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert RemediationPriority.LOW == "low"

    def test_priority_informational(self):
        assert RemediationPriority.INFORMATIONAL == "informational"

    def test_state_open(self):
        assert RemediationState.OPEN == "open"

    def test_state_assigned(self):
        assert RemediationState.ASSIGNED == "assigned"

    def test_state_in_progress(self):
        assert RemediationState.IN_PROGRESS == "in_progress"

    def test_state_completed(self):
        assert RemediationState.COMPLETED == "completed"

    def test_state_overdue(self):
        assert RemediationState.OVERDUE == "overdue"

    def test_source_internal_audit(self):
        assert FindingSource.INTERNAL_AUDIT == "internal_audit"

    def test_source_external_audit(self):
        assert FindingSource.EXTERNAL_AUDIT == "external_audit"

    def test_source_penetration_test(self):
        assert FindingSource.PENETRATION_TEST == "penetration_test"

    def test_source_compliance_scan(self):
        assert FindingSource.COMPLIANCE_SCAN == "compliance_scan"

    def test_source_self_assessment(self):
        assert FindingSource.SELF_ASSESSMENT == "self_assessment"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_remediation_record_defaults(self):
        r = RemediationRecord()
        assert r.id
        assert r.finding_id == ""
        assert r.remediation_priority == RemediationPriority.MEDIUM
        assert r.remediation_state == RemediationState.OPEN
        assert r.finding_source == FindingSource.INTERNAL_AUDIT
        assert r.remediation_days == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_remediation_assessment_defaults(self):
        a = RemediationAssessment()
        assert a.id
        assert a.finding_id == ""
        assert a.remediation_priority == RemediationPriority.MEDIUM
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_remediation_report_defaults(self):
        r = AuditRemediationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.overdue_count == 0
        assert r.avg_remediation_days == 0.0
        assert r.by_priority == {}
        assert r.by_state == {}
        assert r.by_source == {}
        assert r.top_overdue == []
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
            remediation_priority=RemediationPriority.HIGH,
            remediation_state=RemediationState.IN_PROGRESS,
            finding_source=FindingSource.EXTERNAL_AUDIT,
            remediation_days=30.0,
            service="api-gateway",
            team="sre",
        )
        assert r.finding_id == "FIND-001"
        assert r.remediation_priority == RemediationPriority.HIGH
        assert r.remediation_state == RemediationState.IN_PROGRESS
        assert r.finding_source == FindingSource.EXTERNAL_AUDIT
        assert r.remediation_days == 30.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

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
            remediation_priority=RemediationPriority.CRITICAL,
        )
        result = eng.get_remediation(r.id)
        assert result is not None
        assert result.remediation_priority == RemediationPriority.CRITICAL

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

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.CRITICAL,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_priority=RemediationPriority.LOW,
        )
        results = eng.list_remediations(priority=RemediationPriority.CRITICAL)
        assert len(results) == 1

    def test_filter_by_state(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_state=RemediationState.OPEN,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_state=RemediationState.COMPLETED,
        )
        results = eng.list_remediations(state=RemediationState.OPEN)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_remediation(finding_id="FIND-001", team="sre")
        eng.record_remediation(finding_id="FIND-002", team="platform")
        results = eng.list_remediations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_remediation(finding_id=f"FIND-{i}")
        assert len(eng.list_remediations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.HIGH,
            assessment_score=75.0,
            threshold=80.0,
            breached=True,
            description="Below target",
        )
        assert a.finding_id == "FIND-001"
        assert a.remediation_priority == RemediationPriority.HIGH
        assert a.assessment_score == 75.0
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(finding_id=f"FIND-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_remediation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRemediationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.HIGH,
            remediation_days=20.0,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_priority=RemediationPriority.HIGH,
            remediation_days=40.0,
        )
        result = eng.analyze_remediation_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_remediation_days"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_remediation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_overdue_remediations
# ---------------------------------------------------------------------------


class TestIdentifyOverdueRemediations:
    def test_detects_overdue(self):
        eng = _engine(max_remediation_days=45.0)
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_days=60.0,
        )
        eng.record_remediation(
            finding_id="FIND-002",
            remediation_days=30.0,
        )
        results = eng.identify_overdue_remediations()
        assert len(results) == 1
        assert results[0]["finding_id"] == "FIND-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_remediations() == []


# ---------------------------------------------------------------------------
# rank_by_remediation_time
# ---------------------------------------------------------------------------


class TestRankByRemediationTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_remediation(finding_id="FIND-001", remediation_days=10.0, service="svc-a")
        eng.record_remediation(finding_id="FIND-002", remediation_days=50.0, service="svc-b")
        results = eng.rank_by_remediation_time()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_remediation_days"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_remediation_time() == []


# ---------------------------------------------------------------------------
# detect_remediation_trends
# ---------------------------------------------------------------------------


class TestDetectRemediationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(finding_id="FIND-001", assessment_score=70.0)
        result = eng.detect_remediation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(finding_id="FIND-001", assessment_score=50.0)
        eng.add_assessment(finding_id="FIND-002", assessment_score=50.0)
        eng.add_assessment(finding_id="FIND-003", assessment_score=80.0)
        eng.add_assessment(finding_id="FIND-004", assessment_score=80.0)
        result = eng.detect_remediation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_remediation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_remediation_days=45.0)
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.HIGH,
            remediation_state=RemediationState.OVERDUE,
            remediation_days=60.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditRemediationReport)
        assert report.total_records == 1
        assert report.overdue_count == 1
        assert len(report.top_overdue) == 1
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
        eng.add_assessment(finding_id="FIND-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_remediation(
            finding_id="FIND-001",
            remediation_priority=RemediationPriority.HIGH,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "high" in stats["priority_distribution"]
