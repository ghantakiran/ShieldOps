"""Tests for shieldops.topology.infra_health_scorer — InfrastructureHealthScorer."""

from __future__ import annotations

from shieldops.topology.infra_health_scorer import (
    HealthDimension,
    HealthDimensionDetail,
    HealthGrade,
    HealthScoreRecord,
    InfraHealthScorerReport,
    InfraLayer,
    InfrastructureHealthScorer,
)


def _engine(**kw) -> InfrastructureHealthScorer:
    return InfrastructureHealthScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # HealthDimension (5)
    def test_dimension_availability(self):
        assert HealthDimension.AVAILABILITY == "availability"

    def test_dimension_performance(self):
        assert HealthDimension.PERFORMANCE == "performance"

    def test_dimension_reliability(self):
        assert HealthDimension.RELIABILITY == "reliability"

    def test_dimension_security(self):
        assert HealthDimension.SECURITY == "security"

    def test_dimension_capacity(self):
        assert HealthDimension.CAPACITY == "capacity"

    # HealthGrade (5)
    def test_grade_excellent(self):
        assert HealthGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert HealthGrade.GOOD == "good"

    def test_grade_fair(self):
        assert HealthGrade.FAIR == "fair"

    def test_grade_poor(self):
        assert HealthGrade.POOR == "poor"

    def test_grade_critical(self):
        assert HealthGrade.CRITICAL == "critical"

    # InfraLayer (5)
    def test_layer_compute(self):
        assert InfraLayer.COMPUTE == "compute"

    def test_layer_storage(self):
        assert InfraLayer.STORAGE == "storage"

    def test_layer_network(self):
        assert InfraLayer.NETWORK == "network"

    def test_layer_database(self):
        assert InfraLayer.DATABASE == "database"

    def test_layer_platform(self):
        assert InfraLayer.PLATFORM == "platform"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_health_score_record_defaults(self):
        r = HealthScoreRecord()
        assert r.id
        assert r.resource_name == ""
        assert r.layer == InfraLayer.COMPUTE
        assert r.grade == HealthGrade.GOOD
        assert r.health_score == 0.0
        assert r.dimension == HealthDimension.AVAILABILITY
        assert r.details == ""
        assert r.created_at > 0

    def test_health_dimension_detail_defaults(self):
        r = HealthDimensionDetail()
        assert r.id
        assert r.detail_name == ""
        assert r.dimension == HealthDimension.AVAILABILITY
        assert r.grade == HealthGrade.GOOD
        assert r.score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_infra_health_scorer_report_defaults(self):
        r = InfraHealthScorerReport()
        assert r.total_health_records == 0
        assert r.total_dimension_details == 0
        assert r.avg_health_score_pct == 0.0
        assert r.by_layer == {}
        assert r.by_grade == {}
        assert r.unhealthy_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_health
# -------------------------------------------------------------------


class TestRecordHealth:
    def test_basic(self):
        eng = _engine()
        r = eng.record_health(
            "prod-db-01",
            layer=InfraLayer.DATABASE,
            grade=HealthGrade.GOOD,
            health_score=85.0,
            dimension=HealthDimension.AVAILABILITY,
            details="nominal",
        )
        assert r.resource_name == "prod-db-01"
        assert r.health_score == 85.0
        assert r.id

    def test_stored(self):
        eng = _engine()
        eng.record_health("prod-db-01")
        assert len(eng._records) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_health(f"resource-{i}")
        assert len(eng._records) == 2

    def test_multiple_resources(self):
        eng = _engine()
        eng.record_health("prod-db-01")
        eng.record_health("prod-api-01")
        assert len(eng._records) == 2


# -------------------------------------------------------------------
# get_health
# -------------------------------------------------------------------


class TestGetHealth:
    def test_found(self):
        eng = _engine()
        r = eng.record_health("prod-db-01")
        result = eng.get_health(r.id)
        assert result is not None
        assert result.id == r.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_health("nonexistent") is None


# -------------------------------------------------------------------
# list_health_records
# -------------------------------------------------------------------


class TestListHealthRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_health("prod-db-01")
        eng.record_health("prod-api-01")
        assert len(eng.list_health_records()) == 2

    def test_filter_by_layer(self):
        eng = _engine()
        eng.record_health("prod-db-01", layer=InfraLayer.DATABASE)
        eng.record_health("prod-api-01", layer=InfraLayer.COMPUTE)
        results = eng.list_health_records(layer=InfraLayer.DATABASE)
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_health("prod-db-01", grade=HealthGrade.CRITICAL)
        eng.record_health("prod-api-01", grade=HealthGrade.GOOD)
        results = eng.list_health_records(grade=HealthGrade.CRITICAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_dimension
# -------------------------------------------------------------------


class TestAddDimension:
    def test_basic(self):
        eng = _engine()
        d = eng.add_dimension(
            "availability-check",
            dimension=HealthDimension.AVAILABILITY,
            grade=HealthGrade.EXCELLENT,
            score=98.0,
            description="99.9% uptime verified",
        )
        assert d.detail_name == "availability-check"
        assert d.score == 98.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_dimension(f"dim-{i}")
        assert len(eng._dimension_details) == 2


# -------------------------------------------------------------------
# analyze_health_by_layer
# -------------------------------------------------------------------


class TestAnalyzeHealthByLayer:
    def test_with_data(self):
        eng = _engine()
        eng.record_health("prod-db-01", layer=InfraLayer.DATABASE, health_score=80.0)
        eng.record_health("prod-db-02", layer=InfraLayer.DATABASE, health_score=60.0)
        result = eng.analyze_health_by_layer(InfraLayer.DATABASE)
        assert result["layer"] == "database"
        assert result["total_records"] == 2
        assert result["avg_health_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_health_by_layer(InfraLayer.NETWORK)
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_unhealthy_infra
# -------------------------------------------------------------------


class TestIdentifyUnhealthyInfra:
    def test_with_unhealthy(self):
        eng = _engine()
        eng.record_health("prod-db-01", grade=HealthGrade.CRITICAL)
        eng.record_health("prod-db-01", grade=HealthGrade.POOR)
        eng.record_health("prod-api-01", grade=HealthGrade.GOOD)
        results = eng.identify_unhealthy_infra()
        assert len(results) == 1
        assert results[0]["resource_name"] == "prod-db-01"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_infra() == []


# -------------------------------------------------------------------
# rank_by_health_score
# -------------------------------------------------------------------


class TestRankByHealthScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_health("prod-db-01", health_score=30.0)
        eng.record_health("prod-db-01", health_score=20.0)
        eng.record_health("prod-api-01", health_score=90.0)
        results = eng.rank_by_health_score()
        assert results[0]["resource_name"] == "prod-db-01"
        assert results[0]["avg_health_score"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_health_score() == []


# -------------------------------------------------------------------
# detect_health_trends
# -------------------------------------------------------------------


class TestDetectHealthTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_health("prod-db-01")
        eng.record_health("prod-api-01")
        results = eng.detect_health_trends()
        assert len(results) == 1
        assert results[0]["resource_name"] == "prod-db-01"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_health("prod-db-01")
        assert eng.detect_health_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_health_score=70.0)
        eng.record_health("prod-db-01", grade=HealthGrade.CRITICAL, health_score=40.0)
        eng.record_health("prod-api-01", grade=HealthGrade.GOOD, health_score=90.0)
        eng.add_dimension("dim-1")
        report = eng.generate_report()
        assert report.total_health_records == 2
        assert report.total_dimension_details == 1
        assert report.by_layer != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_health_records == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_health("prod-db-01")
        eng.add_dimension("dim-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._dimension_details) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_health_records"] == 0
        assert stats["total_dimension_details"] == 0
        assert stats["layer_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_health("prod-db-01", layer=InfraLayer.DATABASE)
        eng.record_health("prod-net-01", layer=InfraLayer.NETWORK)
        eng.add_dimension("dim-1")
        stats = eng.get_stats()
        assert stats["total_health_records"] == 2
        assert stats["total_dimension_details"] == 1
        assert stats["unique_resources"] == 2
