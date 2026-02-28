"""Tests for shieldops.observability.predictive_alert — PredictiveAlertEngine."""

from __future__ import annotations

from shieldops.observability.predictive_alert import (
    AlertConfidence,
    PredictionType,
    PredictiveAlertEngine,
    PredictiveAlertRecord,
    PredictiveAlertReport,
    PreventionOutcome,
    SignalTrend,
)


def _engine(**kw) -> PredictiveAlertEngine:
    return PredictiveAlertEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PredictionType (5)
    def test_prediction_anomaly_projection(self):
        assert PredictionType.ANOMALY_PROJECTION == "anomaly_projection"

    def test_prediction_trend_breach(self):
        assert PredictionType.TREND_BREACH == "trend_breach"

    def test_prediction_causal_inference(self):
        assert PredictionType.CAUSAL_INFERENCE == "causal_inference"

    def test_prediction_pattern_match(self):
        assert PredictionType.PATTERN_MATCH == "pattern_match"

    def test_prediction_seasonal(self):
        assert PredictionType.SEASONAL == "seasonal"

    # AlertConfidence (5)
    def test_confidence_very_high(self):
        assert AlertConfidence.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert AlertConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert AlertConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert AlertConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert AlertConfidence.SPECULATIVE == "speculative"

    # PreventionOutcome (5)
    def test_outcome_prevented(self):
        assert PreventionOutcome.PREVENTED == "prevented"

    def test_outcome_mitigated(self):
        assert PreventionOutcome.MITIGATED == "mitigated"

    def test_outcome_false_positive(self):
        assert PreventionOutcome.FALSE_POSITIVE == "false_positive"

    def test_outcome_missed(self):
        assert PreventionOutcome.MISSED == "missed"

    def test_outcome_inconclusive(self):
        assert PreventionOutcome.INCONCLUSIVE == "inconclusive"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_predictive_alert_record_defaults(self):
        r = PredictiveAlertRecord()
        assert r.id
        assert r.service_name == ""
        assert r.prediction_type == PredictionType.TREND_BREACH
        assert r.alert_confidence == AlertConfidence.MODERATE
        assert r.prevention_outcome == PreventionOutcome.PREVENTED
        assert r.lead_time_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_signal_trend_defaults(self):
        r = SignalTrend()
        assert r.id
        assert r.trend_label == ""
        assert r.prediction_type == PredictionType.TREND_BREACH
        assert r.alert_confidence == AlertConfidence.HIGH
        assert r.slope_value == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PredictiveAlertReport()
        assert r.total_alerts == 0
        assert r.total_trends == 0
        assert r.prevention_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_confidence == {}
        assert r.false_positive_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_alert
# -------------------------------------------------------------------


class TestRecordAlert:
    def test_basic(self):
        eng = _engine()
        r = eng.record_alert(
            "svc-a",
            prediction_type=PredictionType.ANOMALY_PROJECTION,
            alert_confidence=AlertConfidence.HIGH,
        )
        assert r.service_name == "svc-a"
        assert r.prediction_type == PredictionType.ANOMALY_PROJECTION

    def test_with_outcome(self):
        eng = _engine()
        r = eng.record_alert(
            "svc-b",
            prevention_outcome=PreventionOutcome.FALSE_POSITIVE,
            lead_time_minutes=15.5,
        )
        assert r.prevention_outcome == PreventionOutcome.FALSE_POSITIVE
        assert r.lead_time_minutes == 15.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_alert(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_alert
# -------------------------------------------------------------------


class TestGetAlert:
    def test_found(self):
        eng = _engine()
        r = eng.record_alert("svc-a")
        assert eng.get_alert(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_alert("nonexistent") is None


# -------------------------------------------------------------------
# list_alerts
# -------------------------------------------------------------------


class TestListAlerts:
    def test_list_all(self):
        eng = _engine()
        eng.record_alert("svc-a")
        eng.record_alert("svc-b")
        assert len(eng.list_alerts()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_alert("svc-a")
        eng.record_alert("svc-b")
        results = eng.list_alerts(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_alert("svc-a", prediction_type=PredictionType.SEASONAL)
        eng.record_alert("svc-b", prediction_type=PredictionType.TREND_BREACH)
        results = eng.list_alerts(prediction_type=PredictionType.SEASONAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_trend
# -------------------------------------------------------------------


class TestAddTrend:
    def test_basic(self):
        eng = _engine()
        t = eng.add_trend(
            "trend-1",
            prediction_type=PredictionType.CAUSAL_INFERENCE,
            alert_confidence=AlertConfidence.VERY_HIGH,
            slope_value=1.5,
        )
        assert t.trend_label == "trend-1"
        assert t.slope_value == 1.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_trend(f"trend-{i}")
        assert len(eng._trends) == 2


# -------------------------------------------------------------------
# analyze_prediction_accuracy
# -------------------------------------------------------------------


class TestAnalyzePredictionAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_alert(
            "svc-a", prevention_outcome=PreventionOutcome.PREVENTED, lead_time_minutes=10.0
        )
        eng.record_alert(
            "svc-a", prevention_outcome=PreventionOutcome.FALSE_POSITIVE, lead_time_minutes=20.0
        )
        result = eng.analyze_prediction_accuracy("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_alerts"] == 2
        assert result["prevention_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_prediction_accuracy("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=50.0)
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.PREVENTED)
        result = eng.analyze_prediction_accuracy("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_false_positives
# -------------------------------------------------------------------


class TestIdentifyFalsePositives:
    def test_with_false_positives(self):
        eng = _engine()
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.FALSE_POSITIVE)
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.FALSE_POSITIVE)
        eng.record_alert("svc-b", prevention_outcome=PreventionOutcome.PREVENTED)
        results = eng.identify_false_positives()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_false_positives() == []


# -------------------------------------------------------------------
# rank_by_lead_time
# -------------------------------------------------------------------


class TestRankByLeadTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_alert("svc-a", lead_time_minutes=50.0)
        eng.record_alert("svc-a", lead_time_minutes=30.0)
        eng.record_alert("svc-b", lead_time_minutes=10.0)
        results = eng.rank_by_lead_time()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_lead_time_minutes"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_lead_time() == []


# -------------------------------------------------------------------
# detect_prediction_drift
# -------------------------------------------------------------------


class TestDetectPredictionDrift:
    def test_with_drift(self):
        eng = _engine()
        for _ in range(5):
            eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        eng.record_alert("svc-b", prevention_outcome=PreventionOutcome.PREVENTED)
        results = eng.detect_prediction_drift()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["drifting"] is True

    def test_no_drift(self):
        eng = _engine()
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.PREVENTED)
        assert eng.detect_prediction_drift() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.PREVENTED)
        eng.record_alert("svc-b", prevention_outcome=PreventionOutcome.FALSE_POSITIVE)
        eng.add_trend("trend-1")
        report = eng.generate_report()
        assert report.total_alerts == 2
        assert report.total_trends == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_alerts == 0
        assert report.recommendations[0] == "Predictive alert engine meets targets"

    def test_below_threshold(self):
        eng = _engine(min_confidence_pct=90.0)
        eng.record_alert("svc-a", prevention_outcome=PreventionOutcome.FALSE_POSITIVE)
        report = eng.generate_report()
        assert any("below threshold" in r for r in report.recommendations)


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_alert("svc-a")
        eng.add_trend("trend-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._trends) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_trends"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_alert("svc-a", prediction_type=PredictionType.TREND_BREACH)
        eng.record_alert("svc-b", prediction_type=PredictionType.SEASONAL)
        eng.add_trend("t1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_trends"] == 1
        assert stats["unique_services"] == 2
