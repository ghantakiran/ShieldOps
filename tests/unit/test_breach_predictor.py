"""Tests for shieldops.sla.breach_predictor — SLABreachPredictor."""

from __future__ import annotations

from shieldops.sla.breach_predictor import (
    BreachCategory,
    BreachPrediction,
    BreachPredictorReport,
    BreachRisk,
    BreachThreshold,
    MitigationAction,
    SLABreachPredictor,
)


def _engine(**kw) -> SLABreachPredictor:
    return SLABreachPredictor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BreachRisk (5)
    def test_risk_imminent(self):
        assert BreachRisk.IMMINENT == "imminent"

    def test_risk_high(self):
        assert BreachRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert BreachRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert BreachRisk.LOW == "low"

    def test_risk_negligible(self):
        assert BreachRisk.NEGLIGIBLE == "negligible"

    # BreachCategory (5)
    def test_cat_availability(self):
        assert BreachCategory.AVAILABILITY == "availability"

    def test_cat_latency(self):
        assert BreachCategory.LATENCY == "latency"

    def test_cat_error_rate(self):
        assert BreachCategory.ERROR_RATE == "error_rate"

    def test_cat_throughput(self):
        assert BreachCategory.THROUGHPUT == "throughput"

    def test_cat_durability(self):
        assert BreachCategory.DURABILITY == "durability"

    # MitigationAction (5)
    def test_action_scale(self):
        assert MitigationAction.SCALE_RESOURCES == "scale_resources"

    def test_action_reroute(self):
        assert MitigationAction.REROUTE_TRAFFIC == "reroute_traffic"

    def test_action_cache(self):
        assert MitigationAction.ENABLE_CACHE == "enable_cache"

    def test_action_oncall(self):
        assert MitigationAction.ALERT_ONCALL == "alert_oncall"

    def test_action_none(self):
        assert MitigationAction.NO_ACTION == "no_action"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_prediction_defaults(self):
        r = BreachPrediction()
        assert r.id
        assert r.service_name == ""
        assert r.risk == BreachRisk.LOW
        assert r.category == BreachCategory.AVAILABILITY
        assert r.action == MitigationAction.NO_ACTION
        assert r.confidence_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_threshold_defaults(self):
        r = BreachThreshold()
        assert r.id
        assert r.threshold_name == ""
        assert r.category == BreachCategory.AVAILABILITY
        assert r.risk == BreachRisk.MODERATE
        assert r.warning_hours == 24.0
        assert r.critical_hours == 4.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = BreachPredictorReport()
        assert r.total_predictions == 0
        assert r.total_thresholds == 0
        assert r.high_risk_rate_pct == 0.0
        assert r.by_risk == {}
        assert r.by_category == {}
        assert r.imminent_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_prediction
# -------------------------------------------------------------------


class TestRecordPrediction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            "svc-a",
            risk=BreachRisk.IMMINENT,
            category=BreachCategory.LATENCY,
        )
        assert r.service_name == "svc-a"
        assert r.risk == BreachRisk.IMMINENT

    def test_with_confidence(self):
        eng = _engine()
        r = eng.record_prediction("svc-b", confidence_pct=85.5)
        assert r.confidence_pct == 85.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_prediction
# -------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction("svc-a")
        assert eng.get_prediction(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# -------------------------------------------------------------------
# list_predictions
# -------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction("svc-a")
        eng.record_prediction("svc-b")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_prediction("svc-a")
        eng.record_prediction("svc-b")
        results = eng.list_predictions(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_prediction("svc-a", risk=BreachRisk.IMMINENT)
        eng.record_prediction("svc-b", risk=BreachRisk.LOW)
        results = eng.list_predictions(risk=BreachRisk.IMMINENT)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_threshold
# -------------------------------------------------------------------


class TestAddThreshold:
    def test_basic(self):
        eng = _engine()
        t = eng.add_threshold(
            "latency-breach",
            category=BreachCategory.LATENCY,
            risk=BreachRisk.HIGH,
            warning_hours=12.0,
            critical_hours=2.0,
        )
        assert t.threshold_name == "latency-breach"
        assert t.warning_hours == 12.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_threshold(f"thresh-{i}")
        assert len(eng._thresholds) == 2


# -------------------------------------------------------------------
# analyze_breach_risk
# -------------------------------------------------------------------


class TestAnalyzeBreachRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(
            "svc-a",
            risk=BreachRisk.IMMINENT,
            confidence_pct=90.0,
        )
        eng.record_prediction(
            "svc-a",
            risk=BreachRisk.LOW,
            confidence_pct=50.0,
        )
        result = eng.analyze_breach_risk("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["prediction_count"] == 2
        assert result["high_risk_count"] == 1
        assert result["high_risk_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_breach_risk("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_imminent_breaches
# -------------------------------------------------------------------


class TestIdentifyImminentBreaches:
    def test_with_breaches(self):
        eng = _engine()
        eng.record_prediction("svc-a", risk=BreachRisk.IMMINENT)
        eng.record_prediction("svc-a", risk=BreachRisk.HIGH)
        eng.record_prediction("svc-b", risk=BreachRisk.LOW)
        results = eng.identify_imminent_breaches()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_imminent_breaches() == []


# -------------------------------------------------------------------
# rank_by_confidence
# -------------------------------------------------------------------


class TestRankByConfidence:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction("svc-a", confidence_pct=90.0)
        eng.record_prediction("svc-a", confidence_pct=80.0)
        eng.record_prediction("svc-b", confidence_pct=50.0)
        results = eng.rank_by_confidence()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_confidence"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# -------------------------------------------------------------------
# detect_breach_patterns
# -------------------------------------------------------------------


class TestDetectBreachPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_prediction(
                "svc-a",
                risk=BreachRisk.MODERATE,
            )
        eng.record_prediction("svc-b", risk=BreachRisk.LOW)
        results = eng.detect_breach_patterns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["pattern_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_prediction("svc-a", risk=BreachRisk.MODERATE)
        assert eng.detect_breach_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction("svc-a", risk=BreachRisk.IMMINENT)
        eng.record_prediction("svc-a", risk=BreachRisk.HIGH)
        eng.record_prediction("svc-b", risk=BreachRisk.LOW)
        eng.add_threshold("thresh-1")
        report = eng.generate_report()
        assert report.total_predictions == 3
        assert report.total_thresholds == 1
        assert report.by_risk != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_predictions == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction("svc-a")
        eng.add_threshold("thresh-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._thresholds) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_predictions"] == 0
        assert stats["total_thresholds"] == 0
        assert stats["risk_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prediction("svc-a", risk=BreachRisk.IMMINENT)
        eng.record_prediction("svc-b", risk=BreachRisk.LOW)
        eng.add_threshold("t1")
        stats = eng.get_stats()
        assert stats["total_predictions"] == 2
        assert stats["total_thresholds"] == 1
        assert stats["unique_services"] == 2
