"""Tests for shieldops.incidents.severity_predictor — IncidentSeverityPredictor."""

from __future__ import annotations

import pytest

from shieldops.incidents.severity_predictor import (
    IncidentSeverityPredictor,
    IncidentSignal,
    PredictedSeverity,
    PredictionOutcome,
    ServiceProfile,
    SeverityPrediction,
    SignalType,
)


def _predictor(**kw) -> IncidentSeverityPredictor:
    return IncidentSeverityPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PredictedSeverity (5 values)

    def test_predicted_severity_sev1(self):
        assert PredictedSeverity.SEV1 == "sev1"

    def test_predicted_severity_sev2(self):
        assert PredictedSeverity.SEV2 == "sev2"

    def test_predicted_severity_sev3(self):
        assert PredictedSeverity.SEV3 == "sev3"

    def test_predicted_severity_sev4(self):
        assert PredictedSeverity.SEV4 == "sev4"

    def test_predicted_severity_sev5(self):
        assert PredictedSeverity.SEV5 == "sev5"

    # SignalType (6 values)

    def test_signal_type_alert(self):
        assert SignalType.ALERT == "alert"

    def test_signal_type_error_spike(self):
        assert SignalType.ERROR_SPIKE == "error_spike"

    def test_signal_type_latency(self):
        assert SignalType.LATENCY == "latency"

    def test_signal_type_availability(self):
        assert SignalType.AVAILABILITY == "availability"

    def test_signal_type_security(self):
        assert SignalType.SECURITY == "security"

    def test_signal_type_capacity(self):
        assert SignalType.CAPACITY == "capacity"

    # PredictionOutcome (4 values)

    def test_prediction_outcome_pending(self):
        assert PredictionOutcome.PENDING == "pending"

    def test_prediction_outcome_correct(self):
        assert PredictionOutcome.CORRECT == "correct"

    def test_prediction_outcome_over_estimated(self):
        assert PredictionOutcome.OVER_ESTIMATED == "over_estimated"

    def test_prediction_outcome_under_estimated(self):
        assert PredictionOutcome.UNDER_ESTIMATED == "under_estimated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_incident_signal_defaults(self):
        signal = IncidentSignal(signal_type=SignalType.ALERT)
        assert signal.signal_type == SignalType.ALERT
        assert signal.value == 0.0
        assert signal.service == ""
        assert signal.description == ""

    def test_service_profile_defaults(self):
        profile = ServiceProfile(service_name="api-gateway")
        assert profile.id
        assert profile.service_name == "api-gateway"
        assert profile.criticality == 3
        assert profile.historical_incidents == 0
        assert profile.avg_severity == 3.0
        assert profile.tags == []
        assert profile.created_at > 0

    def test_severity_prediction_defaults(self):
        prediction = SeverityPrediction(
            service="api-gateway",
            predicted_severity=PredictedSeverity.SEV3,
        )
        assert prediction.id
        assert prediction.service == "api-gateway"
        assert prediction.predicted_severity == PredictedSeverity.SEV3
        assert prediction.confidence == 0.0
        assert prediction.signals == []
        assert prediction.actual_severity is None
        assert prediction.outcome == PredictionOutcome.PENDING
        assert prediction.predicted_at > 0


# ---------------------------------------------------------------------------
# register_service
# ---------------------------------------------------------------------------


class TestRegisterService:
    def test_basic_register(self):
        pred = _predictor()
        profile = pred.register_service("api-gateway")
        assert profile.service_name == "api-gateway"
        assert profile.criticality == 3
        assert pred.get_service_profile(profile.id) is not None

    def test_register_assigns_unique_ids(self):
        pred = _predictor()
        p1 = pred.register_service("api-gateway")
        p2 = pred.register_service("payment-svc")
        assert p1.id != p2.id

    def test_evicts_at_max_profiles(self):
        pred = _predictor(max_profiles=3)
        ids = []
        for i in range(4):
            profile = pred.register_service(f"svc-{i}")
            ids.append(profile.id)
        assert pred.get_service_profile(ids[0]) is None
        assert pred.get_service_profile(ids[3]) is not None
        assert len(pred.list_profiles()) == 3


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------


class TestPredict:
    def test_basic_predict(self):
        pred = _predictor()
        prediction = pred.predict("api-gateway", [])
        assert prediction.service == "api-gateway"
        assert prediction.predicted_severity == PredictedSeverity.SEV5
        assert prediction.confidence == pytest.approx(0.5, abs=1e-4)
        assert pred.get_prediction(prediction.id) is not None

    def test_predict_with_signals(self):
        pred = _predictor()
        signals = [
            {"signal_type": "availability", "value": 1.0},
            {"signal_type": "security", "value": 1.0},
            {"signal_type": "error_spike", "value": 1.0},
            {"signal_type": "latency", "value": 1.0},
        ]
        # base_score = 25 + 22 + 18 + 15 = 80 -> no profile -> no multiplier
        # score = 80 -> >= 70 -> SEV2
        prediction = pred.predict("api-gateway", signals)
        assert prediction.predicted_severity == PredictedSeverity.SEV2
        assert len(prediction.signals) == 4
        # confidence = min(0.95, 0.5 + 4*0.1) = 0.9
        assert prediction.confidence == pytest.approx(0.9, abs=1e-4)

    def test_predict_with_service_profile(self):
        pred = _predictor()
        # criticality=1 -> multiplier = (6-1)/5 = 1.0 -> score *= (0.5 + 1.0*0.5) = 1.0
        pred.register_service("critical-svc", criticality=1)
        signals = [
            {"signal_type": "availability", "value": 1.0},
            {"signal_type": "security", "value": 1.0},
            {"signal_type": "error_spike", "value": 1.0},
            {"signal_type": "latency", "value": 1.0},
        ]
        # base_score = 25+22+18+15 = 80, * 1.0 = 80 -> SEV2
        prediction = pred.predict("critical-svc", signals)
        assert prediction.predicted_severity == PredictedSeverity.SEV2

    def test_predict_evicts_at_max(self):
        pred = _predictor(max_predictions=3)
        ids = []
        for i in range(4):
            p = pred.predict(f"svc-{i}", [])
            ids.append(p.id)
        assert pred.get_prediction(ids[0]) is None
        assert pred.get_prediction(ids[3]) is not None
        assert len(pred.list_predictions()) == 3


# ---------------------------------------------------------------------------
# record_actual
# ---------------------------------------------------------------------------


class TestRecordActual:
    def test_correct_prediction(self):
        pred = _predictor()
        prediction = pred.predict("api-gateway", [])
        # predicted SEV5, record actual SEV5 -> CORRECT
        result = pred.record_actual(prediction.id, PredictedSeverity.SEV5)
        assert result is not None
        assert result.actual_severity == PredictedSeverity.SEV5
        assert result.outcome == PredictionOutcome.CORRECT

    def test_over_estimated(self):
        pred = _predictor()
        signals = [
            {"signal_type": "availability", "value": 1.0},
            {"signal_type": "security", "value": 1.0},
            {"signal_type": "error_spike", "value": 1.0},
            {"signal_type": "latency", "value": 1.0},
        ]
        prediction = pred.predict("api-gateway", signals)
        # predicted SEV2 (idx=1), actual SEV4 (idx=3) -> pred_idx < actual_idx -> OVER_ESTIMATED
        result = pred.record_actual(prediction.id, PredictedSeverity.SEV4)
        assert result is not None
        assert result.outcome == PredictionOutcome.OVER_ESTIMATED

    def test_under_estimated(self):
        pred = _predictor()
        prediction = pred.predict("api-gateway", [])
        # predicted SEV5 (idx=4), actual SEV1 (idx=0) -> pred_idx > actual_idx -> UNDER_ESTIMATED
        result = pred.record_actual(prediction.id, PredictedSeverity.SEV1)
        assert result is not None
        assert result.outcome == PredictionOutcome.UNDER_ESTIMATED

    def test_record_actual_not_found(self):
        pred = _predictor()
        result = pred.record_actual("nonexistent", PredictedSeverity.SEV3)
        assert result is None


# ---------------------------------------------------------------------------
# get_prediction
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        pred = _predictor()
        prediction = pred.predict("api-gateway", [])
        result = pred.get_prediction(prediction.id)
        assert result is not None
        assert result.id == prediction.id

    def test_not_found(self):
        pred = _predictor()
        assert pred.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        pred = _predictor()
        pred.predict("svc-a", [])
        pred.predict("svc-b", [])
        pred.predict("svc-c", [])
        assert len(pred.list_predictions()) == 3

    def test_filter_by_service(self):
        pred = _predictor()
        pred.predict("svc-a", [])
        pred.predict("svc-b", [])
        pred.predict("svc-a", [])
        results = pred.list_predictions(service="svc-a")
        assert len(results) == 2
        assert all(p.service == "svc-a" for p in results)

    def test_filter_by_outcome(self):
        pred = _predictor()
        p1 = pred.predict("svc-a", [])
        p2 = pred.predict("svc-b", [])
        pred.record_actual(p1.id, PredictedSeverity.SEV5)  # CORRECT
        pred.record_actual(p2.id, PredictedSeverity.SEV1)  # UNDER_ESTIMATED
        results = pred.list_predictions(outcome=PredictionOutcome.CORRECT)
        assert len(results) == 1
        assert results[0].outcome == PredictionOutcome.CORRECT


# ---------------------------------------------------------------------------
# get_accuracy
# ---------------------------------------------------------------------------


class TestGetAccuracy:
    def test_accuracy_empty(self):
        pred = _predictor()
        acc = pred.get_accuracy()
        assert acc["total_evaluated"] == 0
        assert acc["accuracy"] == 0.0

    def test_accuracy_populated(self):
        pred = _predictor()
        p1 = pred.predict("svc-a", [])
        p2 = pred.predict("svc-b", [])
        p3 = pred.predict("svc-c", [])
        pred.record_actual(p1.id, PredictedSeverity.SEV5)  # CORRECT
        pred.record_actual(p2.id, PredictedSeverity.SEV5)  # CORRECT
        pred.record_actual(p3.id, PredictedSeverity.SEV1)  # UNDER_ESTIMATED
        acc = pred.get_accuracy()
        assert acc["total_evaluated"] == 3
        assert acc["correct"] == 2
        assert acc["under_estimated"] == 1
        assert acc["accuracy"] == pytest.approx(2 / 3, abs=1e-4)


# ---------------------------------------------------------------------------
# get_service_profile
# ---------------------------------------------------------------------------


class TestGetServiceProfile:
    def test_found(self):
        pred = _predictor()
        profile = pred.register_service("api-gateway")
        result = pred.get_service_profile(profile.id)
        assert result is not None
        assert result.id == profile.id

    def test_not_found(self):
        pred = _predictor()
        assert pred.get_service_profile("nonexistent") is None


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_all(self):
        pred = _predictor()
        pred.register_service("svc-a")
        pred.register_service("svc-b")
        assert len(pred.list_profiles()) == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        pred = _predictor()
        stats = pred.get_stats()
        assert stats["total_predictions"] == 0
        assert stats["total_profiles"] == 0
        assert stats["severity_distribution"] == {}
        assert stats["outcome_distribution"] == {}
        assert stats["accuracy"] == 0.0

    def test_stats_populated(self):
        pred = _predictor()
        pred.register_service("svc-a", criticality=1)
        pred.register_service("svc-b", criticality=5)
        p1 = pred.predict("svc-a", [])
        p2 = pred.predict("svc-b", [])
        pred.record_actual(p1.id, PredictedSeverity.SEV5)  # CORRECT
        pred.record_actual(p2.id, PredictedSeverity.SEV1)  # UNDER_ESTIMATED

        stats = pred.get_stats()
        assert stats["total_predictions"] == 2
        assert stats["total_profiles"] == 2
        assert stats["severity_distribution"][PredictedSeverity.SEV5] == 2
        assert PredictionOutcome.CORRECT in stats["outcome_distribution"]
        assert PredictionOutcome.UNDER_ESTIMATED in stats["outcome_distribution"]
        assert stats["accuracy"] == pytest.approx(0.5, abs=1e-4)
