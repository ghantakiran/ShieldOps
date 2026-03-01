"""Tests for shieldops.security.security_posture_gap — SecurityPostureGapAnalyzer."""

from __future__ import annotations

from shieldops.security.security_posture_gap import (
    GapAssessment,
    GapCategory,
    GapSeverity,
    PostureGapRecord,
    RemediationStatus,
    SecurityPostureGapAnalyzer,
    SecurityPostureGapReport,
)


def _engine(**kw) -> SecurityPostureGapAnalyzer:
    return SecurityPostureGapAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_authentication(self):
        assert GapCategory.AUTHENTICATION == "authentication"

    def test_category_authorization(self):
        assert GapCategory.AUTHORIZATION == "authorization"

    def test_category_encryption(self):
        assert GapCategory.ENCRYPTION == "encryption"

    def test_category_logging(self):
        assert GapCategory.LOGGING == "logging"

    def test_category_network(self):
        assert GapCategory.NETWORK == "network"

    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert GapSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_informational(self):
        assert GapSeverity.INFORMATIONAL == "informational"

    def test_status_open(self):
        assert RemediationStatus.OPEN == "open"

    def test_status_planned(self):
        assert RemediationStatus.PLANNED == "planned"

    def test_status_in_progress(self):
        assert RemediationStatus.IN_PROGRESS == "in_progress"

    def test_status_resolved(self):
        assert RemediationStatus.RESOLVED == "resolved"

    def test_status_accepted(self):
        assert RemediationStatus.ACCEPTED == "accepted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_posture_gap_record_defaults(self):
        r = PostureGapRecord()
        assert r.id
        assert r.gap_id == ""
        assert r.gap_category == GapCategory.AUTHENTICATION
        assert r.gap_severity == GapSeverity.INFORMATIONAL
        assert r.remediation_status == RemediationStatus.OPEN
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_gap_assessment_defaults(self):
        m = GapAssessment()
        assert m.id
        assert m.gap_id == ""
        assert m.gap_category == GapCategory.AUTHENTICATION
        assert m.assessment_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_security_posture_gap_report_defaults(self):
        r = SecurityPostureGapReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.critical_gaps == 0
        assert r.avg_risk_score == 0.0
        assert r.by_category == {}
        assert r.by_severity == {}
        assert r.by_remediation == {}
        assert r.top_critical == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_gap
# ---------------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap(
            gap_id="GAP-001",
            gap_category=GapCategory.ENCRYPTION,
            gap_severity=GapSeverity.CRITICAL,
            remediation_status=RemediationStatus.OPEN,
            risk_score=9.5,
            service="api-gateway",
            team="sre",
        )
        assert r.gap_id == "GAP-001"
        assert r.gap_category == GapCategory.ENCRYPTION
        assert r.gap_severity == GapSeverity.CRITICAL
        assert r.remediation_status == RemediationStatus.OPEN
        assert r.risk_score == 9.5
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(gap_id=f"GAP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_gap
# ---------------------------------------------------------------------------


class TestGetGap:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
        )
        result = eng.get_gap(r.id)
        assert result is not None
        assert result.gap_severity == GapSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


# ---------------------------------------------------------------------------
# list_gaps
# ---------------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001")
        eng.record_gap(gap_id="GAP-002")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_category=GapCategory.AUTHENTICATION,
        )
        eng.record_gap(
            gap_id="GAP-002",
            gap_category=GapCategory.ENCRYPTION,
        )
        results = eng.list_gaps(category=GapCategory.AUTHENTICATION)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
        )
        eng.record_gap(
            gap_id="GAP-002",
            gap_severity=GapSeverity.LOW,
        )
        results = eng.list_gaps(severity=GapSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", service="api-gateway")
        eng.record_gap(gap_id="GAP-002", service="auth-svc")
        results = eng.list_gaps(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", team="sre")
        eng.record_gap(gap_id="GAP-002", team="platform")
        results = eng.list_gaps(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(gap_id=f"GAP-{i}")
        assert len(eng.list_gaps(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        m = eng.add_assessment(
            gap_id="GAP-001",
            gap_category=GapCategory.ENCRYPTION,
            assessment_score=85.0,
            threshold=90.0,
            breached=True,
            description="Encryption coverage below threshold",
        )
        assert m.gap_id == "GAP-001"
        assert m.gap_category == GapCategory.ENCRYPTION
        assert m.assessment_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Encryption coverage below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(gap_id=f"GAP-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_gap_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeGapDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_category=GapCategory.AUTHENTICATION,
            risk_score=8.0,
        )
        eng.record_gap(
            gap_id="GAP-002",
            gap_category=GapCategory.AUTHENTICATION,
            risk_score=6.0,
        )
        result = eng.analyze_gap_distribution()
        assert "authentication" in result
        assert result["authentication"]["count"] == 2
        assert result["authentication"]["avg_risk_score"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_gap_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCriticalGaps:
    def test_detects(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
        )
        eng.record_gap(
            gap_id="GAP-002",
            gap_severity=GapSeverity.LOW,
        )
        results = eng.identify_critical_gaps()
        assert len(results) == 1
        assert results[0]["gap_id"] == "GAP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            service="api-gateway",
            risk_score=9.0,
        )
        eng.record_gap(
            gap_id="GAP-002",
            service="auth-svc",
            risk_score=3.0,
        )
        eng.record_gap(
            gap_id="GAP-003",
            service="api-gateway",
            risk_score=7.0,
        )
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        # descending: api-gateway (8.0) first, auth-svc (3.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_risk_score"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_gap_trends
# ---------------------------------------------------------------------------


class TestDetectGapTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_assessment(gap_id="GAP-1", assessment_score=val)
        result = eng.detect_gap_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_assessment(gap_id="GAP-1", assessment_score=val)
        result = eng.detect_gap_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_decreasing(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_assessment(gap_id="GAP-1", assessment_score=val)
        result = eng.detect_gap_trends()
        assert result["trend"] == "decreasing"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_gap_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_category=GapCategory.ENCRYPTION,
            gap_severity=GapSeverity.CRITICAL,
            remediation_status=RemediationStatus.OPEN,
            risk_score=9.5,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SecurityPostureGapReport)
        assert report.total_records == 1
        assert report.critical_gaps == 1
        assert len(report.top_critical) >= 1
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
        eng.record_gap(gap_id="GAP-001")
        eng.add_assessment(gap_id="GAP-001")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_category=GapCategory.AUTHENTICATION,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "authentication" in stats["category_distribution"]
