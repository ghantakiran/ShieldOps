"""Tests for shieldops.sla.slo_forecast — SLOComplianceForecaster."""

from __future__ import annotations

from shieldops.sla.slo_forecast import (
    ComplianceRisk,
    ForecastHorizon,
    SLIMeasurement,
    SLOComplianceForecaster,
    SLOForecast,
    SLOForecastReport,
    TrendDirection,
)


def _engine(**kw) -> SLOComplianceForecaster:
    return SLOComplianceForecaster(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ForecastHorizon (5)
    def test_horizon_daily(self):
        assert ForecastHorizon.DAILY == "daily"

    def test_horizon_weekly(self):
        assert ForecastHorizon.WEEKLY == "weekly"

    def test_horizon_monthly(self):
        assert ForecastHorizon.MONTHLY == "monthly"

    def test_horizon_quarterly(self):
        assert ForecastHorizon.QUARTERLY == "quarterly"

    def test_horizon_annual(self):
        assert ForecastHorizon.ANNUAL == "annual"

    # ComplianceRisk (5)
    def test_risk_on_track(self):
        assert ComplianceRisk.ON_TRACK == "on_track"

    def test_risk_at_risk(self):
        assert ComplianceRisk.AT_RISK == "at_risk"

    def test_risk_critical(self):
        assert ComplianceRisk.CRITICAL == "critical"

    def test_risk_breached(self):
        assert ComplianceRisk.BREACHED == "breached"

    def test_risk_unknown(self):
        assert ComplianceRisk.UNKNOWN == "unknown"

    # TrendDirection (5)
    def test_trend_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_trend_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trend_degrading(self):
        assert TrendDirection.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert TrendDirection.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_sli_measurement_defaults(self):
        m = SLIMeasurement()
        assert m.id
        assert m.service == ""
        assert m.slo_name == ""
        assert m.target_pct == 99.9
        assert m.current_pct == 100.0
        assert m.horizon == ForecastHorizon.MONTHLY
        assert m.period_elapsed_pct == 0.0
        assert m.created_at > 0

    def test_slo_forecast_defaults(self):
        f = SLOForecast()
        assert f.id
        assert f.service == ""
        assert f.slo_name == ""
        assert f.target_pct == 99.9
        assert f.forecasted_pct == 100.0
        assert f.risk == ComplianceRisk.UNKNOWN
        assert f.trend == TrendDirection.INSUFFICIENT_DATA
        assert f.probability_of_breach_pct == 0.0
        assert f.created_at > 0

    def test_slo_forecast_report_defaults(self):
        r = SLOForecastReport()
        assert r.total_measurements == 0
        assert r.total_forecasts == 0
        assert r.at_risk_count == 0
        assert r.breached_count == 0
        assert r.by_risk == {}
        assert r.by_trend == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_measurement
# ---------------------------------------------------------------------------


class TestRecordMeasurement:
    def test_basic(self):
        eng = _engine()
        m = eng.record_measurement(service="api-gw", slo_name="availability")
        assert m.service == "api-gw"
        assert m.slo_name == "availability"
        assert m.target_pct == 99.9
        assert m.current_pct == 100.0

    def test_with_params(self):
        eng = _engine()
        m = eng.record_measurement(
            service="payment-svc",
            slo_name="latency-p99",
            target_pct=99.5,
            current_pct=99.2,
            horizon=ForecastHorizon.WEEKLY,
            period_elapsed_pct=60.0,
        )
        assert m.target_pct == 99.5
        assert m.current_pct == 99.2
        assert m.horizon == ForecastHorizon.WEEKLY
        assert m.period_elapsed_pct == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_measurement(service=f"svc-{i}", slo_name="avail")
        assert len(eng._measurements) == 3


# ---------------------------------------------------------------------------
# get_measurement
# ---------------------------------------------------------------------------


class TestGetMeasurement:
    def test_found(self):
        eng = _engine()
        m = eng.record_measurement(service="api-gw", slo_name="availability")
        result = eng.get_measurement(m.id)
        assert result is not None
        assert result.service == "api-gw"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_measurement("nonexistent") is None


# ---------------------------------------------------------------------------
# list_measurements
# ---------------------------------------------------------------------------


class TestListMeasurements:
    def test_list_all(self):
        eng = _engine()
        eng.record_measurement(service="api-gw", slo_name="availability")
        eng.record_measurement(service="payment-svc", slo_name="latency")
        assert len(eng.list_measurements()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_measurement(service="api-gw", slo_name="availability")
        eng.record_measurement(service="payment-svc", slo_name="latency")
        results = eng.list_measurements(service="api-gw")
        assert len(results) == 1
        assert results[0].service == "api-gw"

    def test_filter_by_slo_name(self):
        eng = _engine()
        eng.record_measurement(service="api-gw", slo_name="availability")
        eng.record_measurement(service="api-gw", slo_name="latency")
        results = eng.list_measurements(slo_name="latency")
        assert len(results) == 1
        assert results[0].slo_name == "latency"


# ---------------------------------------------------------------------------
# forecast_compliance
# ---------------------------------------------------------------------------


class TestForecastCompliance:
    def test_no_measurements_returns_unknown(self):
        eng = _engine()
        fc = eng.forecast_compliance(service="api-gw", slo_name="availability")
        assert fc.risk == ComplianceRisk.UNKNOWN
        assert fc.trend == TrendDirection.INSUFFICIENT_DATA

    def test_breached_slo(self):
        eng = _engine()
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.9,
            current_pct=99.5,
            period_elapsed_pct=80.0,
        )
        fc = eng.forecast_compliance(service="api-gw", slo_name="availability")
        assert fc.risk == ComplianceRisk.BREACHED
        assert fc.service == "api-gw"

    def test_on_track_slo(self):
        eng = _engine()
        # margin must be >= 1.0 for ON_TRACK: current - target >= 1.0
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.0,
            current_pct=100.0,
            period_elapsed_pct=50.0,
        )
        fc = eng.forecast_compliance(service="api-gw", slo_name="availability")
        assert fc.risk == ComplianceRisk.ON_TRACK


# ---------------------------------------------------------------------------
# assess_risk
# ---------------------------------------------------------------------------


class TestAssessRisk:
    def test_with_measurements(self):
        eng = _engine()
        # margin must be >= 1.0 for on_track: 100.0 - 99.0 = 1.0
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.0,
            current_pct=100.0,
            period_elapsed_pct=50.0,
        )
        result = eng.assess_risk(service="api-gw", slo_name="availability")
        assert result["risk"] == "on_track"
        assert result["current_pct"] == 100.0
        assert result["target_pct"] == 99.0

    def test_no_measurements(self):
        eng = _engine()
        result = eng.assess_risk(service="api-gw", slo_name="availability")
        assert result["risk"] == "unknown"


# ---------------------------------------------------------------------------
# detect_trend
# ---------------------------------------------------------------------------


class TestDetectTrend:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.9)
        trend = eng.detect_trend(service="svc", slo_name="avail")
        assert trend == TrendDirection.INSUFFICIENT_DATA

    def test_improving(self):
        eng = _engine()
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.0)
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.5)
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.9)
        trend = eng.detect_trend(service="svc", slo_name="avail")
        assert trend == TrendDirection.IMPROVING

    def test_degrading(self):
        eng = _engine()
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.9)
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.5)
        eng.record_measurement(service="svc", slo_name="avail", current_pct=99.0)
        trend = eng.detect_trend(service="svc", slo_name="avail")
        assert trend == TrendDirection.DEGRADING


# ---------------------------------------------------------------------------
# identify_at_risk_slos
# ---------------------------------------------------------------------------


class TestIdentifyAtRiskSLOs:
    def test_has_at_risk(self):
        eng = _engine()
        # breached: current < target
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.9,
            current_pct=99.5,
        )
        # on_track: margin >= 1.0 (100.0 - 99.0 = 1.0)
        eng.record_measurement(
            service="payment-svc",
            slo_name="latency",
            target_pct=99.0,
            current_pct=100.0,
        )
        results = eng.identify_at_risk_slos()
        assert len(results) == 1
        assert results[0]["service"] == "api-gw"
        assert results[0]["risk"] == "breached"

    def test_none_at_risk(self):
        eng = _engine()
        # margin >= 1.0 -> ON_TRACK
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.0,
            current_pct=100.0,
        )
        assert len(eng.identify_at_risk_slos()) == 0


# ---------------------------------------------------------------------------
# project_end_of_period
# ---------------------------------------------------------------------------


class TestProjectEndOfPeriod:
    def test_with_measurement(self):
        eng = _engine()
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.9,
            current_pct=99.95,
            period_elapsed_pct=50.0,
        )
        result = eng.project_end_of_period(service="api-gw", slo_name="availability")
        assert result["service"] == "api-gw"
        assert result["current_pct"] == 99.95
        assert result["target_pct"] == 99.9
        assert "projected_pct" in result
        assert "risk" in result
        assert "trend" in result

    def test_no_measurements(self):
        eng = _engine()
        result = eng.project_end_of_period(service="api-gw", slo_name="availability")
        assert result["projected_pct"] == 0.0
        assert result["risk"] == "unknown"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_measurement(
            service="api-gw",
            slo_name="availability",
            target_pct=99.9,
            current_pct=99.5,
            period_elapsed_pct=80.0,
        )
        eng.forecast_compliance(service="api-gw", slo_name="availability")
        eng.record_measurement(
            service="payment-svc",
            slo_name="latency",
            target_pct=99.0,
            current_pct=99.99,
            period_elapsed_pct=50.0,
        )
        eng.forecast_compliance(service="payment-svc", slo_name="latency")
        report = eng.generate_report()
        assert isinstance(report, SLOForecastReport)
        assert report.total_measurements == 2
        assert report.total_forecasts == 2
        assert report.breached_count >= 1
        assert len(report.by_risk) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_measurements == 0
        assert report.total_forecasts == 0
        assert "All SLOs on track" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_measurement(service="api-gw", slo_name="availability")
        eng.forecast_compliance(service="api-gw", slo_name="availability")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._measurements) == 0
        assert len(eng._forecasts) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_measurements"] == 0
        assert stats["total_forecasts"] == 0
        assert stats["risk_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_measurement(service="api-gw", slo_name="availability")
        eng.forecast_compliance(service="api-gw", slo_name="availability")
        stats = eng.get_stats()
        assert stats["total_measurements"] == 1
        assert stats["total_forecasts"] == 1
        assert stats["risk_threshold_pct"] == 95.0
        assert stats["unique_services"] == 1
        assert len(stats["risk_distribution"]) > 0
