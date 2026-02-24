"""Tests for shieldops.sla.burn_predictor — SLOBurnRatePredictor."""

from __future__ import annotations

import time

from shieldops.sla.burn_predictor import (
    AlertSensitivity,
    BurnPrediction,
    BurnSeverity,
    PredictionHorizon,
    SLOBurnRatePredictor,
    SLOTarget,
    ViolationForecast,
)


def _engine(**kw) -> SLOBurnRatePredictor:
    return SLOBurnRatePredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_severity_safe(self):
        assert BurnSeverity.SAFE == "safe"

    def test_severity_watch(self):
        assert BurnSeverity.WATCH == "watch"

    def test_severity_warning(self):
        assert BurnSeverity.WARNING == "warning"

    def test_severity_danger(self):
        assert BurnSeverity.DANGER == "danger"

    def test_severity_breach(self):
        assert BurnSeverity.BREACH == "breach"

    def test_horizon_one_hour(self):
        assert PredictionHorizon.ONE_HOUR == "one_hour"

    def test_horizon_six_hours(self):
        assert PredictionHorizon.SIX_HOURS == "six_hours"

    def test_horizon_one_day(self):
        assert PredictionHorizon.ONE_DAY == "one_day"

    def test_horizon_one_week(self):
        assert PredictionHorizon.ONE_WEEK == "one_week"

    def test_horizon_one_month(self):
        assert PredictionHorizon.ONE_MONTH == "one_month"

    def test_sensitivity_relaxed(self):
        assert AlertSensitivity.RELAXED == "relaxed"

    def test_sensitivity_normal(self):
        assert AlertSensitivity.NORMAL == "normal"

    def test_sensitivity_elevated(self):
        assert AlertSensitivity.ELEVATED == "elevated"

    def test_sensitivity_aggressive(self):
        assert AlertSensitivity.AGGRESSIVE == "aggressive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_slo_defaults(self):
        s = SLOTarget()
        assert s.id
        assert s.target_pct == 99.9
        assert s.current_burn_rate == 0.0

    def test_prediction_defaults(self):
        p = BurnPrediction()
        assert p.severity == BurnSeverity.SAFE

    def test_forecast_defaults(self):
        f = ViolationForecast()
        assert f.severity == BurnSeverity.SAFE


# ---------------------------------------------------------------------------
# register_slo
# ---------------------------------------------------------------------------


class TestRegisterSLO:
    def test_basic_register(self):
        eng = _engine()
        slo = eng.register_slo("api-latency", service="gateway")
        assert slo.name == "api-latency"
        assert slo.error_budget_total > 0

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.register_slo("slo1")
        s2 = eng.register_slo("slo2")
        assert s1.id != s2.id

    def test_eviction_at_max(self):
        eng = _engine(max_slos=3)
        for i in range(5):
            eng.register_slo(f"slo{i}")
        assert len(eng._slos) == 3

    def test_custom_target(self):
        eng = _engine()
        slo = eng.register_slo("strict", target_pct=99.99)
        assert slo.target_pct == 99.99


# ---------------------------------------------------------------------------
# get / list SLOs
# ---------------------------------------------------------------------------


class TestGetSLO:
    def test_found(self):
        eng = _engine()
        slo = eng.register_slo("test")
        assert eng.get_slo(slo.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_slo("nonexistent") is None


class TestListSLOs:
    def test_list_all(self):
        eng = _engine()
        eng.register_slo("slo1")
        eng.register_slo("slo2")
        assert len(eng.list_slos()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_slo("slo1", service="gw")
        eng.register_slo("slo2", service="api")
        results = eng.list_slos(service="gw")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_error_event
# ---------------------------------------------------------------------------


class TestRecordErrorEvent:
    def test_basic_event(self):
        eng = _engine()
        slo = eng.register_slo("test")
        result = eng.record_error_event(slo.id, error_count=5, total_count=100)
        assert result["burn_rate"] > 0

    def test_budget_consumed(self):
        eng = _engine()
        slo = eng.register_slo("test")
        initial_budget = slo.error_budget_remaining
        eng.record_error_event(slo.id, error_count=10, total_count=100)
        assert slo.error_budget_remaining < initial_budget

    def test_invalid_slo(self):
        eng = _engine()
        result = eng.record_error_event("bad_id")
        assert result.get("error") == "slo_not_found"


# ---------------------------------------------------------------------------
# predict_burn
# ---------------------------------------------------------------------------


class TestPredictBurn:
    def test_safe_prediction(self):
        eng = _engine()
        slo = eng.register_slo("test")
        eng.record_error_event(slo.id, error_count=0, total_count=1000)
        pred = eng.predict_burn(slo.id)
        assert pred is not None
        assert pred.severity == BurnSeverity.SAFE

    def test_danger_prediction(self):
        eng = _engine()
        slo = eng.register_slo("test", target_pct=99.9)
        eng.record_error_event(slo.id, error_count=50, total_count=100)
        pred = eng.predict_burn(slo.id)
        assert pred is not None
        assert pred.severity in (BurnSeverity.DANGER, BurnSeverity.BREACH)

    def test_not_found(self):
        eng = _engine()
        assert eng.predict_burn("bad") is None


# ---------------------------------------------------------------------------
# forecast_violation
# ---------------------------------------------------------------------------


class TestForecastViolation:
    def test_forecast(self):
        eng = _engine()
        slo = eng.register_slo("test")
        eng.record_error_event(slo.id, error_count=1, total_count=100)
        forecast = eng.forecast_violation(slo.id)
        assert forecast is not None
        assert forecast.recommendation

    def test_not_found(self):
        eng = _engine()
        assert eng.forecast_violation("bad") is None


# ---------------------------------------------------------------------------
# budget_status / correlate_deployments / breach_risk / stats
# ---------------------------------------------------------------------------


class TestBudgetStatus:
    def test_status(self):
        eng = _engine()
        slo = eng.register_slo("test")
        status = eng.get_budget_status(slo.id)
        assert status is not None
        assert status["consumed_pct"] == 0.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_budget_status("bad") is None


class TestCorrelateDeployments:
    def test_correlate(self):
        eng = _engine()
        slo = eng.register_slo("test")
        result = eng.correlate_deployments(slo.id, deployment_time=time.time())
        assert result["correlated"] is True

    def test_invalid_slo(self):
        eng = _engine()
        result = eng.correlate_deployments("bad", deployment_time=time.time())
        assert result.get("error") == "slo_not_found"


class TestBreachRisk:
    def test_no_risk(self):
        eng = _engine()
        eng.register_slo("safe")
        assert len(eng.get_breach_risk()) == 0

    def test_at_risk(self):
        eng = _engine()
        slo = eng.register_slo("risky", target_pct=99.9)
        eng.record_error_event(slo.id, error_count=50, total_count=100)
        risks = eng.get_breach_risk()
        assert len(risks) >= 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_slos"] == 0

    def test_populated_stats(self):
        eng = _engine()
        slo = eng.register_slo("test")
        eng.record_error_event(slo.id, error_count=1, total_count=100)
        eng.predict_burn(slo.id)
        stats = eng.get_stats()
        assert stats["total_slos"] == 1
        assert stats["total_predictions"] == 1
