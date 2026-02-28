"""Tests for shieldops.incidents.trend_forecaster — IncidentTrendForecaster."""

from __future__ import annotations

from shieldops.incidents.trend_forecaster import (
    ForecastConfidence,
    ForecastDataPoint,
    IncidentCategory,
    IncidentTrendForecaster,
    TrendDirection,
    TrendForecasterReport,
    TrendRecord,
)


def _engine(**kw) -> IncidentTrendForecaster:
    return IncidentTrendForecaster(**kw)


class TestEnums:
    def test_direction_increasing(self):
        assert TrendDirection.INCREASING == "increasing"

    def test_direction_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_direction_decreasing(self):
        assert TrendDirection.DECREASING == "decreasing"

    def test_direction_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_direction_insufficient_data(self):
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"

    def test_confidence_high(self):
        assert ForecastConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert ForecastConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ForecastConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ForecastConfidence.SPECULATIVE == "speculative"

    def test_confidence_no_data(self):
        assert ForecastConfidence.NO_DATA == "no_data"

    def test_category_infrastructure(self):
        assert IncidentCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_application(self):
        assert IncidentCategory.APPLICATION == "application"

    def test_category_security(self):
        assert IncidentCategory.SECURITY == "security"

    def test_category_network(self):
        assert IncidentCategory.NETWORK == "network"

    def test_category_database(self):
        assert IncidentCategory.DATABASE == "database"


class TestModels:
    def test_trend_record_defaults(self):
        r = TrendRecord()
        assert r.id
        assert r.category == IncidentCategory.INFRASTRUCTURE
        assert r.direction == TrendDirection.STABLE
        assert r.confidence == ForecastConfidence.MODERATE
        assert r.incident_count == 0
        assert r.growth_rate_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_forecast_data_point_defaults(self):
        p = ForecastDataPoint()
        assert p.id
        assert p.category == IncidentCategory.INFRASTRUCTURE
        assert p.period_label == ""
        assert p.incident_count == 0
        assert p.forecast_count == 0
        assert p.notes == ""
        assert p.created_at > 0

    def test_report_defaults(self):
        r = TrendForecasterReport()
        assert r.total_trends == 0
        assert r.total_data_points == 0
        assert r.avg_growth_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_direction == {}
        assert r.rising_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordTrend:
    def test_basic(self):
        eng = _engine()
        r = eng.record_trend(category=IncidentCategory.SECURITY, growth_rate_pct=15.0)
        assert r.category == IncidentCategory.SECURITY
        assert r.growth_rate_pct == 15.0

    def test_with_direction(self):
        eng = _engine()
        r = eng.record_trend(direction=TrendDirection.INCREASING)
        assert r.direction == TrendDirection.INCREASING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trend(incident_count=i)
        assert len(eng._records) == 3


class TestGetTrend:
    def test_found(self):
        eng = _engine()
        r = eng.record_trend()
        assert eng.get_trend(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_trend("nonexistent") is None


class TestListTrends:
    def test_list_all(self):
        eng = _engine()
        eng.record_trend(category=IncidentCategory.INFRASTRUCTURE)
        eng.record_trend(category=IncidentCategory.SECURITY)
        assert len(eng.list_trends()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_trend(category=IncidentCategory.INFRASTRUCTURE)
        eng.record_trend(category=IncidentCategory.SECURITY)
        results = eng.list_trends(category=IncidentCategory.SECURITY)
        assert len(results) == 1

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_trend(direction=TrendDirection.INCREASING)
        eng.record_trend(direction=TrendDirection.STABLE)
        results = eng.list_trends(direction=TrendDirection.INCREASING)
        assert len(results) == 1


class TestAddDataPoint:
    def test_basic(self):
        eng = _engine()
        p = eng.add_data_point(
            category=IncidentCategory.DATABASE,
            period_label="2026-W01",
            incident_count=5,
            forecast_count=7,
        )
        assert p.category == IncidentCategory.DATABASE
        assert p.period_label == "2026-W01"
        assert p.incident_count == 5
        assert p.forecast_count == 7

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_data_point(period_label=f"W{i:02d}")
        assert len(eng._data_points) == 2


class TestAnalyzeTrendByCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_trend(
            category=IncidentCategory.NETWORK,
            direction=TrendDirection.INCREASING,
            growth_rate_pct=10.0,
        )
        eng.record_trend(
            category=IncidentCategory.NETWORK,
            direction=TrendDirection.STABLE,
            growth_rate_pct=5.0,
        )
        result = eng.analyze_trend_by_category(IncidentCategory.NETWORK)
        assert result["category"] == "network"
        assert result["total"] == 2
        assert result["avg_growth_rate_pct"] == 7.5

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_trend_by_category(IncidentCategory.DATABASE)
        assert result["status"] == "no_data"


class TestIdentifyRisingTrends:
    def test_with_rising(self):
        eng = _engine()
        eng.record_trend(direction=TrendDirection.INCREASING, growth_rate_pct=25.0)
        eng.record_trend(direction=TrendDirection.STABLE, growth_rate_pct=2.0)
        results = eng.identify_rising_trends()
        assert len(results) == 1
        assert results[0]["growth_rate_pct"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_rising_trends() == []


class TestRankByGrowthRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_trend(growth_rate_pct=5.0)
        eng.record_trend(growth_rate_pct=30.0)
        results = eng.rank_by_growth_rate()
        assert results[0]["growth_rate_pct"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_growth_rate() == []


class TestDetectTrendAnomalies:
    def test_with_anomaly(self):
        eng = _engine()
        for i in range(5):
            eng.record_trend(
                category=IncidentCategory.APPLICATION,
                growth_rate_pct=float(5 + i * 5),
            )
        results = eng.detect_trend_anomalies()
        assert len(results) == 1
        assert results[0]["category"] == "application"
        assert results[0]["anomaly_type"] == "spike"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_trend_anomalies() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_trend(direction=TrendDirection.INCREASING, growth_rate_pct=25.0)
        eng.record_trend(direction=TrendDirection.STABLE, growth_rate_pct=3.0)
        eng.add_data_point(period_label="W01")
        report = eng.generate_report()
        assert report.total_trends == 2
        assert report.total_data_points == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_trends == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_trend()
        eng.add_data_point()
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._data_points) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_trends"] == 0
        assert stats["total_data_points"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_trend(category=IncidentCategory.SECURITY)
        eng.record_trend(category=IncidentCategory.NETWORK)
        eng.add_data_point()
        stats = eng.get_stats()
        assert stats["total_trends"] == 2
        assert stats["total_data_points"] == 1
        assert stats["unique_categories"] == 2
