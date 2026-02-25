"""Tests for shieldops.observability.outage_predictor."""

from __future__ import annotations

from shieldops.observability.outage_predictor import (
    MitigationAction,
    OutagePrediction,
    OutagePredictionReport,
    OutageProbability,
    PredictiveOutageDetector,
    SignalReading,
    SignalType,
)


def _engine(**kw) -> PredictiveOutageDetector:
    return PredictiveOutageDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # OutageProbability (5 values)

    def test_probability_negligible(self):
        assert OutageProbability.NEGLIGIBLE == "negligible"

    def test_probability_low(self):
        assert OutageProbability.LOW == "low"

    def test_probability_elevated(self):
        assert OutageProbability.ELEVATED == "elevated"

    def test_probability_high(self):
        assert OutageProbability.HIGH == "high"

    def test_probability_imminent(self):
        assert OutageProbability.IMMINENT == "imminent"

    # SignalType (5 values)

    def test_signal_metric_drift(self):
        assert SignalType.METRIC_DRIFT == "metric_drift"

    def test_signal_dependency_degradation(self):
        assert SignalType.DEPENDENCY_DEGRADATION == "dependency_degradation"

    def test_signal_error_budget_burn(self):
        assert SignalType.ERROR_BUDGET_BURN == "error_budget_burn"

    def test_signal_deploy_recency(self):
        assert SignalType.DEPLOY_RECENCY == "deploy_recency"

    def test_signal_alert_velocity(self):
        assert SignalType.ALERT_VELOCITY == "alert_velocity"

    # MitigationAction (5 values)

    def test_action_no_action(self):
        assert MitigationAction.NO_ACTION == "no_action"

    def test_action_increase_monitoring(self):
        assert MitigationAction.INCREASE_MONITORING == "increase_monitoring"

    def test_action_pre_scale(self):
        assert MitigationAction.PRE_SCALE == "pre_scale"

    def test_action_freeze_changes(self):
        assert MitigationAction.FREEZE_CHANGES == "freeze_changes"

    def test_action_activate_incident(self):
        assert MitigationAction.ACTIVATE_INCIDENT == "activate_incident"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_signal_reading_defaults(self):
        sr = SignalReading()
        assert sr.id
        assert sr.service_name == ""
        assert sr.signal_type == SignalType.METRIC_DRIFT
        assert sr.value == 0.0
        assert sr.weight == 1.0
        assert sr.metadata == {}
        assert sr.created_at > 0

    def test_outage_prediction_defaults(self):
        op = OutagePrediction()
        assert op.id
        assert op.service_name == ""
        assert op.composite_score == 0.0
        assert op.probability == OutageProbability.NEGLIGIBLE
        assert op.signal_count == 0
        assert op.recommended_action == MitigationAction.NO_ACTION
        assert op.lead_time_minutes == 0
        assert op.created_at > 0

    def test_outage_prediction_report_defaults(self):
        rpt = OutagePredictionReport()
        assert rpt.total_signals == 0
        assert rpt.total_predictions == 0
        assert rpt.by_probability == {}
        assert rpt.by_signal_type == {}
        assert rpt.by_action == {}
        assert rpt.high_risk_services == []
        assert rpt.recommendations == []
        assert rpt.generated_at > 0


# -------------------------------------------------------------------
# record_signal
# -------------------------------------------------------------------


class TestRecordSignal:
    def test_basic_record(self):
        eng = _engine()
        sig = eng.record_signal("svc-a")
        assert sig.service_name == "svc-a"
        assert len(eng.list_signals()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        s1 = eng.record_signal("svc-a")
        s2 = eng.record_signal("svc-b")
        assert s1.id != s2.id

    def test_record_with_values(self):
        eng = _engine()
        sig = eng.record_signal(
            "svc-a",
            signal_type=SignalType.ERROR_BUDGET_BURN,
            value=0.85,
            weight=2.0,
        )
        assert sig.signal_type == SignalType.ERROR_BUDGET_BURN
        assert sig.value == 0.85
        assert sig.weight == 2.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            sig = eng.record_signal(f"svc-{i}")
            ids.append(sig.id)
        signals = eng.list_signals(limit=100)
        assert len(signals) == 3
        found = {s.id for s in signals}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_signal
# -------------------------------------------------------------------


class TestGetSignal:
    def test_get_existing(self):
        eng = _engine()
        sig = eng.record_signal("svc-a")
        found = eng.get_signal(sig.id)
        assert found is not None
        assert found.id == sig.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_signal("nonexistent") is None


# -------------------------------------------------------------------
# list_signals
# -------------------------------------------------------------------


class TestListSignals:
    def test_list_all(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.record_signal("svc-b")
        eng.record_signal("svc-c")
        assert len(eng.list_signals()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.record_signal("svc-b")
        eng.record_signal("svc-a")
        results = eng.list_signals(service_name="svc-a")
        assert len(results) == 2
        assert all(s.service_name == "svc-a" for s in results)

    def test_filter_by_signal_type(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_type=SignalType.METRIC_DRIFT)
        eng.record_signal("svc-b", signal_type=SignalType.ALERT_VELOCITY)
        results = eng.list_signals(signal_type=SignalType.METRIC_DRIFT)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_signal(f"svc-{i}")
        results = eng.list_signals(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# compute_prediction
# -------------------------------------------------------------------


class TestComputePrediction:
    def test_with_signals(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.8, weight=1.0)
        eng.record_signal("svc-a", value=0.9, weight=1.0)
        pred = eng.compute_prediction("svc-a")
        assert pred.service_name == "svc-a"
        assert pred.signal_count == 2
        assert pred.composite_score > 0

    def test_without_signals(self):
        eng = _engine()
        pred = eng.compute_prediction("svc-a")
        assert pred.composite_score == 0.0
        assert pred.probability == OutageProbability.NEGLIGIBLE
        assert pred.signal_count == 0

    def test_high_score_imminent(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.95, weight=1.0)
        pred = eng.compute_prediction("svc-a")
        assert pred.probability == OutageProbability.IMMINENT
        assert pred.recommended_action == MitigationAction.ACTIVATE_INCIDENT


# -------------------------------------------------------------------
# get_prediction
# -------------------------------------------------------------------


class TestGetPrediction:
    def test_get_existing(self):
        eng = _engine()
        pred = eng.compute_prediction("svc-a")
        found = eng.get_prediction(pred.id)
        assert found is not None
        assert found.id == pred.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# -------------------------------------------------------------------
# list_predictions
# -------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.compute_prediction("svc-a")
        eng.compute_prediction("svc-b")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.compute_prediction("svc-a")
        eng.compute_prediction("svc-b")
        results = eng.list_predictions(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"


# -------------------------------------------------------------------
# assess_lead_time
# -------------------------------------------------------------------


class TestAssessLeadTime:
    def test_with_predictions(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.6)
        eng.compute_prediction("svc-a")
        result = eng.assess_lead_time("svc-a")
        assert result["has_predictions"] is True
        assert result["lead_time_minutes"] > 0

    def test_without_predictions(self):
        eng = _engine()
        result = eng.assess_lead_time("svc-a")
        assert result["has_predictions"] is False
        assert result["lead_time_minutes"] == 0


# -------------------------------------------------------------------
# recommend_mitigation
# -------------------------------------------------------------------


class TestRecommendMitigation:
    def test_with_predictions(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.8)
        eng.compute_prediction("svc-a")
        result = eng.recommend_mitigation("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["action"] != MitigationAction.NO_ACTION.value

    def test_without_predictions(self):
        eng = _engine()
        result = eng.recommend_mitigation("svc-a")
        assert result["action"] == MitigationAction.NO_ACTION.value
        assert result["reason"] == "No predictions available"


# -------------------------------------------------------------------
# generate_prediction_report
# -------------------------------------------------------------------


class TestGeneratePredictionReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.9)
        eng.record_signal("svc-b", value=0.1)
        eng.compute_prediction("svc-a")
        eng.compute_prediction("svc-b")
        report = eng.generate_prediction_report()
        assert report.total_signals == 2
        assert report.total_predictions == 2
        assert isinstance(report.by_probability, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_prediction_report()
        assert report.total_signals == 0
        assert report.total_predictions == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.record_signal("svc-b")
        eng.compute_prediction("svc-a")
        count = eng.clear_data()
        assert count == 3
        assert len(eng.list_signals()) == 0
        assert len(eng.list_predictions()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_signals"] == 0
        assert stats["total_predictions"] == 0
        assert stats["composite_threshold"] == 0.75
        assert stats["probability_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_signal("svc-a", value=0.9)
        eng.record_signal("svc-b", value=0.1)
        eng.compute_prediction("svc-a")
        eng.compute_prediction("svc-b")
        stats = eng.get_stats()
        assert stats["total_signals"] == 2
        assert stats["total_predictions"] == 2
        assert len(stats["probability_distribution"]) >= 1
