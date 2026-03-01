"""Tests for shieldops.billing.cost_trend — CostTrendForecaster."""

from __future__ import annotations

from shieldops.billing.cost_trend import (
    CostCategory,
    CostForecast,
    CostTrendForecaster,
    CostTrendRecord,
    CostTrendReport,
    ForecastConfidence,
    TrendDirection,
)


def _engine(**kw) -> CostTrendForecaster:
    return CostTrendForecaster(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_direction_increasing(self):
        assert TrendDirection.INCREASING == "increasing"

    def test_direction_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_direction_decreasing(self):
        assert TrendDirection.DECREASING == "decreasing"

    def test_direction_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_direction_seasonal(self):
        assert TrendDirection.SEASONAL == "seasonal"

    def test_category_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_category_network(self):
        assert CostCategory.NETWORK == "network"

    def test_category_database(self):
        assert CostCategory.DATABASE == "database"

    def test_category_third_party(self):
        assert CostCategory.THIRD_PARTY == "third_party"

    def test_confidence_high(self):
        assert ForecastConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert ForecastConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ForecastConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ForecastConfidence.SPECULATIVE == "speculative"

    def test_confidence_insufficient_data(self):
        assert ForecastConfidence.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_trend_record_defaults(self):
        r = CostTrendRecord()
        assert r.id
        assert r.service == ""
        assert r.cost_amount == 0.0
        assert r.direction == TrendDirection.STABLE
        assert r.category == CostCategory.COMPUTE
        assert r.confidence == ForecastConfidence.INSUFFICIENT_DATA
        assert r.period == ""
        assert r.created_at > 0

    def test_cost_forecast_defaults(self):
        f = CostForecast()
        assert f.id
        assert f.service == ""
        assert f.projected_cost == 0.0
        assert f.confidence == ForecastConfidence.INSUFFICIENT_DATA
        assert f.period == ""
        assert f.growth_rate_pct == 0.0
        assert f.created_at > 0

    def test_report_defaults(self):
        r = CostTrendReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_forecasts == 0
        assert r.avg_cost == 0.0
        assert r.avg_growth_rate_pct == 0.0
        assert r.by_direction == {}
        assert r.by_category == {}
        assert r.high_growth_services == []
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
            service="api-gateway",
            cost_amount=5000.0,
            direction=TrendDirection.INCREASING,
            category=CostCategory.COMPUTE,
            confidence=ForecastConfidence.HIGH,
        )
        assert r.service == "api-gateway"
        assert r.cost_amount == 5000.0
        assert r.direction == TrendDirection.INCREASING
        assert r.category == CostCategory.COMPUTE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trend(service=f"svc-{i}", cost_amount=100.0)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------


class TestGetTrend:
    def test_found(self):
        eng = _engine()
        r = eng.record_trend(service="worker", cost_amount=200.0)
        result = eng.get_trend(r.id)
        assert result is not None
        assert result.cost_amount == 200.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_trend("nonexistent") is None


# ---------------------------------------------------------------------------
# list_trends
# ---------------------------------------------------------------------------


class TestListTrends:
    def test_list_all(self):
        eng = _engine()
        eng.record_trend(service="a", cost_amount=100.0)
        eng.record_trend(service="b", cost_amount=200.0)
        assert len(eng.list_trends()) == 2

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_trend(service="a", cost_amount=100.0, direction=TrendDirection.INCREASING)
        eng.record_trend(service="b", cost_amount=200.0, direction=TrendDirection.STABLE)
        results = eng.list_trends(direction=TrendDirection.INCREASING)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_trend(service="a", cost_amount=100.0, category=CostCategory.COMPUTE)
        eng.record_trend(service="b", cost_amount=200.0, category=CostCategory.STORAGE)
        results = eng.list_trends(category=CostCategory.STORAGE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_trend(service="api", cost_amount=100.0)
        eng.record_trend(service="worker", cost_amount=200.0)
        results = eng.list_trends(service="api")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_trend(service=f"svc-{i}", cost_amount=100.0)
        assert len(eng.list_trends(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_forecast
# ---------------------------------------------------------------------------


class TestAddForecast:
    def test_basic(self):
        eng = _engine()
        f = eng.add_forecast(
            service="api-gateway",
            projected_cost=8000.0,
            confidence=ForecastConfidence.HIGH,
            period="2026-Q1",
            growth_rate_pct=25.0,
        )
        assert f.service == "api-gateway"
        assert f.projected_cost == 8000.0
        assert f.growth_rate_pct == 25.0
        assert f.confidence == ForecastConfidence.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_forecast(service=f"svc-{i}", projected_cost=100.0)
        assert len(eng._forecasts) == 2


# ---------------------------------------------------------------------------
# analyze_cost_by_category
# ---------------------------------------------------------------------------


class TestAnalyzeCostByCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_trend(service="a", cost_amount=200.0, category=CostCategory.COMPUTE)
        eng.record_trend(service="b", cost_amount=400.0, category=CostCategory.COMPUTE)
        result = eng.analyze_cost_by_category()
        assert "compute" in result
        assert result["compute"]["count"] == 2
        assert result["compute"]["avg_cost"] == 300.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_cost_by_category() == {}


# ---------------------------------------------------------------------------
# identify_high_growth_services
# ---------------------------------------------------------------------------


class TestIdentifyHighGrowthServices:
    def test_detects_high_growth(self):
        eng = _engine(max_growth_rate_pct=20.0)
        eng.add_forecast(service="api", projected_cost=1000.0, growth_rate_pct=35.0)
        eng.add_forecast(service="worker", projected_cost=500.0, growth_rate_pct=5.0)
        results = eng.identify_high_growth_services()
        assert len(results) == 1
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_growth_services() == []


# ---------------------------------------------------------------------------
# rank_by_cost
# ---------------------------------------------------------------------------


class TestRankByCost:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_trend(service="api", cost_amount=5000.0)
        eng.record_trend(service="worker", cost_amount=1000.0)
        results = eng.rank_by_cost()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_cost"] == 5000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost() == []


# ---------------------------------------------------------------------------
# detect_cost_trends
# ---------------------------------------------------------------------------


class TestDetectCostTrends:
    def test_stable(self):
        eng = _engine()
        for cost in [100.0, 100.0, 100.0, 100.0]:
            eng.record_trend(service="svc", cost_amount=cost)
        result = eng.detect_cost_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for cost in [50.0, 50.0, 200.0, 200.0]:
            eng.record_trend(service="svc", cost_amount=cost)
        result = eng.detect_cost_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_cost_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_growth_rate_pct=20.0)
        eng.record_trend(
            service="api",
            cost_amount=5000.0,
            direction=TrendDirection.VOLATILE,
        )
        eng.add_forecast(service="api", projected_cost=7000.0, growth_rate_pct=40.0)
        report = eng.generate_report()
        assert isinstance(report, CostTrendReport)
        assert report.total_records == 1
        assert report.total_forecasts == 1
        assert len(report.high_growth_services) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "expected" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_trend(service="api", cost_amount=100.0)
        eng.add_forecast(service="api", projected_cost=120.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._forecasts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["direction_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_trend(
            service="api",
            cost_amount=100.0,
            direction=TrendDirection.INCREASING,
            category=CostCategory.COMPUTE,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_categories"] == 1
        assert "increasing" in stats["direction_distribution"]
