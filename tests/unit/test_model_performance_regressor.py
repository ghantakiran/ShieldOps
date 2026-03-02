"""Tests for shieldops.analytics.model_performance_regressor."""

from __future__ import annotations

from shieldops.analytics.model_performance_regressor import (
    ModelPerformanceRegressor,
    PerformanceAnalysis,
    PerformanceMetric,
    PerformanceRecord,
    PerformanceReport,
    RegressionType,
    TrendDirection,
)


def _engine(**kw) -> ModelPerformanceRegressor:
    return ModelPerformanceRegressor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_accuracy(self):
        assert PerformanceMetric.ACCURACY == "accuracy"

    def test_metric_precision(self):
        assert PerformanceMetric.PRECISION == "precision"

    def test_metric_recall(self):
        assert PerformanceMetric.RECALL == "recall"

    def test_metric_f1_score(self):
        assert PerformanceMetric.F1_SCORE == "f1_score"

    def test_metric_auc_roc(self):
        assert PerformanceMetric.AUC_ROC == "auc_roc"

    def test_regression_gradual(self):
        assert RegressionType.GRADUAL == "gradual"

    def test_regression_sudden(self):
        assert RegressionType.SUDDEN == "sudden"

    def test_regression_seasonal(self):
        assert RegressionType.SEASONAL == "seasonal"

    def test_regression_periodic(self):
        assert RegressionType.PERIODIC == "periodic"

    def test_regression_unknown(self):
        assert RegressionType.UNKNOWN == "unknown"

    def test_trend_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_trend_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_trend_degrading(self):
        assert TrendDirection.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_trend_insufficient(self):
        assert TrendDirection.INSUFFICIENT == "insufficient"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_performance_record_defaults(self):
        r = PerformanceRecord()
        assert r.id
        assert r.model_id == ""
        assert r.performance_metric == PerformanceMetric.ACCURACY
        assert r.regression_type == RegressionType.UNKNOWN
        assert r.trend_direction == TrendDirection.STABLE
        assert r.metric_value == 0.0
        assert r.baseline_value == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_performance_analysis_defaults(self):
        a = PerformanceAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.performance_metric == PerformanceMetric.ACCURACY
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_performance_report_defaults(self):
        r = PerformanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.regressed_count == 0
        assert r.avg_metric_value == 0.0
        assert r.by_metric == {}
        assert r.by_regression == {}
        assert r.by_trend == {}
        assert r.top_regressed == []
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
        assert eng._regression_threshold == 0.05

    def test_custom_init(self):
        eng = _engine(max_records=500, regression_threshold=0.1)
        assert eng._max_records == 500
        assert eng._regression_threshold == 0.1

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_performance / get_performance
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_performance(
            model_id="model-001",
            performance_metric=PerformanceMetric.F1_SCORE,
            regression_type=RegressionType.GRADUAL,
            trend_direction=TrendDirection.DEGRADING,
            metric_value=0.82,
            baseline_value=0.90,
            service="ml-svc",
            team="ml-team",
        )
        assert r.model_id == "model-001"
        assert r.performance_metric == PerformanceMetric.F1_SCORE
        assert r.metric_value == 0.82

    def test_get_found(self):
        eng = _engine()
        r = eng.record_performance(model_id="m-001", metric_value=0.85)
        assert eng.get_performance(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_performance("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_performance(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_performances
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_performance(model_id="m-001")
        eng.record_performance(model_id="m-002")
        assert len(eng.list_performances()) == 2

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_performance(model_id="m-001", performance_metric=PerformanceMetric.ACCURACY)
        eng.record_performance(model_id="m-002", performance_metric=PerformanceMetric.RECALL)
        assert len(eng.list_performances(performance_metric=PerformanceMetric.ACCURACY)) == 1

    def test_filter_by_trend(self):
        eng = _engine()
        eng.record_performance(model_id="m-001", trend_direction=TrendDirection.DEGRADING)
        eng.record_performance(model_id="m-002", trend_direction=TrendDirection.IMPROVING)
        assert len(eng.list_performances(trend_direction=TrendDirection.DEGRADING)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_performance(model_id="m-001", team="ml-team")
        eng.record_performance(model_id="m-002", team="data-team")
        assert len(eng.list_performances(team="ml-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_performance(model_id=f"m-{i}")
        assert len(eng.list_performances(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            performance_metric=PerformanceMetric.F1_SCORE,
            analysis_score=75.0,
            threshold=85.0,
            breached=True,
            description="performance regression",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 75.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.performance_metric == PerformanceMetric.ACCURACY
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_performance(
            model_id="m-001",
            performance_metric=PerformanceMetric.ACCURACY,
            metric_value=0.92,
        )
        eng.record_performance(
            model_id="m-002",
            performance_metric=PerformanceMetric.ACCURACY,
            metric_value=0.88,
        )
        result = eng.analyze_distribution()
        assert "accuracy" in result
        assert result["accuracy"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_regression(self):
        eng = _engine(regression_threshold=0.05)
        eng.record_performance(model_id="m-001", metric_value=0.80, baseline_value=0.92)
        eng.record_performance(model_id="m-002", metric_value=0.91, baseline_value=0.92)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_by_regression_descending(self):
        eng = _engine(regression_threshold=0.05)
        eng.record_performance(model_id="m-001", metric_value=0.80, baseline_value=0.95)
        eng.record_performance(model_id="m-002", metric_value=0.70, baseline_value=0.95)
        results = eng.identify_severe_drifts()
        assert results[0]["model_id"] == "m-002"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_performance(model_id="m-001", metric_value=0.95)
        eng.record_performance(model_id="m-002", metric_value=0.70)
        results = eng.rank_by_severity()
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
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(regression_threshold=0.05)
        eng.record_performance(
            model_id="m-001",
            performance_metric=PerformanceMetric.F1_SCORE,
            regression_type=RegressionType.GRADUAL,
            trend_direction=TrendDirection.DEGRADING,
            metric_value=0.75,
            baseline_value=0.90,
        )
        report = eng.generate_report()
        assert isinstance(report, PerformanceReport)
        assert report.total_records == 1
        assert report.regressed_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "stable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_performance(model_id="m-001")
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
        eng.record_performance(
            model_id="m-001",
            performance_metric=PerformanceMetric.ACCURACY,
            team="ml-team",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_performance(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
