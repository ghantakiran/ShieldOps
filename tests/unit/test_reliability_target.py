"""Tests for shieldops.sla.reliability_target — ReliabilityTargetAdvisor."""

from __future__ import annotations

from shieldops.sla.reliability_target import (
    BusinessTier,
    RecommendationBasis,
    ReliabilityTarget,
    ReliabilityTargetAdvisor,
    TargetAdvisorReport,
    TargetAssessment,
    TargetConfidence,
)


def _engine(**kw) -> ReliabilityTargetAdvisor:
    return ReliabilityTargetAdvisor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BusinessTier (5)
    def test_tier_platinum(self):
        assert BusinessTier.PLATINUM == "platinum"

    def test_tier_gold(self):
        assert BusinessTier.GOLD == "gold"

    def test_tier_silver(self):
        assert BusinessTier.SILVER == "silver"

    def test_tier_bronze(self):
        assert BusinessTier.BRONZE == "bronze"

    def test_tier_internal(self):
        assert BusinessTier.INTERNAL == "internal"

    # RecommendationBasis (5)
    def test_basis_historical_p50(self):
        assert RecommendationBasis.HISTORICAL_P50 == "historical_p50"

    def test_basis_historical_p95(self):
        assert RecommendationBasis.HISTORICAL_P95 == "historical_p95"

    def test_basis_dependency_chain(self):
        assert RecommendationBasis.DEPENDENCY_CHAIN == "dependency_chain"

    def test_basis_industry_benchmark(self):
        assert RecommendationBasis.INDUSTRY_BENCHMARK == "industry_benchmark"

    def test_basis_custom(self):
        assert RecommendationBasis.CUSTOM == "custom"

    # TargetConfidence (5)
    def test_confidence_very_high(self):
        assert TargetConfidence.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert TargetConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert TargetConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert TargetConfidence.LOW == "low"

    def test_confidence_insufficient_data(self):
        assert TargetConfidence.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_target_defaults(self):
        t = ReliabilityTarget()
        assert t.id
        assert t.service_name == ""
        assert t.business_tier == BusinessTier.SILVER
        assert t.current_reliability_pct == 0.0
        assert t.recommended_target_pct == 0.0
        assert t.confidence == (TargetConfidence.INSUFFICIENT_DATA)
        assert t.dependencies == []
        assert t.created_at > 0

    def test_assessment_defaults(self):
        a = TargetAssessment()
        assert a.id
        assert a.target_id == ""
        assert a.actual_pct == 0.0
        assert a.met is False
        assert a.assessment_window == ""

    def test_report_defaults(self):
        r = TargetAdvisorReport()
        assert r.total_targets == 0
        assert r.total_assessments == 0
        assert r.avg_reliability_pct == 0.0
        assert r.by_tier == {}
        assert r.by_confidence == {}
        assert r.underperforming == []
        assert r.recommendations == []


# -------------------------------------------------------------------
# create_target
# -------------------------------------------------------------------


class TestCreateTarget:
    def test_basic_create(self):
        eng = _engine()
        t = eng.create_target("api-gateway")
        assert t.service_name == "api-gateway"
        assert t.business_tier == BusinessTier.SILVER
        assert t.recommended_target_pct == 99.9

    def test_platinum_target(self):
        eng = _engine()
        t = eng.create_target(
            "payments",
            business_tier=BusinessTier.PLATINUM,
        )
        assert t.recommended_target_pct == 99.99

    def test_with_dependencies(self):
        eng = _engine()
        t = eng.create_target("web", dependencies=["api", "db"])
        assert t.dependencies == ["api", "db"]

    def test_eviction_at_max(self):
        eng = _engine(max_targets=3)
        for i in range(5):
            eng.create_target(f"svc{i}")
        assert len(eng._targets) == 3

    def test_unique_ids(self):
        eng = _engine()
        t1 = eng.create_target("svc1")
        t2 = eng.create_target("svc2")
        assert t1.id != t2.id


# -------------------------------------------------------------------
# get_target
# -------------------------------------------------------------------


class TestGetTarget:
    def test_found(self):
        eng = _engine()
        t = eng.create_target("test")
        assert eng.get_target(t.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_target("nonexistent") is None


# -------------------------------------------------------------------
# list_targets
# -------------------------------------------------------------------


class TestListTargets:
    def test_list_all(self):
        eng = _engine()
        eng.create_target("svc1")
        eng.create_target("svc2")
        assert len(eng.list_targets()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_target("api")
        eng.create_target("web")
        results = eng.list_targets(service_name="api")
        assert len(results) == 1

    def test_filter_by_tier(self):
        eng = _engine()
        eng.create_target(
            "critical",
            business_tier=BusinessTier.PLATINUM,
        )
        eng.create_target(
            "normal",
            business_tier=BusinessTier.SILVER,
        )
        results = eng.list_targets(business_tier=BusinessTier.PLATINUM)
        assert len(results) == 1


# -------------------------------------------------------------------
# recommend_target
# -------------------------------------------------------------------


class TestRecommendTarget:
    def test_very_high_confidence(self):
        eng = _engine()
        t = eng.recommend_target("api", BusinessTier.SILVER, 99.95)
        assert t.confidence == TargetConfidence.VERY_HIGH
        assert t.recommended_target_pct == 99.95

    def test_high_confidence(self):
        eng = _engine()
        t = eng.recommend_target("api", BusinessTier.SILVER, 99.5)
        assert t.confidence == TargetConfidence.HIGH
        assert t.recommended_target_pct == 99.9

    def test_moderate_confidence(self):
        eng = _engine()
        t = eng.recommend_target("api", BusinessTier.SILVER, 97.0)
        assert t.confidence == TargetConfidence.MODERATE
        assert t.recommended_target_pct == round((97.0 + 99.9) / 2.0, 4)

    def test_gap_calculated(self):
        eng = _engine()
        t = eng.recommend_target("api", BusinessTier.GOLD, 99.0)
        assert t.gap_pct == round(t.recommended_target_pct - 99.0, 4)


# -------------------------------------------------------------------
# assess_target
# -------------------------------------------------------------------


class TestAssessTarget:
    def test_target_met(self):
        eng = _engine()
        t = eng.create_target("api", current_reliability_pct=99.9)
        assessment = eng.assess_target(t.id, 99.95)
        assert assessment is not None
        assert assessment.met is True

    def test_target_missed(self):
        eng = _engine()
        t = eng.create_target("api", current_reliability_pct=99.9)
        assessment = eng.assess_target(t.id, 99.0)
        assert assessment is not None
        assert assessment.met is False

    def test_not_found(self):
        eng = _engine()
        assert eng.assess_target("bad", 99.0) is None

    def test_updates_gap(self):
        eng = _engine()
        t = eng.create_target("api", current_reliability_pct=99.9)
        eng.assess_target(t.id, 98.0)
        assert t.gap_pct == round(t.recommended_target_pct - 98.0, 4)


# -------------------------------------------------------------------
# identify_overcommitted
# -------------------------------------------------------------------


class TestIdentifyOvercommitted:
    def test_overcommitted(self):
        eng = _engine()
        eng.create_target(
            "struggling",
            current_reliability_pct=96.0,
        )
        results = eng.identify_overcommitted()
        assert len(results) == 1
        assert results[0]["service"] == "struggling"

    def test_no_overcommitted(self):
        eng = _engine()
        eng.create_target("fine", current_reliability_pct=99.95)
        assert len(eng.identify_overcommitted()) == 0


# -------------------------------------------------------------------
# identify_undercommitted
# -------------------------------------------------------------------


class TestIdentifyUndercommitted:
    def test_undercommitted(self):
        eng = _engine()
        eng.create_target(
            "overachiever",
            business_tier=BusinessTier.INTERNAL,
            current_reliability_pct=99.99,
        )
        results = eng.identify_undercommitted()
        assert len(results) == 1
        assert results[0]["service"] == "overachiever"

    def test_no_undercommitted(self):
        eng = _engine()
        eng.create_target("normal", current_reliability_pct=99.9)
        assert len(eng.identify_undercommitted()) == 0


# -------------------------------------------------------------------
# analyze_dependency_impact
# -------------------------------------------------------------------


class TestAnalyzeDependencyImpact:
    def test_with_deps(self):
        eng = _engine()
        eng.create_target("web", dependencies=["db"])
        eng.create_target("api", dependencies=["db"])
        eng.create_target("db")
        results = eng.analyze_dependency_impact()
        assert len(results) == 1
        assert results[0]["dependency"] == "db"
        assert results[0]["dependent_count"] == 2

    def test_no_deps(self):
        eng = _engine()
        eng.create_target("standalone")
        results = eng.analyze_dependency_impact()
        assert len(results) == 0


# -------------------------------------------------------------------
# generate_advisor_report
# -------------------------------------------------------------------


class TestGenerateAdvisorReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_advisor_report()
        assert report.total_targets == 0

    def test_populated_report(self):
        eng = _engine()
        eng.create_target("api", current_reliability_pct=99.9)
        eng.create_target(
            "slow",
            current_reliability_pct=95.0,
        )
        report = eng.generate_advisor_report()
        assert report.total_targets == 2
        assert report.avg_reliability_pct > 0
        assert "slow" in report.underperforming


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.create_target("test")
        t = eng._targets[0]
        eng.assess_target(t.id, 99.0)
        eng.clear_data()
        assert len(eng._targets) == 0
        assert len(eng._assessments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_targets"] == 0
        assert stats["total_assessments"] == 0
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine()
        t = eng.create_target("api")
        eng.assess_target(t.id, 99.5)
        stats = eng.get_stats()
        assert stats["total_targets"] == 1
        assert stats["total_assessments"] == 1
        assert stats["unique_services"] == 1
        assert "silver" in stats["tiers"]
