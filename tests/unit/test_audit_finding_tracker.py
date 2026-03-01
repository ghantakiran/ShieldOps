"""Tests for shieldops.audit.audit_finding_tracker — AuditFindingTracker."""

from __future__ import annotations

from shieldops.audit.audit_finding_tracker import (
    AuditFindingReport,
    AuditFindingTracker,
    FindingCategory,
    FindingRecord,
    FindingRemediation,
    FindingSeverity,
    FindingStatus,
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

    def test_finding_severity_moderate(self):
        assert FindingSeverity.MODERATE == "moderate"

    def test_finding_severity_low(self):
        assert FindingSeverity.LOW == "low"

    def test_finding_severity_informational(self):
        assert FindingSeverity.INFORMATIONAL == "informational"

    def test_finding_category_access_control(self):
        assert FindingCategory.ACCESS_CONTROL == "access_control"

    def test_finding_category_data_protection(self):
        assert FindingCategory.DATA_PROTECTION == "data_protection"

    def test_finding_category_configuration(self):
        assert FindingCategory.CONFIGURATION == "configuration"

    def test_finding_category_monitoring(self):
        assert FindingCategory.MONITORING == "monitoring"

    def test_finding_category_compliance(self):
        assert FindingCategory.COMPLIANCE == "compliance"

    def test_finding_status_open(self):
        assert FindingStatus.OPEN == "open"

    def test_finding_status_investigating(self):
        assert FindingStatus.INVESTIGATING == "investigating"

    def test_finding_status_remediated(self):
        assert FindingStatus.REMEDIATED == "remediated"

    def test_finding_status_accepted(self):
        assert FindingStatus.ACCEPTED == "accepted"

    def test_finding_status_closed(self):
        assert FindingStatus.CLOSED == "closed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_finding_record_defaults(self):
        r = FindingRecord()
        assert r.id
        assert r.finding_id == ""
        assert r.finding_severity == FindingSeverity.INFORMATIONAL
        assert r.finding_category == FindingCategory.COMPLIANCE
        assert r.finding_status == FindingStatus.OPEN
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_finding_remediation_defaults(self):
        r = FindingRemediation()
        assert r.id
        assert r.finding_id == ""
        assert r.finding_severity == FindingSeverity.INFORMATIONAL
        assert r.remediation_score == 0.0
        assert r.threshold == 0.0
        assert r.breached is False
        assert r.description == ""
        assert r.created_at > 0

    def test_audit_finding_report_defaults(self):
        r = AuditFindingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_remediations == 0
        assert r.open_findings == 0
        assert r.avg_risk_score == 0.0
        assert r.by_severity == {}
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.top_open == []
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
            finding_id="FIND-001",
            finding_severity=FindingSeverity.HIGH,
            finding_category=FindingCategory.ACCESS_CONTROL,
            finding_status=FindingStatus.OPEN,
            risk_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.finding_id == "FIND-001"
        assert r.finding_severity == FindingSeverity.HIGH
        assert r.finding_category == FindingCategory.ACCESS_CONTROL
        assert r.finding_status == FindingStatus.OPEN
        assert r.risk_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_finding(finding_id=f"FIND-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_finding
# ---------------------------------------------------------------------------


class TestGetFinding:
    def test_found(self):
        eng = _engine()
        r = eng.record_finding(
            finding_id="FIND-001",
            finding_severity=FindingSeverity.MODERATE,
        )
        result = eng.get_finding(r.id)
        assert result is not None
        assert result.finding_severity == FindingSeverity.MODERATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent") is None


# ---------------------------------------------------------------------------
# list_findings
# ---------------------------------------------------------------------------


class TestListFindings:
    def test_list_all(self):
        eng = _engine()
        eng.record_finding(finding_id="FIND-001")
        eng.record_finding(finding_id="FIND-002")
        assert len(eng.list_findings()) == 2

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_finding(finding_id="FIND-001", finding_severity=FindingSeverity.CRITICAL)
        eng.record_finding(finding_id="FIND-002", finding_severity=FindingSeverity.LOW)
        results = eng.list_findings(severity=FindingSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            finding_category=FindingCategory.ACCESS_CONTROL,
        )
        eng.record_finding(
            finding_id="FIND-002",
            finding_category=FindingCategory.DATA_PROTECTION,
        )
        results = eng.list_findings(category=FindingCategory.ACCESS_CONTROL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_finding(finding_id="FIND-001", service="api-gateway")
        eng.record_finding(finding_id="FIND-002", service="auth-svc")
        results = eng.list_findings(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_finding(finding_id="FIND-001", team="sre")
        eng.record_finding(finding_id="FIND-002", team="platform")
        results = eng.list_findings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_finding(finding_id=f"FIND-{i}")
        assert len(eng.list_findings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_remediation
# ---------------------------------------------------------------------------


class TestAddRemediation:
    def test_basic(self):
        eng = _engine()
        r = eng.add_remediation(
            finding_id="FIND-001",
            finding_severity=FindingSeverity.HIGH,
            remediation_score=85.0,
            threshold=90.0,
            breached=True,
            description="Access control gap found",
        )
        assert r.finding_id == "FIND-001"
        assert r.finding_severity == FindingSeverity.HIGH
        assert r.remediation_score == 85.0
        assert r.threshold == 90.0
        assert r.breached is True
        assert r.description == "Access control gap found"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_remediation(finding_id=f"FIND-{i}")
        assert len(eng._remediations) == 2


# ---------------------------------------------------------------------------
# analyze_finding_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeFindingDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            finding_severity=FindingSeverity.HIGH,
            risk_score=10.0,
        )
        eng.record_finding(
            finding_id="FIND-002",
            finding_severity=FindingSeverity.HIGH,
            risk_score=20.0,
        )
        result = eng.analyze_finding_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_risk_score"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_finding_distribution() == {}


# ---------------------------------------------------------------------------
# identify_open_findings
# ---------------------------------------------------------------------------


class TestIdentifyOpenFindings:
    def test_detects(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            finding_status=FindingStatus.OPEN,
        )
        eng.record_finding(
            finding_id="FIND-002",
            finding_status=FindingStatus.CLOSED,
        )
        results = eng.identify_open_findings()
        assert len(results) == 1
        assert results[0]["finding_id"] == "FIND-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_open_findings() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            service="api-gateway",
            risk_score=120.0,
        )
        eng.record_finding(
            finding_id="FIND-002",
            service="auth-svc",
            risk_score=30.0,
        )
        eng.record_finding(
            finding_id="FIND-003",
            service="api-gateway",
            risk_score=80.0,
        )
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        # descending: api-gateway (100.0) first, auth-svc (30.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_risk_score"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_finding_trends
# ---------------------------------------------------------------------------


class TestDetectFindingTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_remediation(finding_id="FIND-1", remediation_score=val)
        result = eng.detect_finding_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_remediation(finding_id="FIND-1", remediation_score=val)
        result = eng.detect_finding_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_shrinking(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_remediation(finding_id="FIND-1", remediation_score=val)
        result = eng.detect_finding_trends()
        assert result["trend"] == "shrinking"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_finding_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            finding_severity=FindingSeverity.CRITICAL,
            finding_category=FindingCategory.ACCESS_CONTROL,
            finding_status=FindingStatus.OPEN,
            risk_score=95.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, AuditFindingReport)
        assert report.total_records == 1
        assert report.open_findings == 1
        assert len(report.top_open) >= 1
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
        eng.record_finding(finding_id="FIND-001")
        eng.add_remediation(finding_id="FIND-001")
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
        assert stats["finding_severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            finding_id="FIND-001",
            finding_severity=FindingSeverity.HIGH,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "high" in stats["finding_severity_distribution"]
