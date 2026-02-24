"""Tests for shieldops.analytics.capacity_forecast_engine — CapacityForecastEngine."""

from __future__ import annotations

from shieldops.analytics.capacity_forecast_engine import (
    CapacityForecast,
    CapacityForecastEngine,
    CapacityRisk,
    ForecastMethod,
    ForecastReport,
    ResourceDimension,
    UsageDataPoint,
)


def _engine(**kw) -> CapacityForecastEngine:
    return CapacityForecastEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ForecastMethod (5)
    def test_method_linear(self):
        assert ForecastMethod.LINEAR == "linear"

    def test_method_exponential(self):
        assert ForecastMethod.EXPONENTIAL == "exponential"

    def test_method_seasonal(self):
        assert ForecastMethod.SEASONAL == "seasonal"

    def test_method_holt_winters(self):
        assert ForecastMethod.HOLT_WINTERS == "holt_winters"

    def test_method_ensemble(self):
        assert ForecastMethod.ENSEMBLE == "ensemble"

    # CapacityRisk (5)
    def test_risk_surplus(self):
        assert CapacityRisk.SURPLUS == "surplus"

    def test_risk_adequate(self):
        assert CapacityRisk.ADEQUATE == "adequate"

    def test_risk_tight(self):
        assert CapacityRisk.TIGHT == "tight"

    def test_risk_critical(self):
        assert CapacityRisk.CRITICAL == "critical"

    def test_risk_exhausted(self):
        assert CapacityRisk.EXHAUSTED == "exhausted"

    # ResourceDimension (5)
    def test_dimension_cpu(self):
        assert ResourceDimension.CPU == "cpu"

    def test_dimension_memory(self):
        assert ResourceDimension.MEMORY == "memory"

    def test_dimension_disk(self):
        assert ResourceDimension.DISK == "disk"

    def test_dimension_network(self):
        assert ResourceDimension.NETWORK == "network"

    def test_dimension_connections(self):
        assert ResourceDimension.CONNECTIONS == "connections"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_usage_data_point_defaults(self):
        dp = UsageDataPoint()
        assert dp.id
        assert dp.service_name == ""
        assert dp.dimension == ResourceDimension.CPU
        assert dp.value == 0.0
        assert dp.capacity_limit == 100.0
        assert dp.utilization_pct == 0.0
        assert dp.recorded_at > 0
        assert dp.created_at > 0

    def test_capacity_forecast_defaults(self):
        fc = CapacityForecast()
        assert fc.id
        assert fc.service_name == ""
        assert fc.dimension == ResourceDimension.CPU
        assert fc.method == ForecastMethod.LINEAR
        assert fc.current_utilization_pct == 0.0
        assert fc.forecast_utilization_pct == 0.0
        assert fc.days_to_exhaustion == 0.0
        assert fc.risk == CapacityRisk.ADEQUATE
        assert fc.confidence == 0.0
        assert fc.created_at > 0

    def test_forecast_report_defaults(self):
        r = ForecastReport()
        assert r.total_services == 0
        assert r.total_data_points == 0
        assert r.forecasts_generated == 0
        assert r.by_risk == {}
        assert r.by_dimension == {}
        assert r.urgent_services == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# ingest_usage
# ---------------------------------------------------------------------------


class TestIngestUsage:
    def test_basic_ingest(self):
        eng = _engine()
        dp = eng.ingest_usage(
            service_name="api-gw",
            dimension=ResourceDimension.CPU,
            value=70.0,
            capacity_limit=100.0,
        )
        assert dp.service_name == "api-gw"
        assert dp.dimension == ResourceDimension.CPU
        assert dp.value == 70.0
        assert dp.utilization_pct == 70.0

    def test_utilization_calculation(self):
        eng = _engine()
        dp = eng.ingest_usage(
            service_name="db",
            dimension=ResourceDimension.MEMORY,
            value=6.0,
            capacity_limit=8.0,
        )
        assert dp.utilization_pct == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_data_points=3)
        for i in range(5):
            eng.ingest_usage(service_name=f"svc-{i}", value=float(i))
        assert len(eng._items) == 3

    def test_zero_capacity_limit(self):
        eng = _engine()
        dp = eng.ingest_usage(
            service_name="empty",
            value=50.0,
            capacity_limit=0.0,
        )
        assert dp.utilization_pct == 0.0


# ---------------------------------------------------------------------------
# get_data_point
# ---------------------------------------------------------------------------


class TestGetDataPoint:
    def test_found(self):
        eng = _engine()
        dp = eng.ingest_usage(service_name="api")
        assert eng.get_data_point(dp.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_data_point("nonexistent") is None


# ---------------------------------------------------------------------------
# list_usage
# ---------------------------------------------------------------------------


class TestListUsage:
    def test_list_all(self):
        eng = _engine()
        eng.ingest_usage(service_name="a")
        eng.ingest_usage(service_name="b")
        assert len(eng.list_usage()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.ingest_usage(service_name="a")
        eng.ingest_usage(service_name="b")
        results = eng.list_usage(service_name="a")
        assert len(results) == 1
        assert results[0].service_name == "a"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.ingest_usage(
            service_name="a",
            dimension=ResourceDimension.CPU,
        )
        eng.ingest_usage(
            service_name="b",
            dimension=ResourceDimension.DISK,
        )
        results = eng.list_usage(dimension=ResourceDimension.CPU)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# generate_forecast
# ---------------------------------------------------------------------------


class TestGenerateForecast:
    def test_linear_forecast(self):
        eng = _engine()
        # Simulate rising usage
        for i in range(5):
            eng.ingest_usage(
                service_name="api",
                dimension=ResourceDimension.CPU,
                value=40.0 + i * 5,
                capacity_limit=100.0,
            )
        fc = eng.generate_forecast("api", ResourceDimension.CPU)
        assert fc.service_name == "api"
        assert fc.dimension == ResourceDimension.CPU
        assert fc.current_utilization_pct >= 60.0
        assert fc.forecast_utilization_pct >= fc.current_utilization_pct
        assert fc.confidence > 0

    def test_exponential_method(self):
        eng = _engine()
        for i in range(5):
            eng.ingest_usage(
                service_name="db",
                dimension=ResourceDimension.MEMORY,
                value=50.0 + i * 3,
                capacity_limit=100.0,
            )
        fc = eng.generate_forecast(
            "db",
            ResourceDimension.MEMORY,
            method=ForecastMethod.EXPONENTIAL,
        )
        assert fc.method == ForecastMethod.EXPONENTIAL

    def test_no_data_forecast(self):
        eng = _engine()
        fc = eng.generate_forecast("missing", ResourceDimension.CPU)
        assert fc.current_utilization_pct == 0.0
        assert fc.forecast_utilization_pct == 0.0

    def test_single_data_point(self):
        eng = _engine()
        eng.ingest_usage(
            service_name="solo",
            dimension=ResourceDimension.DISK,
            value=50.0,
            capacity_limit=100.0,
        )
        fc = eng.generate_forecast("solo", ResourceDimension.DISK)
        assert fc.current_utilization_pct == 50.0


# ---------------------------------------------------------------------------
# detect_capacity_risk
# ---------------------------------------------------------------------------


class TestDetectCapacityRisk:
    def test_high_utilization_detected(self):
        eng = _engine()
        for i in range(3):
            eng.ingest_usage(
                service_name="hot-svc",
                dimension=ResourceDimension.CPU,
                value=80.0 + i * 5,
                capacity_limit=100.0,
            )
        risks = eng.detect_capacity_risk()
        assert len(risks) >= 1
        assert risks[0]["service_name"] == "hot-svc"

    def test_low_utilization_not_flagged(self):
        eng = _engine()
        eng.ingest_usage(
            service_name="cold-svc",
            dimension=ResourceDimension.CPU,
            value=10.0,
            capacity_limit=100.0,
        )
        risks = eng.detect_capacity_risk()
        cold_risks = [r for r in risks if r["service_name"] == "cold-svc"]
        assert len(cold_risks) == 0


# ---------------------------------------------------------------------------
# calculate_days_to_exhaustion
# ---------------------------------------------------------------------------


class TestCalculateDaysToExhaustion:
    def test_rising_trend(self):
        eng = _engine()
        for i in range(5):
            eng.ingest_usage(
                service_name="api",
                dimension=ResourceDimension.CPU,
                value=50.0 + i * 10,
                capacity_limit=100.0,
            )
        days = eng.calculate_days_to_exhaustion("api", ResourceDimension.CPU)
        assert days > 0
        assert days < 999.0

    def test_flat_trend(self):
        eng = _engine()
        for _ in range(5):
            eng.ingest_usage(
                service_name="stable",
                dimension=ResourceDimension.CPU,
                value=30.0,
                capacity_limit=100.0,
            )
        days = eng.calculate_days_to_exhaustion("stable", ResourceDimension.CPU)
        assert days == 999.0


# ---------------------------------------------------------------------------
# identify_trending_services
# ---------------------------------------------------------------------------


class TestIdentifyTrendingServices:
    def test_upward_trend(self):
        eng = _engine()
        for i in range(6):
            eng.ingest_usage(
                service_name="growing",
                dimension=ResourceDimension.MEMORY,
                value=20.0 + i * 10,
                capacity_limit=100.0,
            )
        trending = eng.identify_trending_services()
        assert len(trending) >= 1
        assert trending[0]["service_name"] == "growing"
        assert trending[0]["trend_increase_pct"] > 0

    def test_flat_not_trending(self):
        eng = _engine()
        for _ in range(6):
            eng.ingest_usage(
                service_name="flat",
                dimension=ResourceDimension.CPU,
                value=50.0,
                capacity_limit=100.0,
            )
        trending = eng.identify_trending_services()
        flat_entries = [t for t in trending if t["service_name"] == "flat"]
        assert len(flat_entries) == 0


# ---------------------------------------------------------------------------
# plan_headroom
# ---------------------------------------------------------------------------


class TestPlanHeadroom:
    def test_over_target(self):
        eng = _engine()
        for i in range(3):
            eng.ingest_usage(
                service_name="hot",
                dimension=ResourceDimension.CPU,
                value=75.0 + i * 5,
                capacity_limit=100.0,
            )
        plans = eng.plan_headroom(target_utilization_pct=70.0)
        assert len(plans) >= 1
        assert plans[0]["service_name"] == "hot"
        assert plans[0]["action"] == "scale_up"

    def test_under_target(self):
        eng = _engine()
        eng.ingest_usage(
            service_name="cold",
            dimension=ResourceDimension.CPU,
            value=20.0,
            capacity_limit=100.0,
        )
        plans = eng.plan_headroom(target_utilization_pct=70.0)
        cold_plans = [p for p in plans if p["service_name"] == "cold"]
        assert len(cold_plans) == 0


# ---------------------------------------------------------------------------
# generate_forecast_report
# ---------------------------------------------------------------------------


class TestGenerateForecastReport:
    def test_basic_report(self):
        eng = _engine()
        for i in range(3):
            eng.ingest_usage(
                service_name="api",
                dimension=ResourceDimension.CPU,
                value=60.0 + i * 10,
                capacity_limit=100.0,
            )
        eng.generate_forecast("api", ResourceDimension.CPU)
        report = eng.generate_forecast_report()
        assert isinstance(report, ForecastReport)
        assert report.total_services >= 1
        assert report.total_data_points == 3
        assert report.by_dimension["cpu"] == 3

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_forecast_report()
        assert report.total_data_points == 0
        assert len(report.recommendations) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.ingest_usage(service_name="a")
        eng.generate_forecast("a", ResourceDimension.CPU)
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._forecasts) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_data_points"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["unique_services"] == 0
        assert stats["dimensions"] == []

    def test_populated(self):
        eng = _engine()
        eng.ingest_usage(
            service_name="api",
            dimension=ResourceDimension.CPU,
        )
        eng.ingest_usage(
            service_name="db",
            dimension=ResourceDimension.MEMORY,
        )
        stats = eng.get_stats()
        assert stats["total_data_points"] == 2
        assert stats["unique_services"] == 2
        assert "cpu" in stats["dimensions"]
        assert "memory" in stats["dimensions"]
