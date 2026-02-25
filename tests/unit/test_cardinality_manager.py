"""Tests for shieldops.observability.cardinality_manager — MetricCardinalityManager."""

from __future__ import annotations

from shieldops.observability.cardinality_manager import (
    CardinalityLevel,
    CardinalityRecord,
    CardinalityReport,
    CardinalityRule,
    LabelAction,
    MetricCardinalityManager,
    MetricType,
)


def _engine(**kw) -> MetricCardinalityManager:
    return MetricCardinalityManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_normal(self):
        assert CardinalityLevel.NORMAL == "normal"

    def test_level_elevated(self):
        assert CardinalityLevel.ELEVATED == "elevated"

    def test_level_high(self):
        assert CardinalityLevel.HIGH == "high"

    def test_level_critical(self):
        assert CardinalityLevel.CRITICAL == "critical"

    def test_level_explosive(self):
        assert CardinalityLevel.EXPLOSIVE == "explosive"

    def test_action_keep(self):
        assert LabelAction.KEEP == "keep"

    def test_action_aggregate(self):
        assert LabelAction.AGGREGATE == "aggregate"

    def test_action_drop(self):
        assert LabelAction.DROP == "drop"

    def test_action_sample(self):
        assert LabelAction.SAMPLE == "sample"

    def test_action_relabel(self):
        assert LabelAction.RELABEL == "relabel"

    def test_type_counter(self):
        assert MetricType.COUNTER == "counter"

    def test_type_gauge(self):
        assert MetricType.GAUGE == "gauge"

    def test_type_histogram(self):
        assert MetricType.HISTOGRAM == "histogram"

    def test_type_summary(self):
        assert MetricType.SUMMARY == "summary"

    def test_type_untyped(self):
        assert MetricType.UNTYPED == "untyped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cardinality_record_defaults(self):
        r = CardinalityRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.metric_type == MetricType.COUNTER
        assert r.cardinality == 0
        assert r.label_count == 0
        assert r.level == CardinalityLevel.NORMAL
        assert r.labels == []
        assert r.details == ""
        assert r.created_at > 0

    def test_cardinality_rule_defaults(self):
        r = CardinalityRule()
        assert r.id
        assert r.metric_pattern == ""
        assert r.label_name == ""
        assert r.action == LabelAction.KEEP
        assert r.reason == ""
        assert r.created_at > 0

    def test_cardinality_report_defaults(self):
        r = CardinalityReport()
        assert r.total_metrics == 0
        assert r.total_rules == 0
        assert r.avg_cardinality == 0.0
        assert r.by_level == {}
        assert r.by_type == {}
        assert r.high_cardinality_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------


class TestRecordMetric:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metric(
            metric_name="http_requests_total",
            metric_type=MetricType.COUNTER,
            cardinality=500,
            label_count=3,
            labels=["method", "status", "path"],
        )
        assert r.metric_name == "http_requests_total"
        assert r.metric_type == MetricType.COUNTER
        assert r.cardinality == 500
        assert r.level == CardinalityLevel.NORMAL

    def test_auto_level_high(self):
        eng = _engine(max_cardinality_threshold=1000)
        r = eng.record_metric(metric_name="m1", cardinality=1500)
        assert r.level == CardinalityLevel.HIGH

    def test_auto_level_explosive(self):
        eng = _engine(max_cardinality_threshold=1000)
        r = eng.record_metric(metric_name="m1", cardinality=15000)
        assert r.level == CardinalityLevel.EXPLOSIVE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metric(metric_name=f"m{i}", cardinality=100)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------


class TestGetMetric:
    def test_found(self):
        eng = _engine()
        r = eng.record_metric(metric_name="m1", cardinality=100)
        result = eng.get_metric(r.id)
        assert result is not None
        assert result.metric_name == "m1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metric("nonexistent") is None


# ---------------------------------------------------------------------------
# list_metrics
# ---------------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", cardinality=100)
        eng.record_metric(metric_name="m2", cardinality=200)
        assert len(eng.list_metrics()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", cardinality=100)
        eng.record_metric(metric_name="m2", cardinality=200)
        results = eng.list_metrics(metric_name="m1")
        assert len(results) == 1
        assert results[0].metric_name == "m1"

    def test_filter_by_level(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=100)
        eng.record_metric(metric_name="m2", cardinality=1500)
        results = eng.list_metrics(level=CardinalityLevel.HIGH)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            metric_pattern="http_*",
            label_name="path",
            action=LabelAction.AGGREGATE,
            reason="High cardinality path label",
        )
        assert r.metric_pattern == "http_*"
        assert r.label_name == "path"
        assert r.action == LabelAction.AGGREGATE
        assert r.reason == "High cardinality path label"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_rule(metric_pattern=f"m{i}", label_name="l")
        assert len(eng._rules) == 3


# ---------------------------------------------------------------------------
# detect_high_cardinality
# ---------------------------------------------------------------------------


class TestDetectHighCardinality:
    def test_finds_high(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=500)
        eng.record_metric(metric_name="m2", cardinality=5000, labels=["a", "b"])
        results = eng.detect_high_cardinality()
        assert len(results) == 1
        assert results[0]["metric_name"] == "m2"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_high_cardinality() == []


# ---------------------------------------------------------------------------
# recommend_label_actions
# ---------------------------------------------------------------------------


class TestRecommendLabelActions:
    def test_high_cardinality(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=2000, labels=["method", "path"])
        results = eng.recommend_label_actions("m1")
        assert len(results) == 2
        assert results[0]["recommended_action"] == LabelAction.AGGREGATE.value

    def test_explosive_cardinality(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=50000, labels=["user_id"])
        results = eng.recommend_label_actions("m1")
        assert results[0]["recommended_action"] == LabelAction.DROP.value

    def test_no_metric(self):
        eng = _engine()
        assert eng.recommend_label_actions("unknown") == []


# ---------------------------------------------------------------------------
# analyze_growth_trend
# ---------------------------------------------------------------------------


class TestAnalyzeGrowthTrend:
    def test_growing(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", cardinality=100)
        eng.record_metric(metric_name="m1", cardinality=200)
        results = eng.analyze_growth_trend()
        assert len(results) == 1
        assert results[0]["growth_rate_pct"] == 100.0

    def test_single_sample(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", cardinality=100)
        results = eng.analyze_growth_trend()
        assert results[0]["growth_rate_pct"] == 0.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_growth_trend() == []


# ---------------------------------------------------------------------------
# identify_label_culprits
# ---------------------------------------------------------------------------


class TestIdentifyLabelCulprits:
    def test_with_data(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=5000, labels=["path", "method"])
        eng.record_metric(metric_name="m2", cardinality=500, labels=["method"])
        results = eng.identify_label_culprits()
        assert len(results) == 2
        path_entry = next(r for r in results if r["label"] == "path")
        assert path_entry["high_cardinality_occurrences"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_label_culprits() == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=5000)
        eng.record_metric(metric_name="m2", cardinality=100)
        eng.add_rule(metric_pattern="m*", label_name="l", action=LabelAction.DROP)
        report = eng.generate_report()
        assert isinstance(report, CardinalityReport)
        assert report.total_metrics == 2
        assert report.total_rules == 1
        assert report.avg_cardinality > 0
        assert report.high_cardinality_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_metrics == 0
        assert "Metric cardinality within acceptable limits" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_metric(metric_name="m1", cardinality=100)
        eng.add_rule(metric_pattern="m*", label_name="l")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_metrics"] == 0
        assert stats["total_rules"] == 0
        assert stats["level_distribution"] == {}
        assert stats["unique_metric_names"] == 0

    def test_populated(self):
        eng = _engine(max_cardinality_threshold=1000)
        eng.record_metric(metric_name="m1", cardinality=500)
        eng.add_rule(metric_pattern="m*", label_name="l")
        stats = eng.get_stats()
        assert stats["total_metrics"] == 1
        assert stats["total_rules"] == 1
        assert stats["max_cardinality_threshold"] == 1000
        assert "elevated" in stats["level_distribution"]
        assert stats["unique_metric_names"] == 1
