"""Tests for shieldops.compliance.risk_scorer — ComplianceRiskScorer."""

from __future__ import annotations

from shieldops.compliance.risk_scorer import (
    AssessmentStatus,
    ComplianceRiskReport,
    ComplianceRiskScorer,
    RiskDomain,
    RiskLevel,
    RiskRecord,
    RiskRule,
)


def _engine(**kw) -> ComplianceRiskScorer:
    return ComplianceRiskScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_risk_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_level_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_level_negligible(self):
        assert RiskLevel.NEGLIGIBLE == "negligible"

    def test_risk_domain_data_privacy(self):
        assert RiskDomain.DATA_PRIVACY == "data_privacy"

    def test_risk_domain_access_control(self):
        assert RiskDomain.ACCESS_CONTROL == "access_control"

    def test_risk_domain_encryption(self):
        assert RiskDomain.ENCRYPTION == "encryption"

    def test_risk_domain_audit_logging(self):
        assert RiskDomain.AUDIT_LOGGING == "audit_logging"

    def test_risk_domain_change_management(self):
        assert RiskDomain.CHANGE_MANAGEMENT == "change_management"

    def test_assessment_status_completed(self):
        assert AssessmentStatus.COMPLETED == "completed"

    def test_assessment_status_in_progress(self):
        assert AssessmentStatus.IN_PROGRESS == "in_progress"

    def test_assessment_status_scheduled(self):
        assert AssessmentStatus.SCHEDULED == "scheduled"

    def test_assessment_status_overdue(self):
        assert AssessmentStatus.OVERDUE == "overdue"

    def test_assessment_status_cancelled(self):
        assert AssessmentStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_risk_record_defaults(self):
        r = RiskRecord()
        assert r.id
        assert r.control_id == ""
        assert r.risk_level == RiskLevel.LOW
        assert r.risk_domain == RiskDomain.DATA_PRIVACY
        assert r.assessment_status == AssessmentStatus.SCHEDULED
        assert r.risk_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_risk_rule_defaults(self):
        p = RiskRule()
        assert p.id
        assert p.domain_pattern == ""
        assert p.risk_domain == RiskDomain.DATA_PRIVACY
        assert p.max_acceptable_risk == 0.0
        assert p.review_frequency_days == 90
        assert p.description == ""
        assert p.created_at > 0

    def test_compliance_risk_report_defaults(self):
        r = ComplianceRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_level == {}
        assert r.by_domain == {}
        assert r.by_status == {}
        assert r.critical_risks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_risk
# ---------------------------------------------------------------------------


class TestRecordRisk:
    def test_basic(self):
        eng = _engine()
        r = eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.HIGH,
            risk_domain=RiskDomain.ACCESS_CONTROL,
            assessment_status=AssessmentStatus.COMPLETED,
            risk_score=85.0,
            team="security",
        )
        assert r.control_id == "CTRL-001"
        assert r.risk_level == RiskLevel.HIGH
        assert r.risk_domain == RiskDomain.ACCESS_CONTROL
        assert r.assessment_status == AssessmentStatus.COMPLETED
        assert r.risk_score == 85.0
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(control_id=f"CTRL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_risk
# ---------------------------------------------------------------------------


class TestGetRisk:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.CRITICAL,
        )
        result = eng.get_risk(r.id)
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_risk("nonexistent") is None


# ---------------------------------------------------------------------------
# list_risks
# ---------------------------------------------------------------------------


class TestListRisks:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk(control_id="CTRL-001")
        eng.record_risk(control_id="CTRL-002")
        assert len(eng.list_risks()) == 2

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.HIGH,
        )
        eng.record_risk(
            control_id="CTRL-002",
            risk_level=RiskLevel.LOW,
        )
        results = eng.list_risks(risk_level=RiskLevel.HIGH)
        assert len(results) == 1

    def test_filter_by_risk_domain(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_domain=RiskDomain.ENCRYPTION,
        )
        eng.record_risk(
            control_id="CTRL-002",
            risk_domain=RiskDomain.AUDIT_LOGGING,
        )
        results = eng.list_risks(risk_domain=RiskDomain.ENCRYPTION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_risk(control_id="CTRL-001", team="security")
        eng.record_risk(control_id="CTRL-002", team="platform")
        results = eng.list_risks(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_risk(control_id=f"CTRL-{i}")
        assert len(eng.list_risks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            domain_pattern="privacy-*",
            risk_domain=RiskDomain.CHANGE_MANAGEMENT,
            max_acceptable_risk=50.0,
            review_frequency_days=30,
            description="Change management rule",
        )
        assert p.domain_pattern == "privacy-*"
        assert p.risk_domain == RiskDomain.CHANGE_MANAGEMENT
        assert p.max_acceptable_risk == 50.0
        assert p.review_frequency_days == 30

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(domain_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_risk_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRiskDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.HIGH,
            risk_score=80.0,
        )
        eng.record_risk(
            control_id="CTRL-002",
            risk_level=RiskLevel.HIGH,
            risk_score=60.0,
        )
        result = eng.analyze_risk_distribution()
        assert "high" in result
        assert result["high"]["count"] == 2
        assert result["high"]["avg_risk_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_risk_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_risks
# ---------------------------------------------------------------------------


class TestIdentifyCriticalRisks:
    def test_detects_critical_and_high(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_risk(
            control_id="CTRL-002",
            risk_level=RiskLevel.LOW,
        )
        eng.record_risk(
            control_id="CTRL-003",
            risk_level=RiskLevel.HIGH,
        )
        results = eng.identify_critical_risks()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_risks() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_risk(control_id="CTRL-001", team="security", risk_score=90.0)
        eng.record_risk(control_id="CTRL-002", team="security", risk_score=70.0)
        eng.record_risk(control_id="CTRL-003", team="platform", risk_score=30.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["team"] == "security"
        assert results[0]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectRiskTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.record_risk(control_id="CTRL", risk_score=score)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [10.0, 10.0, 30.0, 30.0]:
            eng.record_risk(control_id="CTRL", risk_score=score)
        result = eng.detect_risk_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.CRITICAL,
            risk_score=95.0,
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, ComplianceRiskReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
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
        eng.record_risk(control_id="CTRL-001")
        eng.add_rule(domain_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_risk(
            control_id="CTRL-001",
            risk_level=RiskLevel.HIGH,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_controls"] == 1
        assert "high" in stats["level_distribution"]
