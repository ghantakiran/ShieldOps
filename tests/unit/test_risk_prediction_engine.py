"""Tests for shieldops.analytics.risk_prediction_engine — RiskPredictionEngine."""

from __future__ import annotations

from shieldops.analytics.risk_prediction_engine import (
    PredictionAnalysis,
    PredictionConfidence,
    PredictionModel,
    PredictionRecord,
    PredictionReport,
    RiskHorizon,
    RiskPredictionEngine,
)


def _engine(**kw) -> RiskPredictionEngine:
    return RiskPredictionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_predictionmodel_regression(self):
        assert PredictionModel.REGRESSION == "regression"

    def test_predictionmodel_classification(self):
        assert PredictionModel.CLASSIFICATION == "classification"

    def test_predictionmodel_time_series(self):
        assert PredictionModel.TIME_SERIES == "time_series"

    def test_predictionmodel_ensemble(self):
        assert PredictionModel.ENSEMBLE == "ensemble"

    def test_predictionmodel_bayesian(self):
        assert PredictionModel.BAYESIAN == "bayesian"

    def test_riskhorizon_immediate(self):
        assert RiskHorizon.IMMEDIATE == "immediate"

    def test_riskhorizon_short_term(self):
        assert RiskHorizon.SHORT_TERM == "short_term"

    def test_riskhorizon_medium_term(self):
        assert RiskHorizon.MEDIUM_TERM == "medium_term"

    def test_riskhorizon_long_term(self):
        assert RiskHorizon.LONG_TERM == "long_term"

    def test_riskhorizon_strategic(self):
        assert RiskHorizon.STRATEGIC == "strategic"

    def test_predictionconfidence_very_high(self):
        assert PredictionConfidence.VERY_HIGH == "very_high"

    def test_predictionconfidence_high(self):
        assert PredictionConfidence.HIGH == "high"

    def test_predictionconfidence_medium(self):
        assert PredictionConfidence.MEDIUM == "medium"

    def test_predictionconfidence_low(self):
        assert PredictionConfidence.LOW == "low"

    def test_predictionconfidence_very_low(self):
        assert PredictionConfidence.VERY_LOW == "very_low"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_predictionrecord_defaults(self):
        r = PredictionRecord()
        assert r.id
        assert r.prediction_name == ""
        assert r.risk_forecast == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_predictionanalysis_defaults(self):
        c = PredictionAnalysis()
        assert c.id
        assert c.prediction_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_predictionreport_defaults(self):
        r = PredictionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_risk_forecast == 0
        assert r.by_model == {}
        assert r.by_horizon == {}
        assert r.by_confidence == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_prediction
# ---------------------------------------------------------------------------


class TestRecordPrediction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            prediction_name="test-item",
            prediction_model=PredictionModel.CLASSIFICATION,
            risk_forecast=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.prediction_name == "test-item"
        assert r.risk_forecast == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(prediction_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_prediction
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(prediction_name="test-item")
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.prediction_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(prediction_name="ITEM-001")
        eng.record_prediction(prediction_name="ITEM-002")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_prediction_model(self):
        eng = _engine()
        eng.record_prediction(
            prediction_name="ITEM-001", prediction_model=PredictionModel.REGRESSION
        )
        eng.record_prediction(
            prediction_name="ITEM-002", prediction_model=PredictionModel.CLASSIFICATION
        )
        results = eng.list_predictions(prediction_model=PredictionModel.REGRESSION)
        assert len(results) == 1

    def test_filter_by_risk_horizon(self):
        eng = _engine()
        eng.record_prediction(prediction_name="ITEM-001", risk_horizon=RiskHorizon.IMMEDIATE)
        eng.record_prediction(prediction_name="ITEM-002", risk_horizon=RiskHorizon.SHORT_TERM)
        results = eng.list_predictions(risk_horizon=RiskHorizon.IMMEDIATE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_prediction(prediction_name="ITEM-001", team="security")
        eng.record_prediction(prediction_name="ITEM-002", team="platform")
        results = eng.list_predictions(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(prediction_name=f"ITEM-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            prediction_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.prediction_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(prediction_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_model_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(
            prediction_name="ITEM-001",
            prediction_model=PredictionModel.REGRESSION,
            risk_forecast=90.0,
        )
        eng.record_prediction(
            prediction_name="ITEM-002",
            prediction_model=PredictionModel.REGRESSION,
            risk_forecast=70.0,
        )
        result = eng.analyze_model_distribution()
        assert "regression" in result
        assert result["regression"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_model_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_predictions
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(forecast_confidence_threshold=65.0)
        eng.record_prediction(prediction_name="ITEM-001", risk_forecast=30.0)
        eng.record_prediction(prediction_name="ITEM-002", risk_forecast=90.0)
        results = eng.identify_low_confidence_predictions()
        assert len(results) == 1
        assert results[0]["prediction_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(forecast_confidence_threshold=65.0)
        eng.record_prediction(prediction_name="ITEM-001", risk_forecast=50.0)
        eng.record_prediction(prediction_name="ITEM-002", risk_forecast=30.0)
        results = eng.identify_low_confidence_predictions()
        assert len(results) == 2
        assert results[0]["risk_forecast"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_predictions() == []


# ---------------------------------------------------------------------------
# rank_by_risk_forecast
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_prediction(prediction_name="ITEM-001", service="auth-svc", risk_forecast=90.0)
        eng.record_prediction(prediction_name="ITEM-002", service="api-gw", risk_forecast=50.0)
        results = eng.rank_by_risk_forecast()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_forecast() == []


# ---------------------------------------------------------------------------
# detect_forecast_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(prediction_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(prediction_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(prediction_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(prediction_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(prediction_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_forecast_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(forecast_confidence_threshold=65.0)
        eng.record_prediction(prediction_name="test-item", risk_forecast=30.0)
        report = eng.generate_report()
        assert isinstance(report, PredictionReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(prediction_name="ITEM-001")
        eng.add_analysis(prediction_name="ITEM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_prediction(
            prediction_name="ITEM-001",
            prediction_model=PredictionModel.REGRESSION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
