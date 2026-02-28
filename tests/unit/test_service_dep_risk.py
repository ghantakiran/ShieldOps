"""Tests for shieldops.topology.service_dep_risk — ServiceDependencyRiskScorer."""

from __future__ import annotations

from shieldops.topology.service_dep_risk import (
    DependencyDirection,
    DependencyRiskRecord,
    DependencyRiskReport,
    DependencyType,
    RiskFactor,
    RiskLevel,
    ServiceDependencyRiskScorer,
)


def _engine(**kw) -> ServiceDependencyRiskScorer:
    return ServiceDependencyRiskScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DependencyType (5)
    def test_type_synchronous(self):
        assert DependencyType.SYNCHRONOUS == "synchronous"

    def test_type_asynchronous(self):
        assert DependencyType.ASYNCHRONOUS == "asynchronous"

    def test_type_database(self):
        assert DependencyType.DATABASE == "database"

    def test_type_cache(self):
        assert DependencyType.CACHE == "cache"

    def test_type_external_api(self):
        assert DependencyType.EXTERNAL_API == "external_api"

    # RiskLevel (5)
    def test_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_level_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_level_negligible(self):
        assert RiskLevel.NEGLIGIBLE == "negligible"

    # DependencyDirection (5)
    def test_direction_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_direction_bidirectional(self):
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_direction_internal(self):
        assert DependencyDirection.INTERNAL == "internal"

    def test_direction_external(self):
        assert DependencyDirection.EXTERNAL == "external"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_dependency_risk_record_defaults(self):
        r = DependencyRiskRecord()
        assert r.id
        assert r.service == ""
        assert r.dependency == ""
        assert r.dep_type == DependencyType.SYNCHRONOUS
        assert r.risk_score == 0.0
        assert r.risk_level == RiskLevel.LOW
        assert r.direction == DependencyDirection.DOWNSTREAM
        assert r.details == ""
        assert r.created_at > 0

    def test_risk_factor_defaults(self):
        r = RiskFactor()
        assert r.id
        assert r.service == ""
        assert r.dependency == ""
        assert r.factor_name == ""
        assert r.factor_score == 0.0
        assert r.weight == 1.0
        assert r.created_at > 0

    def test_dependency_risk_report_defaults(self):
        r = DependencyRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_factors == 0
        assert r.avg_risk_score == 0.0
        assert r.by_dep_type == {}
        assert r.by_risk_level == {}
        assert r.by_direction == {}
        assert r.high_risk_deps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_risk
# -------------------------------------------------------------------


class TestRecordRisk:
    def test_basic(self):
        eng = _engine()
        r = eng.record_risk(
            "svc-a",
            "dep-1",
            dep_type=DependencyType.DATABASE,
            risk_level=RiskLevel.HIGH,
        )
        assert r.service == "svc-a"
        assert r.dependency == "dep-1"
        assert r.dep_type == DependencyType.DATABASE

    def test_with_risk_score(self):
        eng = _engine()
        r = eng.record_risk("svc-b", "dep-2", risk_score=90.0)
        assert r.risk_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(f"svc-{i}", f"dep-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_risk
# -------------------------------------------------------------------


class TestGetRisk:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk("svc-a", "dep-1")
        assert eng.get_risk(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_risk("nonexistent") is None


# -------------------------------------------------------------------
# list_risks
# -------------------------------------------------------------------


class TestListRisks:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1")
        eng.record_risk("svc-b", "dep-2")
        assert len(eng.list_risks()) == 2

    def test_filter_by_dep_type(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", dep_type=DependencyType.CACHE)
        eng.record_risk("svc-b", "dep-2", dep_type=DependencyType.DATABASE)
        results = eng.list_risks(dep_type=DependencyType.CACHE)
        assert len(results) == 1

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", risk_level=RiskLevel.CRITICAL)
        eng.record_risk("svc-b", "dep-2", risk_level=RiskLevel.LOW)
        results = eng.list_risks(risk_level=RiskLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1")
        eng.record_risk("svc-b", "dep-2")
        results = eng.list_risks(service="svc-a")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_risk_factor
# -------------------------------------------------------------------


class TestAddRiskFactor:
    def test_basic(self):
        eng = _engine()
        f = eng.add_risk_factor(
            "svc-a",
            "dep-1",
            "single_maintainer",
            factor_score=75.0,
            weight=1.5,
        )
        assert f.service == "svc-a"
        assert f.factor_name == "single_maintainer"
        assert f.factor_score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_risk_factor(f"svc-{i}", f"dep-{i}", f"factor-{i}")
        assert len(eng._factors) == 2


# -------------------------------------------------------------------
# analyze_risk_by_service
# -------------------------------------------------------------------


class TestAnalyzeRiskByService:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", risk_score=60.0)
        eng.record_risk("svc-a", "dep-2", risk_score=80.0)
        eng.record_risk("svc-b", "dep-3", risk_score=20.0)
        results = eng.analyze_risk_by_service()
        assert len(results) == 2
        assert results[0]["service"] == "svc-a"
        assert results[0]["avg_risk_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_risk_by_service() == []


# -------------------------------------------------------------------
# identify_high_risk_deps
# -------------------------------------------------------------------


class TestIdentifyHighRiskDeps:
    def test_with_high_risk(self):
        eng = _engine(max_risk_score=80.0)
        eng.record_risk("svc-a", "dep-1", risk_score=90.0)
        eng.record_risk("svc-b", "dep-2", risk_score=50.0)
        results = eng.identify_high_risk_deps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_deps() == []


# -------------------------------------------------------------------
# rank_by_risk_score
# -------------------------------------------------------------------


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", risk_score=90.0)
        eng.record_risk("svc-a", "dep-2", risk_score=70.0)
        eng.record_risk("svc-b", "dep-3", risk_score=20.0)
        results = eng.rank_by_risk_score()
        assert results[0]["service"] == "svc-a"
        assert results[0]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# -------------------------------------------------------------------
# detect_risk_trends
# -------------------------------------------------------------------


class TestDetectRiskTrends:
    def test_increasing_trend(self):
        eng = _engine()
        eng.record_risk("svc-a", "d1", risk_score=10.0)
        eng.record_risk("svc-a", "d2", risk_score=12.0)
        eng.record_risk("svc-a", "d3", risk_score=30.0)
        eng.record_risk("svc-a", "d4", risk_score=35.0)
        results = eng.detect_risk_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "increasing"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_risk("svc-a", "d1", risk_score=10.0)
        results = eng.detect_risk_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        eng.record_risk("svc-a", "d1", risk_score=50.0)
        eng.record_risk("svc-a", "d2", risk_score=51.0)
        eng.record_risk("svc-a", "d3", risk_score=50.0)
        eng.record_risk("svc-a", "d4", risk_score=52.0)
        results = eng.detect_risk_trends()
        assert results[0]["trend"] == "stable"


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", risk_score=90.0, risk_level=RiskLevel.HIGH)
        eng.record_risk("svc-b", "dep-2", risk_score=30.0, risk_level=RiskLevel.LOW)
        eng.add_risk_factor("svc-a", "dep-1", "no_fallback")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_factors == 1
        assert report.by_dep_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1")
        eng.add_risk_factor("svc-a", "dep-1", "test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._factors) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_factors"] == 0
        assert stats["dep_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_risk("svc-a", "dep-1", dep_type=DependencyType.DATABASE)
        eng.record_risk("svc-b", "dep-2", dep_type=DependencyType.CACHE)
        eng.add_risk_factor("svc-a", "dep-1", "test")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_factors"] == 1
        assert stats["unique_services"] == 2
