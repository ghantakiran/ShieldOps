"""Tests for shieldops.analytics.response_time_predictor — ResponseTimePredictor."""

from __future__ import annotations

from shieldops.analytics.response_time_predictor import (
    IncidentComplexity,
    PredictionAccuracy,
    PredictionModel,
    ResponseTimePrediction,
    ResponseTimePredictionAnalysis,
    ResponseTimePredictionReport,
    ResponseTimePredictor,
)


def _engine(**kw) -> ResponseTimePredictor:
    return ResponseTimePredictor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert IncidentComplexity.CRITICAL == "critical"

    def test_e1_v2(self):
        assert IncidentComplexity.HIGH == "high"

    def test_e1_v3(self):
        assert IncidentComplexity.MEDIUM == "medium"

    def test_e1_v4(self):
        assert IncidentComplexity.LOW == "low"

    def test_e1_v5(self):
        assert IncidentComplexity.TRIVIAL == "trivial"

    def test_e2_v1(self):
        assert PredictionModel.HISTORICAL == "historical"

    def test_e2_v2(self):
        assert PredictionModel.ML_REGRESSION == "ml_regression"

    def test_e2_v3(self):
        assert PredictionModel.BAYESIAN == "bayesian"

    def test_e2_v4(self):
        assert PredictionModel.ENSEMBLE == "ensemble"

    def test_e2_v5(self):
        assert PredictionModel.RULE_BASED == "rule_based"

    def test_e3_v1(self):
        assert PredictionAccuracy.EXCELLENT == "excellent"

    def test_e3_v2(self):
        assert PredictionAccuracy.GOOD == "good"

    def test_e3_v3(self):
        assert PredictionAccuracy.FAIR == "fair"

    def test_e3_v4(self):
        assert PredictionAccuracy.POOR == "poor"

    def test_e3_v5(self):
        assert PredictionAccuracy.UNRELIABLE == "unreliable"


class TestModels:
    def test_rec(self):
        r = ResponseTimePrediction()
        assert r.id and r.prediction_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ResponseTimePredictionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ResponseTimePredictionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_prediction(
            prediction_id="t",
            incident_complexity=IncidentComplexity.HIGH,
            prediction_model=PredictionModel.ML_REGRESSION,
            prediction_accuracy=PredictionAccuracy.GOOD,
            prediction_score=92.0,
            service="s",
            team="t",
        )
        assert r.prediction_id == "t" and r.prediction_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(prediction_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(prediction_id="t")
        assert eng.get_prediction(r.id) is not None

    def test_not_found(self):
        assert _engine().get_prediction("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a")
        eng.record_prediction(prediction_id="b")
        assert len(eng.list_predictions()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a", incident_complexity=IncidentComplexity.CRITICAL)
        eng.record_prediction(prediction_id="b", incident_complexity=IncidentComplexity.HIGH)
        assert len(eng.list_predictions(incident_complexity=IncidentComplexity.CRITICAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a", prediction_model=PredictionModel.HISTORICAL)
        eng.record_prediction(prediction_id="b", prediction_model=PredictionModel.ML_REGRESSION)
        assert len(eng.list_predictions(prediction_model=PredictionModel.HISTORICAL)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a", team="x")
        eng.record_prediction(prediction_id="b", team="y")
        assert len(eng.list_predictions(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(prediction_id=f"t-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            prediction_id="t",
            incident_complexity=IncidentComplexity.HIGH,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(prediction_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="a",
            incident_complexity=IncidentComplexity.CRITICAL,
            prediction_score=90.0,
        )
        eng.record_prediction(
            prediction_id="b",
            incident_complexity=IncidentComplexity.CRITICAL,
            prediction_score=70.0,
        )
        assert "critical" in eng.analyze_complexity_distribution()

    def test_empty(self):
        assert _engine().analyze_complexity_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(prediction_threshold=80.0)
        eng.record_prediction(prediction_id="a", prediction_score=60.0)
        eng.record_prediction(prediction_id="b", prediction_score=90.0)
        assert len(eng.identify_prediction_gaps()) == 1

    def test_sorted(self):
        eng = _engine(prediction_threshold=80.0)
        eng.record_prediction(prediction_id="a", prediction_score=50.0)
        eng.record_prediction(prediction_id="b", prediction_score=30.0)
        assert len(eng.identify_prediction_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a", service="s1", prediction_score=80.0)
        eng.record_prediction(prediction_id="b", service="s2", prediction_score=60.0)
        assert eng.rank_by_prediction()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_prediction() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(prediction_id="t", analysis_score=float(v))
        assert eng.detect_prediction_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(prediction_id="t", analysis_score=float(v))
        assert eng.detect_prediction_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_prediction_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_prediction(prediction_id="t", prediction_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(prediction_id="t")
        eng.add_analysis(prediction_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_prediction(prediction_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_prediction(prediction_id="a")
        eng.record_prediction(prediction_id="b")
        eng.add_analysis(prediction_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
