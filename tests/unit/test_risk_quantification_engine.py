"""Tests for shieldops.security.risk_quantification_engine — RiskQuantificationEngine."""

from __future__ import annotations

from shieldops.security.risk_quantification_engine import (
    ImpactSeverity,
    LikelihoodLevel,
    RiskAnalysis,
    RiskCategory,
    RiskQuantificationEngine,
    RiskQuantificationReport,
    RiskRecord,
)


def _engine(**kw) -> RiskQuantificationEngine:
    return RiskQuantificationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_operational(self):
        assert RiskCategory.OPERATIONAL == "operational"

    def test_category_financial(self):
        assert RiskCategory.FINANCIAL == "financial"

    def test_category_reputational(self):
        assert RiskCategory.REPUTATIONAL == "reputational"

    def test_category_compliance(self):
        assert RiskCategory.COMPLIANCE == "compliance"

    def test_category_strategic(self):
        assert RiskCategory.STRATEGIC == "strategic"

    def test_likelihood_very_high(self):
        assert LikelihoodLevel.VERY_HIGH == "very_high"

    def test_likelihood_high(self):
        assert LikelihoodLevel.HIGH == "high"

    def test_likelihood_medium(self):
        assert LikelihoodLevel.MEDIUM == "medium"

    def test_likelihood_low(self):
        assert LikelihoodLevel.LOW == "low"

    def test_likelihood_very_low(self):
        assert LikelihoodLevel.VERY_LOW == "very_low"

    def test_impact_catastrophic(self):
        assert ImpactSeverity.CATASTROPHIC == "catastrophic"

    def test_impact_major(self):
        assert ImpactSeverity.MAJOR == "major"

    def test_impact_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_impact_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_impact_negligible(self):
        assert ImpactSeverity.NEGLIGIBLE == "negligible"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_risk_record_defaults(self):
        r = RiskRecord()
        assert r.id
        assert r.risk_name == ""
        assert r.risk_category == RiskCategory.OPERATIONAL
        assert r.likelihood_level == LikelihoodLevel.VERY_HIGH
        assert r.impact_severity == ImpactSeverity.CATASTROPHIC
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_risk_analysis_defaults(self):
        c = RiskAnalysis()
        assert c.id
        assert c.risk_name == ""
        assert c.risk_category == RiskCategory.OPERATIONAL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_risk_quantification_report_defaults(self):
        r = RiskQuantificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_category == {}
        assert r.by_likelihood == {}
        assert r.by_impact == {}
        assert r.top_high_risk == []
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
            risk_name="data-breach-risk",
            risk_category=RiskCategory.FINANCIAL,
            likelihood_level=LikelihoodLevel.HIGH,
            impact_severity=ImpactSeverity.MAJOR,
            risk_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.risk_name == "data-breach-risk"
        assert r.risk_category == RiskCategory.FINANCIAL
        assert r.likelihood_level == LikelihoodLevel.HIGH
        assert r.impact_severity == ImpactSeverity.MAJOR
        assert r.risk_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(risk_name=f"RISK-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_risk
# ---------------------------------------------------------------------------


class TestGetRisk:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk(
            risk_name="data-breach-risk",
            impact_severity=ImpactSeverity.CATASTROPHIC,
        )
        result = eng.get_risk(r.id)
        assert result is not None
        assert result.impact_severity == ImpactSeverity.CATASTROPHIC

    def test_not_found(self):
        eng = _engine()
        assert eng.get_risk("nonexistent") is None


# ---------------------------------------------------------------------------
# list_risks
# ---------------------------------------------------------------------------


class TestListRisks:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk(risk_name="RISK-001")
        eng.record_risk(risk_name="RISK-002")
        assert len(eng.list_risks()) == 2

    def test_filter_by_risk_category(self):
        eng = _engine()
        eng.record_risk(
            risk_name="RISK-001",
            risk_category=RiskCategory.OPERATIONAL,
        )
        eng.record_risk(
            risk_name="RISK-002",
            risk_category=RiskCategory.FINANCIAL,
        )
        results = eng.list_risks(risk_category=RiskCategory.OPERATIONAL)
        assert len(results) == 1

    def test_filter_by_likelihood_level(self):
        eng = _engine()
        eng.record_risk(
            risk_name="RISK-001",
            likelihood_level=LikelihoodLevel.VERY_HIGH,
        )
        eng.record_risk(
            risk_name="RISK-002",
            likelihood_level=LikelihoodLevel.LOW,
        )
        results = eng.list_risks(
            likelihood_level=LikelihoodLevel.VERY_HIGH,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_risk(risk_name="RISK-001", team="security")
        eng.record_risk(risk_name="RISK-002", team="platform")
        results = eng.list_risks(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_risk(risk_name=f"RISK-{i}")
        assert len(eng.list_risks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            risk_name="data-breach-risk",
            risk_category=RiskCategory.FINANCIAL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high risk identified",
        )
        assert a.risk_name == "data-breach-risk"
        assert a.risk_category == RiskCategory.FINANCIAL
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(risk_name=f"RISK-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_risk_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRiskDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk(
            risk_name="RISK-001",
            risk_category=RiskCategory.OPERATIONAL,
            risk_score=90.0,
        )
        eng.record_risk(
            risk_name="RISK-002",
            risk_category=RiskCategory.OPERATIONAL,
            risk_score=70.0,
        )
        result = eng.analyze_risk_distribution()
        assert "operational" in result
        assert result["operational"]["count"] == 2
        assert result["operational"]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_risk_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risks
# ---------------------------------------------------------------------------


class TestIdentifyHighRisks:
    def test_detects_above_threshold(self):
        eng = _engine(risk_tolerance_threshold=70.0)
        eng.record_risk(risk_name="RISK-001", risk_score=90.0)
        eng.record_risk(risk_name="RISK-002", risk_score=50.0)
        results = eng.identify_high_risks()
        assert len(results) == 1
        assert results[0]["risk_name"] == "RISK-001"

    def test_sorted_descending(self):
        eng = _engine(risk_tolerance_threshold=70.0)
        eng.record_risk(risk_name="RISK-001", risk_score=80.0)
        eng.record_risk(risk_name="RISK-002", risk_score=95.0)
        results = eng.identify_high_risks()
        assert len(results) == 2
        assert results[0]["risk_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risks() == []


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankByRisk:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_risk(risk_name="RISK-001", service="auth-svc", risk_score=50.0)
        eng.record_risk(risk_name="RISK-002", service="api-gw", risk_score=90.0)
        results = eng.rank_by_risk()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectRiskTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(risk_name="RISK-001", analysis_score=50.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        eng.add_analysis(risk_name="RISK-001", analysis_score=20.0)
        eng.add_analysis(risk_name="RISK-002", analysis_score=20.0)
        eng.add_analysis(risk_name="RISK-003", analysis_score=80.0)
        eng.add_analysis(risk_name="RISK-004", analysis_score=80.0)
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
        eng = _engine(risk_tolerance_threshold=70.0)
        eng.record_risk(
            risk_name="data-breach-risk",
            risk_category=RiskCategory.FINANCIAL,
            likelihood_level=LikelihoodLevel.HIGH,
            impact_severity=ImpactSeverity.MAJOR,
            risk_score=90.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RiskQuantificationReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_high_risk) == 1
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
        eng.record_risk(risk_name="RISK-001")
        eng.add_analysis(risk_name="RISK-001")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_risk(
            risk_name="RISK-001",
            risk_category=RiskCategory.OPERATIONAL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "operational" in stats["category_distribution"]
