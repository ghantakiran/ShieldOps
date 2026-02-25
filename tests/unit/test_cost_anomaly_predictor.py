"""Tests for shieldops.billing.cost_anomaly_predictor — CostAnomalyPredictor."""

from __future__ import annotations

from shieldops.billing.cost_anomaly_predictor import (
    CostAnomalyPredictor,
    CostPredictionReport,
    CostSpikePrediction,
    CostSpikeRisk,
    IndicatorReading,
    LeadingIndicator,
    PreventionAction,
)


def _engine(**kw) -> CostAnomalyPredictor:
    return CostAnomalyPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CostSpikeRisk (5)
    def test_risk_negligible(self):
        assert CostSpikeRisk.NEGLIGIBLE == "negligible"

    def test_risk_low(self):
        assert CostSpikeRisk.LOW == "low"

    def test_risk_moderate(self):
        assert CostSpikeRisk.MODERATE == "moderate"

    def test_risk_high(self):
        assert CostSpikeRisk.HIGH == "high"

    def test_risk_imminent(self):
        assert CostSpikeRisk.IMMINENT == "imminent"

    # LeadingIndicator (5)
    def test_indicator_resource_provisioning(self):
        assert LeadingIndicator.RESOURCE_PROVISIONING == "resource_provisioning"

    def test_indicator_autoscaler_activity(self):
        assert LeadingIndicator.AUTOSCALER_ACTIVITY == "autoscaler_activity"

    def test_indicator_traffic_surge(self):
        assert LeadingIndicator.TRAFFIC_SURGE == "traffic_surge"

    def test_indicator_new_deployment(self):
        assert LeadingIndicator.NEW_DEPLOYMENT == "new_deployment"

    def test_indicator_data_transfer_spike(self):
        assert LeadingIndicator.DATA_TRANSFER_SPIKE == "data_transfer_spike"

    # PreventionAction (5)
    def test_action_no_action(self):
        assert PreventionAction.NO_ACTION == "no_action"

    def test_action_alert_finops(self):
        assert PreventionAction.ALERT_FINOPS == "alert_finops"

    def test_action_apply_budget_cap(self):
        assert PreventionAction.APPLY_BUDGET_CAP == "apply_budget_cap"

    def test_action_throttle_scaling(self):
        assert PreventionAction.THROTTLE_SCALING == "throttle_scaling"

    def test_action_emergency_review(self):
        assert PreventionAction.EMERGENCY_REVIEW == "emergency_review"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_indicator_reading_defaults(self):
        r = IndicatorReading()
        assert r.id
        assert r.service_name == ""
        assert r.indicator == LeadingIndicator.RESOURCE_PROVISIONING
        assert r.value == 0.0
        assert r.baseline_value == 0.0
        assert r.deviation_pct == 0.0
        assert r.created_at > 0

    def test_cost_spike_prediction_defaults(self):
        p = CostSpikePrediction()
        assert p.id
        assert p.service_name == ""
        assert p.predicted_spike_usd == 0.0
        assert p.risk_level == CostSpikeRisk.NEGLIGIBLE
        assert p.indicator_count == 0
        assert p.recommended_action == PreventionAction.NO_ACTION
        assert p.preventable_spend_usd == 0.0
        assert p.created_at > 0

    def test_cost_prediction_report_defaults(self):
        r = CostPredictionReport()
        assert r.total_indicators == 0
        assert r.total_predictions == 0
        assert r.total_predicted_spend_usd == 0.0
        assert r.total_preventable_usd == 0.0
        assert r.by_risk == {}
        assert r.by_indicator == {}
        assert r.by_action == {}
        assert r.high_risk_services == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_indicator
# ---------------------------------------------------------------------------


class TestRecordIndicator:
    def test_basic_recording(self):
        eng = _engine()
        r = eng.record_indicator(
            service_name="ec2",
            indicator=LeadingIndicator.TRAFFIC_SURGE,
            value=200.0,
            baseline_value=100.0,
        )
        assert r.service_name == "ec2"
        assert r.indicator == LeadingIndicator.TRAFFIC_SURGE
        assert r.value == 200.0
        assert r.baseline_value == 100.0
        assert r.deviation_pct == 100.0

    def test_zero_baseline_deviation(self):
        eng = _engine()
        r = eng.record_indicator(
            service_name="lambda",
            value=500.0,
            baseline_value=0.0,
        )
        assert r.deviation_pct == 0.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_indicator(service_name=f"svc-{i}", value=float(i))
        assert len(eng._indicators) == 3


# ---------------------------------------------------------------------------
# get_indicator
# ---------------------------------------------------------------------------


class TestGetIndicator:
    def test_found(self):
        eng = _engine()
        r = eng.record_indicator(service_name="ec2", value=10.0)
        result = eng.get_indicator(r.id)
        assert result is not None
        assert result.service_name == "ec2"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_indicator("nonexistent") is None


# ---------------------------------------------------------------------------
# list_indicators
# ---------------------------------------------------------------------------


class TestListIndicators:
    def test_list_all(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=10.0)
        eng.record_indicator(service_name="lambda", value=20.0)
        assert len(eng.list_indicators()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=10.0)
        eng.record_indicator(service_name="lambda", value=20.0)
        results = eng.list_indicators(service_name="ec2")
        assert len(results) == 1
        assert results[0].service_name == "ec2"

    def test_filter_by_indicator_type(self):
        eng = _engine()
        eng.record_indicator(
            service_name="ec2",
            indicator=LeadingIndicator.TRAFFIC_SURGE,
            value=10.0,
        )
        eng.record_indicator(
            service_name="lambda",
            indicator=LeadingIndicator.NEW_DEPLOYMENT,
            value=20.0,
        )
        results = eng.list_indicators(indicator=LeadingIndicator.NEW_DEPLOYMENT)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# predict_cost_spike
# ---------------------------------------------------------------------------


class TestPredictCostSpike:
    def test_no_indicators_negligible(self):
        eng = _engine()
        pred = eng.predict_cost_spike("unknown-svc")
        assert pred.service_name == "unknown-svc"
        assert pred.risk_level == CostSpikeRisk.NEGLIGIBLE
        assert pred.indicator_count == 0

    def test_high_deviation_high_risk(self):
        eng = _engine(spike_threshold_usd=1000.0)
        eng.record_indicator(
            service_name="ec2",
            indicator=LeadingIndicator.TRAFFIC_SURGE,
            value=300.0,
            baseline_value=100.0,
        )
        pred = eng.predict_cost_spike("ec2")
        assert pred.risk_level == CostSpikeRisk.IMMINENT
        assert pred.predicted_spike_usd > 0
        assert pred.preventable_spend_usd > 0
        assert pred.recommended_action == PreventionAction.EMERGENCY_REVIEW

    def test_low_deviation_low_risk(self):
        eng = _engine(spike_threshold_usd=1000.0)
        eng.record_indicator(
            service_name="lambda",
            value=125.0,
            baseline_value=100.0,
        )
        pred = eng.predict_cost_spike("lambda")
        assert pred.risk_level == CostSpikeRisk.LOW
        assert pred.recommended_action == PreventionAction.ALERT_FINOPS


# ---------------------------------------------------------------------------
# get_prediction
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        pred = eng.predict_cost_spike("ec2")
        result = eng.get_prediction(pred.id)
        assert result is not None
        assert result.service_name == "ec2"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.predict_cost_spike("ec2")
        eng.predict_cost_spike("lambda")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.predict_cost_spike("ec2")
        eng.predict_cost_spike("lambda")
        results = eng.list_predictions(service_name="ec2")
        assert len(results) == 1

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=500.0, baseline_value=100.0)
        eng.predict_cost_spike("ec2")
        eng.predict_cost_spike("lambda")
        results = eng.list_predictions(risk_level=CostSpikeRisk.NEGLIGIBLE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# suggest_prevention
# ---------------------------------------------------------------------------


class TestSuggestPrevention:
    def test_no_predictions(self):
        eng = _engine()
        result = eng.suggest_prevention("ec2")
        assert result["action"] == PreventionAction.NO_ACTION.value
        assert result["reason"] == "No predictions available"

    def test_with_prediction(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=300.0, baseline_value=100.0)
        eng.predict_cost_spike("ec2")
        result = eng.suggest_prevention("ec2")
        assert result["service_name"] == "ec2"
        assert result["risk_level"] == CostSpikeRisk.IMMINENT.value
        assert result["predicted_spike_usd"] > 0


# ---------------------------------------------------------------------------
# estimate_preventable_spend
# ---------------------------------------------------------------------------


class TestEstimatePreventableSpend:
    def test_empty(self):
        eng = _engine()
        result = eng.estimate_preventable_spend()
        assert result["total_predicted_spend_usd"] == 0.0
        assert result["total_preventable_usd"] == 0.0
        assert result["total_predictions"] == 0

    def test_with_predictions(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=300.0, baseline_value=100.0)
        eng.predict_cost_spike("ec2")
        result = eng.estimate_preventable_spend()
        assert result["total_predicted_spend_usd"] > 0
        assert result["total_preventable_usd"] > 0
        assert result["total_predictions"] == 1


# ---------------------------------------------------------------------------
# generate_prediction_report
# ---------------------------------------------------------------------------


class TestGeneratePredictionReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=300.0, baseline_value=100.0)
        eng.predict_cost_spike("ec2")
        report = eng.generate_prediction_report()
        assert isinstance(report, CostPredictionReport)
        assert report.total_indicators == 1
        assert report.total_predictions == 1
        assert report.total_predicted_spend_usd > 0
        assert len(report.by_risk) > 0
        assert len(report.by_indicator) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_prediction_report()
        assert report.total_indicators == 0
        assert report.total_predictions == 0
        assert report.total_predicted_spend_usd == 0.0
        assert "No significant cost spike risks detected" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=10.0)
        eng.predict_cost_spike("ec2")
        count = eng.clear_data()
        assert count == 2
        assert len(eng._indicators) == 0
        assert len(eng._predictions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_indicators"] == 0
        assert stats["total_predictions"] == 0
        assert stats["risk_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_indicator(service_name="ec2", value=10.0)
        eng.predict_cost_spike("ec2")
        stats = eng.get_stats()
        assert stats["total_indicators"] == 1
        assert stats["total_predictions"] == 1
        assert stats["spike_threshold_usd"] == 1000.0
