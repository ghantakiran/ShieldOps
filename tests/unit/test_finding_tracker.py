"""Tests for shieldops.audit.finding_tracker — AuditFindingTracker."""

from __future__ import annotations

from shieldops.audit.finding_tracker import (
    AuditFindingReport,
    AuditFindingTracker,
    FindingCategory,
    FindingRecord,
    FindingSeverity,
    FindingStatus,
    RemediationPlan,
)


def _engine(**kw) -> AuditFindingTracker:
    return AuditFindingTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_finding_severity_critical(self):
        assert FindingSeverity.CRITICAL == "critical"

    def test_finding_severity_high(self):
        assert FindingSeverity.HIGH == "high"

    def test_finding_severity_medium(self):
        assert FindingSeverity.MEDIUM == "medium"

    def test_finding_severity_low(self):
        assert FindingSeverity.LOW == "low"

    def test_finding_severity_informational(self):
        assert FindingSeverity.INFORMATIONAL == "informational"

    def test_finding_status_open(self):
        assert FindingStatus.OPEN == "open"

    def test_finding_status_in_progress(self):
        assert FindingStatus.IN_PROGRESS == "in_progress"

    def test_finding_status_remediated(self):
        assert FindingStatus.REMEDIATED == "remediated"

    def test_finding_status_accepted_risk(self):
        assert FindingStatus.ACCEPTED_RISK == "accepted_risk"

    def test_finding_status_closed(self):
        assert FindingStatus.CLOSED == "closed"

    def test_finding_category_access_control(self):
        assert FindingCategory.ACCESS_CONTROL == "access_control"

    def test_finding_category_data_protection(self):
        assert FindingCategory.DATA_PROTECTION == "data_protection"

    def test_finding_category_change_management(self):
        assert FindingCategory.CHANGE_MANAGEMENT == "change_management"

    def test_finding_category_incident_response(self):
        assert FindingCategory.INCIDENT_RESPONSE == "incident_response"

    def test_finding_category_monitoring(self):
        assert FindingCategory.MONITORING == "monitoring"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_finding_record_defaults(self):
        r = FindingRecord()
        assert r.id
        assert r.finding_id == ""
        assert r.finding_severity == FindingSeverity.INFORMATIONAL
        assert r.finding_status == FindingStatus.OPEN
        assert r.finding_category == FindingCategory.ACCESS_CONTROL
        assert r.open_finding_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_remediation_plan_defaults(self):
        p = RemediationPlan()
        assert p.id
        assert p.plan_pattern == ""
        assert p.finding_severity == FindingSeverity.INFORMATIONAL
        assert p.days_to_remediate == 0
        assert p.resources_required == 0
        assert p.description == ""
        assert p.created_at > 0

    def test_audit_finding_report_defaults(self):
        r = AuditFindingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_remediations == 0
        assert r.overdue_findings == 0
        assert r.avg_open_finding_pct == 0.0
        assert r.by_severity == {}
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.critical == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_finding
# ---------------------------------------------------------------------------


class TestRecordFinding:
    def test_basic(self):
        eng = _engine()
        r = eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.HIGH,
            finding_status=FindingStatus.IN_PROGRESS,
            finding_category=FindingCategory.DATA_PROTECTION,
            open_finding_pct=20.0,
            team="security",
        )
        assert r.finding_id == "FND-001"
        assert r.finding_severity == FindingSeverity.HIGH
        assert r.finding_status == FindingStatus.IN_PROGRESS
        assert r.finding_category == FindingCategory.DATA_PROTECTION
        assert r.open_finding_pct == 20.0
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_finding(finding_id=f"FND-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_finding
# ---------------------------------------------------------------------------


class TestGetFinding:
    def test_found(self):
        eng = _engine()
        r = eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.CRITICAL,
        )
        result = eng.get_finding(r.id)
        assert result is not None
        assert result.finding_severity == FindingSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent") is None


# ---------------------------------------------------------------------------
# list_findings
# ---------------------------------------------------------------------------


class TestListFindings:
    def test_list_all(self):
        eng = _engine()
        eng.record_finding(finding_id="FND-001")
        eng.record_finding(finding_id="FND-002")
        assert len(eng.list_findings()) == 2

    def test_filter_by_finding_severity(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.CRITICAL,
        )
        eng.record_finding(
            finding_id="FND-002",
            finding_severity=FindingSeverity.LOW,
        )
        results = eng.list_findings(finding_severity=FindingSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_finding_status(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FND-001",
            finding_status=FindingStatus.OPEN,
        )
        eng.record_finding(
            finding_id="FND-002",
            finding_status=FindingStatus.CLOSED,
        )
        results = eng.list_findings(finding_status=FindingStatus.OPEN)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_finding(finding_id="FND-001", team="security")
        eng.record_finding(finding_id="FND-002", team="compliance")
        results = eng.list_findings(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_finding(finding_id=f"FND-{i}")
        assert len(eng.list_findings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_remediation
# ---------------------------------------------------------------------------


class TestAddRemediation:
    def test_basic(self):
        eng = _engine()
        p = eng.add_remediation(
            plan_pattern="access-review-*",
            finding_severity=FindingSeverity.HIGH,
            days_to_remediate=30,
            resources_required=2,
            description="Access control remediation plan",
        )
        assert p.plan_pattern == "access-review-*"
        assert p.finding_severity == FindingSeverity.HIGH
        assert p.days_to_remediate == 30
        assert p.resources_required == 2

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_remediation(plan_pattern=f"plan-{i}")
        assert len(eng._remediations) == 2


# ---------------------------------------------------------------------------
# analyze_finding_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeFindingPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.HIGH,
            open_finding_pct=20.0,
        )
        eng.record_finding(
            finding_id="FND-002",
            finding_severity=FindingSeverity.HIGH,
            open_finding_pct=10.0,
        )
        result = eng.analyze_finding_patterns()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_open_finding_pct"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_finding_patterns() == {}


# ---------------------------------------------------------------------------
# identify_overdue_findings
# ---------------------------------------------------------------------------


class TestIdentifyOverdueFindings:
    def test_detects_overdue(self):
        eng = _engine(max_open_finding_pct=15.0)
        eng.record_finding(
            finding_id="FND-001",
            open_finding_pct=20.0,
        )
        eng.record_finding(
            finding_id="FND-002",
            open_finding_pct=5.0,
        )
        results = eng.identify_overdue_findings()
        assert len(results) == 1
        assert results[0]["finding_id"] == "FND-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_findings() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBySeverity:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_finding(finding_id="FND-001", team="security", open_finding_pct=20.0)
        eng.record_finding(finding_id="FND-002", team="security", open_finding_pct=15.0)
        eng.record_finding(finding_id="FND-003", team="compliance", open_finding_pct=5.0)
        results = eng.rank_by_severity()
        assert len(results) == 2
        assert results[0]["team"] == "security"
        assert results[0]["total_open_pct"] == 35.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_finding_trends
# ---------------------------------------------------------------------------


class TestDetectFindingTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [10.0, 10.0, 10.0, 10.0]:
            eng.record_finding(finding_id="FND", open_finding_pct=pct)
        result = eng.detect_finding_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [5.0, 5.0, 20.0, 20.0]:
            eng.record_finding(finding_id="FND", open_finding_pct=pct)
        result = eng.detect_finding_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_finding_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_open_finding_pct=15.0)
        eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.CRITICAL,
            finding_status=FindingStatus.OPEN,
            open_finding_pct=20.0,
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, AuditFindingReport)
        assert report.total_records == 1
        assert report.avg_open_finding_pct == 20.0
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
        eng.record_finding(finding_id="FND-001")
        eng.add_remediation(plan_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._remediations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_remediations"] == 0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FND-001",
            finding_severity=FindingSeverity.HIGH,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_findings"] == 1
        assert "high" in stats["severity_distribution"]
