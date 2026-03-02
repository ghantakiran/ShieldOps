"""Tests for shieldops.topology.service_health_predictor — ServiceHealthPredictor."""

from __future__ import annotations

from shieldops.topology.service_health_predictor import (
    HealthState,
    PredictionAnalysis,
    PredictionBasis,
    PredictionHorizon,
    PredictionRecord,
    ServiceHealthPredictor,
    ServiceHealthReport,
)


def _engine(**kw) -> ServiceHealthPredictor:
    return ServiceHealthPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_state_healthy(self):
        assert HealthState.HEALTHY == "healthy"

    def test_state_degraded(self):
        assert HealthState.DEGRADED == "degraded"

    def test_state_at_risk(self):
        assert HealthState.AT_RISK == "at_risk"

    def test_state_failing(self):
        assert HealthState.FAILING == "failing"

    def test_state_unknown(self):
        assert HealthState.UNKNOWN == "unknown"

    def test_basis_latency_trend(self):
        assert PredictionBasis.LATENCY_TREND == "latency_trend"

    def test_basis_error_trajectory(self):
        assert PredictionBasis.ERROR_TRAJECTORY == "error_trajectory"

    def test_basis_dependency_signal(self):
        assert PredictionBasis.DEPENDENCY_SIGNAL == "dependency_signal"

    def test_basis_capacity_pressure(self):
        assert PredictionBasis.CAPACITY_PRESSURE == "capacity_pressure"

    def test_basis_anomaly_detection(self):
        assert PredictionBasis.ANOMALY_DETECTION == "anomaly_detection"

    def test_horizon_minutes_15(self):
        assert PredictionHorizon.MINUTES_15 == "minutes_15"

    def test_horizon_hour_1(self):
        assert PredictionHorizon.HOUR_1 == "hour_1"

    def test_horizon_hours_4(self):
        assert PredictionHorizon.HOURS_4 == "hours_4"

    def test_horizon_hours_24(self):
        assert PredictionHorizon.HOURS_24 == "hours_24"

    def test_horizon_days_7(self):
        assert PredictionHorizon.DAYS_7 == "days_7"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_prediction_record_defaults(self):
        r = PredictionRecord()
        assert r.id
        assert r.service_name == ""
        assert r.health_state == HealthState.HEALTHY
        assert r.prediction_basis == PredictionBasis.LATENCY_TREND
        assert r.prediction_horizon == PredictionHorizon.MINUTES_15
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_prediction_analysis_defaults(self):
        a = PredictionAnalysis()
        assert a.id
        assert a.service_name == ""
        assert a.health_state == HealthState.HEALTHY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_service_health_report_defaults(self):
        r = ServiceHealthReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_state == {}
        assert r.by_basis == {}
        assert r.by_horizon == {}
        assert r.top_at_risk == []
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
            service_name="api-gateway",
            health_state=HealthState.DEGRADED,
            prediction_basis=PredictionBasis.ERROR_TRAJECTORY,
            prediction_horizon=PredictionHorizon.HOUR_1,
            confidence_score=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.service_name == "api-gateway"
        assert r.health_state == HealthState.DEGRADED
        assert r.prediction_basis == PredictionBasis.ERROR_TRAJECTORY
        assert r.prediction_horizon == PredictionHorizon.HOUR_1
        assert r.confidence_score == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_prediction
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(
            service_name="api-gateway",
            health_state=HealthState.AT_RISK,
        )
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.health_state == HealthState.AT_RISK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(service_name="svc-1")
        eng.record_prediction(service_name="svc-2")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_state(self):
        eng = _engine()
        eng.record_prediction(
            service_name="svc-1",
            health_state=HealthState.DEGRADED,
        )
        eng.record_prediction(
            service_name="svc-2",
            health_state=HealthState.HEALTHY,
        )
        results = eng.list_predictions(
            health_state=HealthState.DEGRADED,
        )
        assert len(results) == 1

    def test_filter_by_basis(self):
        eng = _engine()
        eng.record_prediction(
            service_name="svc-1",
            prediction_basis=PredictionBasis.ERROR_TRAJECTORY,
        )
        eng.record_prediction(
            service_name="svc-2",
            prediction_basis=PredictionBasis.CAPACITY_PRESSURE,
        )
        results = eng.list_predictions(
            prediction_basis=PredictionBasis.ERROR_TRAJECTORY,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_prediction(service_name="svc-1", team="sre")
        eng.record_prediction(service_name="svc-2", team="platform")
        results = eng.list_predictions(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(service_name=f"svc-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            service_name="api-gateway",
            health_state=HealthState.FAILING,
            analysis_score=35.0,
            threshold=80.0,
            breached=True,
            description="Service health degrading rapidly",
        )
        assert a.service_name == "api-gateway"
        assert a.health_state == HealthState.FAILING
        assert a.analysis_score == 35.0
        assert a.threshold == 80.0
        assert a.breached is True
        assert a.description == "Service health degrading rapidly"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(service_name=f"svc-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_prediction_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePredictionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(
            service_name="svc-1",
            health_state=HealthState.DEGRADED,
            confidence_score=40.0,
        )
        eng.record_prediction(
            service_name="svc-2",
            health_state=HealthState.DEGRADED,
            confidence_score=50.0,
        )
        result = eng.analyze_prediction_distribution()
        assert "degraded" in result
        assert result["degraded"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_prediction_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_predictions
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidencePredictions:
    def test_detects_low_confidence(self):
        eng = _engine(prediction_confidence_threshold=80.0)
        eng.record_prediction(
            service_name="svc-1",
            confidence_score=50.0,
        )
        eng.record_prediction(
            service_name="svc-2",
            confidence_score=90.0,
        )
        results = eng.identify_low_confidence_predictions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_predictions() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_prediction(
            service_name="svc-1",
            service="api-gateway",
            confidence_score=90.0,
        )
        eng.record_prediction(
            service_name="svc-2",
            service="payments",
            confidence_score=30.0,
        )
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_confidence_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_prediction_trends
# ---------------------------------------------------------------------------


class TestDetectPredictionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                service_name="svc-1",
                analysis_score=50.0,
            )
        result = eng.detect_prediction_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(service_name="svc-1", analysis_score=30.0)
        eng.add_analysis(service_name="svc-2", analysis_score=30.0)
        eng.add_analysis(service_name="svc-3", analysis_score=80.0)
        eng.add_analysis(service_name="svc-4", analysis_score=80.0)
        result = eng.detect_prediction_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_prediction_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(prediction_confidence_threshold=80.0)
        eng.record_prediction(
            service_name="api-gateway",
            health_state=HealthState.DEGRADED,
            prediction_basis=PredictionBasis.ERROR_TRAJECTORY,
            prediction_horizon=PredictionHorizon.HOUR_1,
            confidence_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceHealthReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_at_risk) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(service_name="svc-1")
        eng.add_analysis(service_name="svc-1")
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
        assert stats["state_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prediction(
            service_name="api-gateway",
            health_state=HealthState.DEGRADED,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "degraded" in stats["state_distribution"]
