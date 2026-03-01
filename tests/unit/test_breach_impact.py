"""Tests for shieldops.sla.breach_impact — SLABreachImpactAnalyzer."""

from __future__ import annotations

from shieldops.sla.breach_impact import (
    BreachCategory,
    BreachConsequence,
    BreachImpactRecord,
    ImpactAssessment,
    ImpactLevel,
    SLABreachImpactAnalyzer,
    SLABreachImpactReport,
)


def _engine(**kw) -> SLABreachImpactAnalyzer:
    return SLABreachImpactAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_availability(self):
        assert BreachCategory.AVAILABILITY == "availability"

    def test_category_latency(self):
        assert BreachCategory.LATENCY == "latency"

    def test_category_error_rate(self):
        assert BreachCategory.ERROR_RATE == "error_rate"

    def test_category_throughput(self):
        assert BreachCategory.THROUGHPUT == "throughput"

    def test_category_response_time(self):
        assert BreachCategory.RESPONSE_TIME == "response_time"

    def test_impact_catastrophic(self):
        assert ImpactLevel.CATASTROPHIC == "catastrophic"

    def test_impact_major(self):
        assert ImpactLevel.MAJOR == "major"

    def test_impact_moderate(self):
        assert ImpactLevel.MODERATE == "moderate"

    def test_impact_minor(self):
        assert ImpactLevel.MINOR == "minor"

    def test_impact_negligible(self):
        assert ImpactLevel.NEGLIGIBLE == "negligible"

    def test_consequence_financial_penalty(self):
        assert BreachConsequence.FINANCIAL_PENALTY == "financial_penalty"

    def test_consequence_customer_churn(self):
        assert BreachConsequence.CUSTOMER_CHURN == "customer_churn"

    def test_consequence_reputation_damage(self):
        assert BreachConsequence.REPUTATION_DAMAGE == "reputation_damage"

    def test_consequence_contract_risk(self):
        assert BreachConsequence.CONTRACT_RISK == "contract_risk"

    def test_consequence_escalation(self):
        assert BreachConsequence.ESCALATION == "escalation"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_breach_impact_record_defaults(self):
        r = BreachImpactRecord()
        assert r.id
        assert r.sla_id == ""
        assert r.breach_category == BreachCategory.AVAILABILITY
        assert r.impact_level == ImpactLevel.NEGLIGIBLE
        assert r.breach_consequence == BreachConsequence.ESCALATION
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_assessment_defaults(self):
        a = ImpactAssessment()
        assert a.id
        assert a.sla_id == ""
        assert a.breach_category == BreachCategory.AVAILABILITY
        assert a.financial_impact == 0.0
        assert a.affected_customers == 0
        assert a.mitigation_plan == ""
        assert a.description == ""
        assert a.created_at > 0

    def test_sla_breach_impact_report_defaults(self):
        r = SLABreachImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_impact_breaches == 0
        assert r.avg_impact_score == 0.0
        assert r.by_category == {}
        assert r.by_impact_level == {}
        assert r.by_consequence == {}
        assert r.top_breaches == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_breach
# ---------------------------------------------------------------------------


class TestRecordBreach:
    def test_basic(self):
        eng = _engine()
        r = eng.record_breach(
            sla_id="SLA-001",
            breach_category=BreachCategory.LATENCY,
            impact_level=ImpactLevel.MAJOR,
            breach_consequence=BreachConsequence.FINANCIAL_PENALTY,
            impact_score=85.0,
            service="payment-api",
            team="sre",
        )
        assert r.sla_id == "SLA-001"
        assert r.breach_category == BreachCategory.LATENCY
        assert r.impact_level == ImpactLevel.MAJOR
        assert r.breach_consequence == BreachConsequence.FINANCIAL_PENALTY
        assert r.impact_score == 85.0
        assert r.service == "payment-api"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_breach(sla_id=f"SLA-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_breach
# ---------------------------------------------------------------------------


class TestGetBreach:
    def test_found(self):
        eng = _engine()
        r = eng.record_breach(
            sla_id="SLA-001",
            impact_level=ImpactLevel.CATASTROPHIC,
        )
        result = eng.get_breach(r.id)
        assert result is not None
        assert result.impact_level == ImpactLevel.CATASTROPHIC

    def test_not_found(self):
        eng = _engine()
        assert eng.get_breach("nonexistent") is None


# ---------------------------------------------------------------------------
# list_breaches
# ---------------------------------------------------------------------------


class TestListBreaches:
    def test_list_all(self):
        eng = _engine()
        eng.record_breach(sla_id="SLA-001")
        eng.record_breach(sla_id="SLA-002")
        assert len(eng.list_breaches()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            breach_category=BreachCategory.LATENCY,
        )
        eng.record_breach(
            sla_id="SLA-002",
            breach_category=BreachCategory.AVAILABILITY,
        )
        results = eng.list_breaches(category=BreachCategory.LATENCY)
        assert len(results) == 1

    def test_filter_by_impact_level(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            impact_level=ImpactLevel.CATASTROPHIC,
        )
        eng.record_breach(
            sla_id="SLA-002",
            impact_level=ImpactLevel.MINOR,
        )
        results = eng.list_breaches(impact_level=ImpactLevel.CATASTROPHIC)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_breach(sla_id="SLA-001", service="api")
        eng.record_breach(sla_id="SLA-002", service="web")
        results = eng.list_breaches(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_breach(sla_id="SLA-001", team="sre")
        eng.record_breach(sla_id="SLA-002", team="platform")
        results = eng.list_breaches(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_breach(sla_id=f"SLA-{i}")
        assert len(eng.list_breaches(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            sla_id="SLA-001",
            breach_category=BreachCategory.THROUGHPUT,
            financial_impact=50000.0,
            affected_customers=200,
            mitigation_plan="Scale horizontally",
            description="Throughput breach assessment",
        )
        assert a.sla_id == "SLA-001"
        assert a.breach_category == BreachCategory.THROUGHPUT
        assert a.financial_impact == 50000.0
        assert a.affected_customers == 200
        assert a.mitigation_plan == "Scale horizontally"
        assert a.description == "Throughput breach assessment"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(sla_id=f"SLA-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_breach_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeBreachPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            breach_category=BreachCategory.AVAILABILITY,
            impact_score=60.0,
        )
        eng.record_breach(
            sla_id="SLA-002",
            breach_category=BreachCategory.AVAILABILITY,
            impact_score=80.0,
        )
        result = eng.analyze_breach_patterns()
        assert "availability" in result
        assert result["availability"]["count"] == 2
        assert result["availability"]["avg_impact_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_breach_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_breaches
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactBreaches:
    def test_detects_high_impact(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            impact_level=ImpactLevel.CATASTROPHIC,
        )
        eng.record_breach(
            sla_id="SLA-002",
            impact_level=ImpactLevel.MINOR,
        )
        results = eng.identify_high_impact_breaches()
        assert len(results) == 1
        assert results[0]["sla_id"] == "SLA-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_breaches() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByImpactScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_breach(sla_id="SLA-001", service="api", impact_score=90.0)
        eng.record_breach(sla_id="SLA-002", service="api", impact_score=80.0)
        eng.record_breach(sla_id="SLA-003", service="web", impact_score=50.0)
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_breach_trends
# ---------------------------------------------------------------------------


class TestDetectBreachTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_assessment(sla_id="SLA-001", financial_impact=val)
        result = eng.detect_breach_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_assessment(sla_id="SLA-001", financial_impact=val)
        result = eng.detect_breach_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_breach_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            breach_category=BreachCategory.AVAILABILITY,
            impact_level=ImpactLevel.CATASTROPHIC,
            impact_score=90.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SLABreachImpactReport)
        assert report.total_records == 1
        assert report.high_impact_breaches == 1
        assert report.avg_impact_score == 90.0
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
        eng.record_breach(sla_id="SLA-001")
        eng.add_assessment(sla_id="SLA-001")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_breach(
            sla_id="SLA-001",
            breach_category=BreachCategory.LATENCY,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_slas"] == 1
        assert "latency" in stats["category_distribution"]
