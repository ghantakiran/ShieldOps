"""Tests for shieldops.topology.health_trend — ServiceHealthTrendAnalyzer."""

from __future__ import annotations

from shieldops.topology.health_trend import (
    HealthDimension,
    HealthGrade,
    HealthTrendRecord,
    ServiceHealthTrendAnalyzer,
    ServiceHealthTrendReport,
    TrendDataPoint,
    TrendDirection,
)


def _engine(**kw) -> ServiceHealthTrendAnalyzer:
    return ServiceHealthTrendAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_availability(self):
        assert HealthDimension.AVAILABILITY == "availability"

    def test_dimension_latency(self):
        assert HealthDimension.LATENCY == "latency"

    def test_dimension_error_rate(self):
        assert HealthDimension.ERROR_RATE == "error_rate"

    def test_dimension_throughput(self):
        assert HealthDimension.THROUGHPUT == "throughput"

    def test_dimension_saturation(self):
        assert HealthDimension.SATURATION == "saturation"

    def test_direction_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_direction_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_direction_degrading(self):
        assert TrendDirection.DEGRADING == "degrading"

    def test_direction_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_direction_insufficient_data(self):
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"

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


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_health_trend_record_defaults(self):
        r = HealthTrendRecord()
        assert r.id
        assert r.service_id == ""
        assert r.health_dimension == HealthDimension.AVAILABILITY
        assert r.trend_direction == TrendDirection.STABLE
        assert r.health_grade == HealthGrade.GOOD
        assert r.health_score == 0.0
        assert r.service == ""
        assert r.created_at > 0

    def test_trend_data_point_defaults(self):
        dp = TrendDataPoint()
        assert dp.id
        assert dp.data_label == ""
        assert dp.health_dimension == HealthDimension.AVAILABILITY
        assert dp.score_threshold == 0.0
        assert dp.avg_health_score == 0.0
        assert dp.description == ""
        assert dp.created_at > 0

    def test_service_health_trend_report_defaults(self):
        r = ServiceHealthTrendReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_data_points == 0
        assert r.degrading_services == 0
        assert r.avg_health_score == 0.0
        assert r.by_dimension == {}
        assert r.by_direction == {}
        assert r.by_grade == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_trend
# ---------------------------------------------------------------------------


class TestRecordTrend:
    def test_basic(self):
        eng = _engine()
        r = eng.record_trend(
            service_id="SVC-001",
            health_dimension=HealthDimension.LATENCY,
            trend_direction=TrendDirection.IMPROVING,
            health_grade=HealthGrade.EXCELLENT,
            health_score=95.0,
            service="api-gateway",
        )
        assert r.service_id == "SVC-001"
        assert r.health_dimension == HealthDimension.LATENCY
        assert r.trend_direction == TrendDirection.IMPROVING
        assert r.health_grade == HealthGrade.EXCELLENT
        assert r.health_score == 95.0
        assert r.service == "api-gateway"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trend(service_id=f"SVC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------


class TestGetTrend:
    def test_found(self):
        eng = _engine()
        r = eng.record_trend(
            service_id="SVC-001",
            health_grade=HealthGrade.EXCELLENT,
        )
        result = eng.get_trend(r.id)
        assert result is not None
        assert result.health_grade == HealthGrade.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_trend("nonexistent") is None


# ---------------------------------------------------------------------------
# list_trends
# ---------------------------------------------------------------------------


class TestListTrends:
    def test_list_all(self):
        eng = _engine()
        eng.record_trend(service_id="SVC-001")
        eng.record_trend(service_id="SVC-002")
        assert len(eng.list_trends()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_dimension=HealthDimension.LATENCY,
        )
        eng.record_trend(
            service_id="SVC-002",
            health_dimension=HealthDimension.THROUGHPUT,
        )
        results = eng.list_trends(dimension=HealthDimension.LATENCY)
        assert len(results) == 1

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            trend_direction=TrendDirection.IMPROVING,
        )
        eng.record_trend(
            service_id="SVC-002",
            trend_direction=TrendDirection.DEGRADING,
        )
        results = eng.list_trends(direction=TrendDirection.IMPROVING)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_trend(service_id="SVC-001", service="api-gateway")
        eng.record_trend(service_id="SVC-002", service="auth-service")
        results = eng.list_trends(service="api-gateway")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_trend(service_id=f"SVC-{i}")
        assert len(eng.list_trends(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_data_point
# ---------------------------------------------------------------------------


class TestAddDataPoint:
    def test_basic(self):
        eng = _engine()
        dp = eng.add_data_point(
            data_label="latency-check",
            health_dimension=HealthDimension.LATENCY,
            score_threshold=0.8,
            avg_health_score=85.0,
            description="Latency health check",
        )
        assert dp.data_label == "latency-check"
        assert dp.health_dimension == HealthDimension.LATENCY
        assert dp.score_threshold == 0.8
        assert dp.avg_health_score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_data_point(data_label=f"dp-{i}")
        assert len(eng._data_points) == 2


# ---------------------------------------------------------------------------
# analyze_health_trends
# ---------------------------------------------------------------------------


class TestAnalyzeHealthTrends:
    def test_with_data(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_dimension=HealthDimension.LATENCY,
            health_score=90.0,
        )
        eng.record_trend(
            service_id="SVC-002",
            health_dimension=HealthDimension.LATENCY,
            health_score=80.0,
        )
        result = eng.analyze_health_trends()
        assert "latency" in result
        assert result["latency"]["count"] == 2
        assert result["latency"]["avg_health_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_health_trends() == {}


# ---------------------------------------------------------------------------
# identify_degrading_services
# ---------------------------------------------------------------------------


class TestIdentifyDegradingServices:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_grade=HealthGrade.POOR,
            health_score=30.0,
        )
        eng.record_trend(
            service_id="SVC-002",
            health_grade=HealthGrade.EXCELLENT,
        )
        results = eng.identify_degrading_services()
        assert len(results) == 1
        assert results[0]["service_id"] == "SVC-001"

    def test_detects_critical(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_grade=HealthGrade.CRITICAL,
        )
        results = eng.identify_degrading_services()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_degrading_services() == []


# ---------------------------------------------------------------------------
# rank_by_health_score
# ---------------------------------------------------------------------------


class TestRankByHealthScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_trend(service_id="SVC-001", service="api-gw", health_score=90.0)
        eng.record_trend(service_id="SVC-002", service="api-gw", health_score=80.0)
        eng.record_trend(service_id="SVC-003", service="auth", health_score=70.0)
        results = eng.rank_by_health_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_health_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_health_score() == []


# ---------------------------------------------------------------------------
# detect_trend_anomalies
# ---------------------------------------------------------------------------


class TestDetectTrendAnomalies:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_data_point(data_label="d", avg_health_score=s)
        result = eng.detect_trend_anomalies()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_data_point(data_label="d", avg_health_score=s)
        result = eng.detect_trend_anomalies()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trend_anomalies()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_dimension=HealthDimension.LATENCY,
            health_grade=HealthGrade.POOR,
            health_score=30.0,
            service="api-gw",
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceHealthTrendReport)
        assert report.total_records == 1
        assert report.degrading_services == 1
        assert report.avg_health_score == 30.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_trend(service_id="SVC-001")
        eng.add_data_point(data_label="d1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._data_points) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_data_points"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_trend(
            service_id="SVC-001",
            health_dimension=HealthDimension.LATENCY,
            service="api-gw",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_service_ids"] == 1
        assert "latency" in stats["dimension_distribution"]
