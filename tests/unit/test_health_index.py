"""Tests for shieldops.observability.health_index — PlatformHealthIndex."""

from __future__ import annotations

from shieldops.observability.health_index import (
    DimensionScore,
    HealthDimension,
    HealthIndexRecord,
    IndexGrade,
    PlatformHealthIndex,
    PlatformHealthReport,
    TrendDirection,
)


def _engine(**kw) -> PlatformHealthIndex:
    return PlatformHealthIndex(**kw)


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

    def test_dimension_compliance(self):
        assert HealthDimension.COMPLIANCE == "compliance"

    # IndexGrade (5)
    def test_grade_excellent(self):
        assert IndexGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert IndexGrade.GOOD == "good"

    def test_grade_fair(self):
        assert IndexGrade.FAIR == "fair"

    def test_grade_poor(self):
        assert IndexGrade.POOR == "poor"

    def test_grade_critical(self):
        assert IndexGrade.CRITICAL == "critical"

    # TrendDirection (5)
    def test_trend_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_trend_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trend_declining(self):
        assert TrendDirection.DECLINING == "declining"

    def test_trend_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_health_index_record_defaults(self):
        r = HealthIndexRecord()
        assert r.id
        assert r.service_name == ""
        assert r.dimension == HealthDimension.AVAILABILITY
        assert r.grade == IndexGrade.GOOD
        assert r.trend == TrendDirection.STABLE
        assert r.score_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_dimension_score_defaults(self):
        r = DimensionScore()
        assert r.id
        assert r.dimension_name == ""
        assert r.dimension == HealthDimension.AVAILABILITY
        assert r.grade == IndexGrade.GOOD
        assert r.weight == 1.0
        assert r.target_score_pct == 90.0
        assert r.created_at > 0

    def test_platform_health_report_defaults(self):
        r = PlatformHealthReport()
        assert r.total_indices == 0
        assert r.total_dimensions == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_dimension == {}
        assert r.by_grade == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_index
# -------------------------------------------------------------------


class TestRecordIndex:
    def test_basic(self):
        eng = _engine()
        r = eng.record_index("api-gateway", dimension=HealthDimension.AVAILABILITY)
        assert r.service_name == "api-gateway"
        assert r.dimension == HealthDimension.AVAILABILITY

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_index(
            "payment-service",
            dimension=HealthDimension.SECURITY,
            grade=IndexGrade.POOR,
            trend=TrendDirection.DECLINING,
            score_pct=45.0,
            details="Security posture degraded",
        )
        assert r.grade == IndexGrade.POOR
        assert r.trend == TrendDirection.DECLINING
        assert r.score_pct == 45.0
        assert r.details == "Security posture degraded"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_index(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_index
# -------------------------------------------------------------------


class TestGetIndex:
    def test_found(self):
        eng = _engine()
        r = eng.record_index("api-gateway")
        assert eng.get_index(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_index("nonexistent") is None


# -------------------------------------------------------------------
# list_indices
# -------------------------------------------------------------------


class TestListIndices:
    def test_list_all(self):
        eng = _engine()
        eng.record_index("svc-a")
        eng.record_index("svc-b")
        assert len(eng.list_indices()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_index("svc-a")
        eng.record_index("svc-b")
        results = eng.list_indices(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_index("svc-a", dimension=HealthDimension.AVAILABILITY)
        eng.record_index("svc-b", dimension=HealthDimension.SECURITY)
        results = eng.list_indices(dimension=HealthDimension.SECURITY)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_dimension_score
# -------------------------------------------------------------------


class TestAddDimensionScore:
    def test_basic(self):
        eng = _engine()
        d = eng.add_dimension_score(
            "availability-score",
            dimension=HealthDimension.AVAILABILITY,
            grade=IndexGrade.EXCELLENT,
            weight=2.0,
            target_score_pct=95.0,
        )
        assert d.dimension_name == "availability-score"
        assert d.dimension == HealthDimension.AVAILABILITY
        assert d.weight == 2.0
        assert d.target_score_pct == 95.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_dimension_score(f"dim-{i}")
        assert len(eng._dimensions) == 2


# -------------------------------------------------------------------
# analyze_platform_health
# -------------------------------------------------------------------


class TestAnalyzePlatformHealth:
    def test_with_data(self):
        eng = _engine(min_score_pct=70.0)
        eng.record_index("svc-a", score_pct=80.0)
        eng.record_index("svc-a", score_pct=60.0)
        eng.record_index("svc-a", score_pct=90.0)
        result = eng.analyze_platform_health("svc-a")
        assert result["avg_score"] == 76.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_platform_health("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_score_pct=70.0)
        eng.record_index("svc-a", score_pct=80.0)
        eng.record_index("svc-a", score_pct=75.0)
        result = eng.analyze_platform_health("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_weak_dimensions
# -------------------------------------------------------------------


class TestIdentifyWeakDimensions:
    def test_with_weak(self):
        eng = _engine()
        eng.record_index("svc-a", grade=IndexGrade.POOR)
        eng.record_index("svc-a", grade=IndexGrade.CRITICAL)
        eng.record_index("svc-b", grade=IndexGrade.GOOD)
        results = eng.identify_weak_dimensions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["weak_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_dimensions() == []

    def test_single_poor_not_returned(self):
        eng = _engine()
        eng.record_index("svc-a", grade=IndexGrade.POOR)
        assert eng.identify_weak_dimensions() == []


# -------------------------------------------------------------------
# rank_by_health_score
# -------------------------------------------------------------------


class TestRankByHealthScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_index("svc-a", score_pct=20.0)
        eng.record_index("svc-b", score_pct=90.0)
        results = eng.rank_by_health_score()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_score_pct"] == 90.0

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
            eng.record_index("svc-a")
        eng.record_index("svc-b")
        results = eng.detect_health_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_health_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_index("svc-a")
        assert eng.detect_health_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_index("svc-a", grade=IndexGrade.CRITICAL)
        eng.record_index("svc-b", grade=IndexGrade.GOOD)
        eng.add_dimension_score("dim-1")
        report = eng.generate_report()
        assert report.total_indices == 2
        assert report.total_dimensions == 1
        assert report.critical_count == 1
        assert report.by_dimension != {}
        assert report.by_grade != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_indices == 0
        assert report.healthy_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_index("svc-a")
        eng.add_dimension_score("dim-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._dimensions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_indices"] == 0
        assert stats["total_dimensions"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_score_pct=75.0)
        eng.record_index("svc-a", dimension=HealthDimension.AVAILABILITY)
        eng.record_index("svc-b", dimension=HealthDimension.SECURITY)
        eng.add_dimension_score("dim-1")
        stats = eng.get_stats()
        assert stats["total_indices"] == 2
        assert stats["total_dimensions"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_score_pct"] == 75.0
