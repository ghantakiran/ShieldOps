"""Tests for shieldops.analytics.incident_recurrence_predictor."""

from __future__ import annotations

from shieldops.analytics.incident_recurrence_predictor import (
    IncidentRecurrencePredictor,
    PredictionConfidence,
    PreventionStrategy,
    RecurrenceAnalysis,
    RecurrencePattern,
    RecurrencePrediction,
    RecurrencePredictionReport,
)


def _engine(**kw) -> IncidentRecurrencePredictor:
    return IncidentRecurrencePredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_pattern_periodic(self):
        assert RecurrencePattern.PERIODIC == "periodic"

    def test_pattern_random(self):
        assert RecurrencePattern.RANDOM == "random"

    def test_pattern_triggered(self):
        assert RecurrencePattern.TRIGGERED == "triggered"

    def test_pattern_seasonal(self):
        assert RecurrencePattern.SEASONAL == "seasonal"

    def test_pattern_trending(self):
        assert RecurrencePattern.TRENDING == "trending"

    def test_confidence_high(self):
        assert PredictionConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert PredictionConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert PredictionConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert PredictionConfidence.UNCERTAIN == "uncertain"

    def test_confidence_insufficient_data(self):
        assert PredictionConfidence.INSUFFICIENT_DATA == "insufficient_data"

    def test_strategy_root_cause_fix(self):
        assert PreventionStrategy.ROOT_CAUSE_FIX == "root_cause_fix"

    def test_strategy_automation(self):
        assert PreventionStrategy.AUTOMATION == "automation"

    def test_strategy_monitoring(self):
        assert PreventionStrategy.MONITORING == "monitoring"

    def test_strategy_process_change(self):
        assert PreventionStrategy.PROCESS_CHANGE == "process_change"

    def test_strategy_architecture(self):
        assert PreventionStrategy.ARCHITECTURE == "architecture"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_recurrence_prediction_defaults(self):
        r = RecurrencePrediction()
        assert r.id
        assert r.recurrence_pattern == RecurrencePattern.PERIODIC
        assert r.prediction_confidence == PredictionConfidence.MEDIUM
        assert r.prevention_strategy == PreventionStrategy.ROOT_CAUSE_FIX
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_recurrence_analysis_defaults(self):
        a = RecurrenceAnalysis()
        assert a.id
        assert a.recurrence_pattern == RecurrencePattern.PERIODIC
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_recurrence_prediction_report_defaults(self):
        r = RecurrencePredictionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_pattern == {}
        assert r.by_confidence == {}
        assert r.by_strategy == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=7000)
        assert eng._max_records == 7000

    def test_custom_threshold(self):
        eng = _engine(threshold=70.0)
        assert eng._threshold == 70.0


# ---------------------------------------------------------------------------
# record_prediction / get_prediction
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            service="alerts-svc",
            recurrence_pattern=RecurrencePattern.SEASONAL,
            prediction_confidence=PredictionConfidence.HIGH,
            prevention_strategy=PreventionStrategy.AUTOMATION,
            score=85.0,
            team="sre",
        )
        assert r.service == "alerts-svc"
        assert r.recurrence_pattern == RecurrencePattern.SEASONAL
        assert r.prediction_confidence == PredictionConfidence.HIGH
        assert r.prevention_strategy == PreventionStrategy.AUTOMATION
        assert r.score == 85.0
        assert r.team == "sre"

    def test_record_stored(self):
        eng = _engine()
        eng.record_prediction(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_prediction(service="svc-a", score=66.0)
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.score == 66.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(service="svc-a")
        eng.record_prediction(service="svc-b")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", recurrence_pattern=RecurrencePattern.PERIODIC)
        eng.record_prediction(service="svc-b", recurrence_pattern=RecurrencePattern.RANDOM)
        results = eng.list_predictions(recurrence_pattern=RecurrencePattern.PERIODIC)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", prediction_confidence=PredictionConfidence.HIGH)
        eng.record_prediction(service="svc-b", prediction_confidence=PredictionConfidence.LOW)
        results = eng.list_predictions(prediction_confidence=PredictionConfidence.HIGH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", team="sre")
        eng.record_prediction(service="svc-b", team="security")
        assert len(eng.list_predictions(team="sre")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(service=f"svc-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            recurrence_pattern=RecurrencePattern.TRENDING,
            analysis_score=45.0,
            threshold=50.0,
            breached=True,
            description="trending recurrence",
        )
        assert a.recurrence_pattern == RecurrencePattern.TRENDING
        assert a.analysis_score == 45.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(
            service="s1", recurrence_pattern=RecurrencePattern.PERIODIC, score=80.0
        )
        eng.record_prediction(
            service="s2", recurrence_pattern=RecurrencePattern.PERIODIC, score=60.0
        )
        result = eng.analyze_distribution()
        assert "periodic" in result
        assert result["periodic"]["count"] == 2
        assert result["periodic"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_recurrence_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_prediction(service="svc-a", score=60.0)
        eng.record_prediction(service="svc-b", score=90.0)
        results = eng.identify_recurrence_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_prediction(service="svc-a", score=55.0)
        eng.record_prediction(service="svc-b", score=35.0)
        results = eng.identify_recurrence_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_prediction(service="svc-a", score=90.0)
        eng.record_prediction(service="svc-b", score=40.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_prediction(
            service="svc-a",
            recurrence_pattern=RecurrencePattern.TRIGGERED,
            prediction_confidence=PredictionConfidence.LOW,
            prevention_strategy=PreventionStrategy.MONITORING,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RecurrencePredictionReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "well-managed" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_prediction(
            service="svc-a",
            recurrence_pattern=RecurrencePattern.PERIODIC,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "periodic" in stats["pattern_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(service=f"svc-{i}")
        assert len(eng._records) == 3
