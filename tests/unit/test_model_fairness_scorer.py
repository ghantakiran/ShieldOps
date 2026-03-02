"""Tests for shieldops.analytics.model_fairness_scorer — ModelFairnessScorer."""

from __future__ import annotations

from shieldops.analytics.model_fairness_scorer import (
    FairnessAnalysis,
    FairnessLevel,
    FairnessMetric,
    FairnessRecord,
    FairnessReport,
    ModelFairnessScorer,
    ProtectedAttribute,
)


def _engine(**kw) -> ModelFairnessScorer:
    return ModelFairnessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_demographic_parity(self):
        assert FairnessMetric.DEMOGRAPHIC_PARITY == "demographic_parity"

    def test_metric_equalized_odds(self):
        assert FairnessMetric.EQUALIZED_ODDS == "equalized_odds"

    def test_metric_equal_opportunity(self):
        assert FairnessMetric.EQUAL_OPPORTUNITY == "equal_opportunity"

    def test_metric_calibration(self):
        assert FairnessMetric.CALIBRATION == "calibration"

    def test_metric_predictive_parity(self):
        assert FairnessMetric.PREDICTIVE_PARITY == "predictive_parity"

    def test_attribute_gender(self):
        assert ProtectedAttribute.GENDER == "gender"

    def test_attribute_race(self):
        assert ProtectedAttribute.RACE == "race"

    def test_attribute_age(self):
        assert ProtectedAttribute.AGE == "age"

    def test_attribute_disability(self):
        assert ProtectedAttribute.DISABILITY == "disability"

    def test_attribute_religion(self):
        assert ProtectedAttribute.RELIGION == "religion"

    def test_level_excellent(self):
        assert FairnessLevel.EXCELLENT == "excellent"

    def test_level_acceptable(self):
        assert FairnessLevel.ACCEPTABLE == "acceptable"

    def test_level_marginal(self):
        assert FairnessLevel.MARGINAL == "marginal"

    def test_level_poor(self):
        assert FairnessLevel.POOR == "poor"

    def test_level_failing(self):
        assert FairnessLevel.FAILING == "failing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_fairness_record_defaults(self):
        r = FairnessRecord()
        assert r.id
        assert r.model_id == ""
        assert r.fairness_metric == FairnessMetric.DEMOGRAPHIC_PARITY
        assert r.protected_attribute == ProtectedAttribute.GENDER
        assert r.fairness_level == FairnessLevel.ACCEPTABLE
        assert r.fairness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_fairness_analysis_defaults(self):
        a = FairnessAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.fairness_metric == FairnessMetric.DEMOGRAPHIC_PARITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_fairness_report_defaults(self):
        r = FairnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.failing_count == 0
        assert r.avg_fairness_score == 0.0
        assert r.by_metric == {}
        assert r.by_attribute == {}
        assert r.by_level == {}
        assert r.top_violations == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_init(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._fairness_threshold == 0.8
        assert len(eng._records) == 0

    def test_custom_init(self):
        eng = _engine(max_records=500, fairness_threshold=0.9)
        assert eng._max_records == 500
        assert eng._fairness_threshold == 0.9

    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0


# ---------------------------------------------------------------------------
# record_fairness / get_fairness
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_fairness(
            model_id="model-001",
            fairness_metric=FairnessMetric.EQUALIZED_ODDS,
            protected_attribute=ProtectedAttribute.RACE,
            fairness_level=FairnessLevel.POOR,
            fairness_score=0.6,
            service="loan-svc",
            team="fairness-team",
        )
        assert r.model_id == "model-001"
        assert r.fairness_metric == FairnessMetric.EQUALIZED_ODDS
        assert r.protected_attribute == ProtectedAttribute.RACE
        assert r.fairness_score == 0.6

    def test_get_found(self):
        eng = _engine()
        r = eng.record_fairness(model_id="m-001", fairness_score=0.9)
        result = eng.get_fairness(r.id)
        assert result is not None
        assert result.model_id == "m-001"

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_fairness("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_fairness(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_fairness
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001")
        eng.record_fairness(model_id="m-002")
        assert len(eng.list_fairness()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001", fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY)
        eng.record_fairness(model_id="m-002", fairness_metric=FairnessMetric.CALIBRATION)
        results = eng.list_fairness(fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001", fairness_level=FairnessLevel.FAILING)
        eng.record_fairness(model_id="m-002", fairness_level=FairnessLevel.EXCELLENT)
        results = eng.list_fairness(fairness_level=FairnessLevel.FAILING)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001", team="fairness-team")
        eng.record_fairness(model_id="m-002", team="data-team")
        results = eng.list_fairness(team="fairness-team")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_fairness(model_id=f"m-{i}")
        assert len(eng.list_fairness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            fairness_metric=FairnessMetric.EQUALIZED_ODDS,
            analysis_score=60.0,
            threshold=80.0,
            breached=True,
            description="fairness violation",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 60.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.fairness_metric == FairnessMetric.DEMOGRAPHIC_PARITY
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_fairness(
            model_id="m-001", fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY, fairness_score=0.9
        )
        eng.record_fairness(
            model_id="m-002", fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY, fairness_score=0.7
        )
        result = eng.analyze_distribution()
        assert "demographic_parity" in result
        assert result["demographic_parity"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(fairness_threshold=0.8)
        eng.record_fairness(model_id="m-001", fairness_score=0.6)
        eng.record_fairness(model_id="m-002", fairness_score=0.9)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_ascending(self):
        eng = _engine(fairness_threshold=0.8)
        eng.record_fairness(model_id="m-001", fairness_score=0.5)
        eng.record_fairness(model_id="m-002", fairness_score=0.3)
        results = eng.identify_severe_drifts()
        assert len(results) == 2
        assert results[0]["fairness_score"] == 0.3

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001", fairness_score=0.9)
        eng.record_fairness(model_id="m-002", fairness_score=0.4)
        results = eng.rank_by_severity()
        assert len(results) == 2
        assert results[0]["model_id"] == "m-002"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(model_id="m-001", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(fairness_threshold=0.8)
        eng.record_fairness(
            model_id="m-001",
            fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY,
            protected_attribute=ProtectedAttribute.GENDER,
            fairness_level=FairnessLevel.POOR,
            fairness_score=0.5,
        )
        report = eng.generate_report()
        assert isinstance(report, FairnessReport)
        assert report.total_records == 1
        assert report.failing_count == 1
        assert len(report.top_violations) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_fairness(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["metric_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_fairness(
            model_id="m-001",
            fairness_metric=FairnessMetric.DEMOGRAPHIC_PARITY,
            service="loan-svc",
            team="fairness-team",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_models"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_fairness(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
