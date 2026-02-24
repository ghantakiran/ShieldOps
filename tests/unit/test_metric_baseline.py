"""Tests for shieldops.observability.metric_baseline — MetricBaselineManager.

Covers BaselineStrategy, DeviationSeverity, and MetricType enums,
MetricBaseline / DeviationEvent / BaselineReport models, and all
MetricBaselineManager operations including baseline creation, deviation
detection, auto-update, stale identification, accuracy calculation,
and report generation.
"""

from __future__ import annotations

from shieldops.observability.metric_baseline import (
    BaselineReport,
    BaselineStrategy,
    DeviationEvent,
    DeviationSeverity,
    MetricBaseline,
    MetricBaselineManager,
    MetricType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> MetricBaselineManager:
    return MetricBaselineManager(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of all three enums."""

    # -- BaselineStrategy (5 members) -------------------------------

    def test_strategy_static(self):
        assert BaselineStrategy.STATIC == "static"

    def test_strategy_rolling_average(self):
        assert BaselineStrategy.ROLLING_AVERAGE == "rolling_average"

    def test_strategy_percentile(self):
        assert BaselineStrategy.PERCENTILE == "percentile"

    def test_strategy_seasonal(self):
        assert BaselineStrategy.SEASONAL == "seasonal"

    def test_strategy_adaptive(self):
        assert BaselineStrategy.ADAPTIVE == "adaptive"

    # -- DeviationSeverity (5 members) ------------------------------

    def test_severity_normal(self):
        assert DeviationSeverity.NORMAL == "normal"

    def test_severity_minor(self):
        assert DeviationSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert DeviationSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert DeviationSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert DeviationSeverity.CRITICAL == "critical"

    # -- MetricType (5 members) -------------------------------------

    def test_type_latency(self):
        assert MetricType.LATENCY == "latency"

    def test_type_error_rate(self):
        assert MetricType.ERROR_RATE == "error_rate"

    def test_type_throughput(self):
        assert MetricType.THROUGHPUT == "throughput"

    def test_type_cpu(self):
        assert MetricType.CPU == "cpu"

    def test_type_memory(self):
        assert MetricType.MEMORY == "memory"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_metric_baseline_defaults(self):
        b = MetricBaseline()
        assert b.id
        assert b.service_name == ""
        assert b.metric_name == ""
        assert b.metric_type == MetricType.LATENCY
        assert b.strategy == BaselineStrategy.STATIC
        assert b.baseline_value == 0.0
        assert b.upper_bound == 0.0
        assert b.lower_bound == 0.0
        assert b.sample_count == 0
        assert b.last_updated > 0
        assert b.created_at > 0

    def test_deviation_event_defaults(self):
        d = DeviationEvent()
        assert d.id
        assert d.baseline_id == ""
        assert d.metric_value == 0.0
        assert d.deviation_pct == 0.0
        assert d.severity == DeviationSeverity.NORMAL
        assert d.detected_at > 0

    def test_baseline_report_defaults(self):
        r = BaselineReport()
        assert r.total_baselines == 0
        assert r.total_deviations == 0
        assert r.avg_deviation_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_severity == {}
        assert r.stale_baselines == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# CreateBaseline
# ===========================================================================


class TestCreateBaseline:
    """Test MetricBaselineManager.create_baseline."""

    def test_basic_creation(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="p99_latency",
            metric_type=MetricType.LATENCY,
            strategy=BaselineStrategy.ROLLING_AVERAGE,
            baseline_value=120.0,
            upper_bound=200.0,
            lower_bound=50.0,
        )
        assert b.id
        assert b.service_name == "api"
        assert b.metric_name == "p99_latency"
        assert b.baseline_value == 120.0
        assert b.upper_bound == 200.0
        assert b.lower_bound == 50.0

    def test_eviction_on_overflow(self):
        eng = _engine(max_baselines=2)
        eng.create_baseline(
            service_name="a",
            metric_name="cpu",
        )
        eng.create_baseline(
            service_name="b",
            metric_name="mem",
        )
        b3 = eng.create_baseline(
            service_name="c",
            metric_name="lat",
        )
        items = eng.list_baselines(limit=100)
        assert len(items) == 2
        assert items[-1].id == b3.id

    def test_default_strategy(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="err_rate",
        )
        assert b.strategy == BaselineStrategy.STATIC


# ===========================================================================
# GetBaseline
# ===========================================================================


class TestGetBaseline:
    """Test MetricBaselineManager.get_baseline."""

    def test_found(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        assert eng.get_baseline(b.id) is b

    def test_not_found(self):
        eng = _engine()
        assert eng.get_baseline("missing") is None


# ===========================================================================
# ListBaselines
# ===========================================================================


class TestListBaselines:
    """Test MetricBaselineManager.list_baselines."""

    def test_all(self):
        eng = _engine()
        eng.create_baseline(
            service_name="a",
            metric_name="lat",
        )
        eng.create_baseline(
            service_name="b",
            metric_name="cpu",
        )
        assert len(eng.list_baselines()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        eng.create_baseline(
            service_name="web",
            metric_name="lat",
        )
        results = eng.list_baselines(service_name="api")
        assert len(results) == 1
        assert results[0].service_name == "api"

    def test_filter_by_type(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
            metric_type=MetricType.LATENCY,
        )
        eng.create_baseline(
            service_name="api",
            metric_name="cpu",
            metric_type=MetricType.CPU,
        )
        results = eng.list_baselines(
            metric_type=MetricType.CPU,
        )
        assert len(results) == 1
        assert results[0].metric_type == MetricType.CPU

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_baseline(
                service_name=f"svc-{i}",
                metric_name="lat",
            )
        assert len(eng.list_baselines(limit=3)) == 3


# ===========================================================================
# RecordMetricValue
# ===========================================================================


class TestRecordMetricValue:
    """Test MetricBaselineManager.record_metric_value."""

    def test_records_value(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.record_metric_value(b.id, 110.0)
        assert dev is not None
        assert b.sample_count == 1

    def test_missing_baseline(self):
        eng = _engine()
        assert eng.record_metric_value("nope", 42.0) is None

    def test_normal_value_no_stored_deviation(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.record_metric_value(b.id, 101.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.NORMAL


# ===========================================================================
# DetectDeviation
# ===========================================================================


class TestDetectDeviation:
    """Test MetricBaselineManager.detect_deviation."""

    def test_normal(self):
        eng = _engine(deviation_threshold_pct=25.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.detect_deviation(b.id, 105.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.NORMAL

    def test_minor(self):
        eng = _engine(deviation_threshold_pct=25.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.detect_deviation(b.id, 120.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.MINOR

    def test_moderate(self):
        eng = _engine(deviation_threshold_pct=25.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.detect_deviation(b.id, 140.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.MODERATE

    def test_critical(self):
        eng = _engine(deviation_threshold_pct=25.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        dev = eng.detect_deviation(b.id, 500.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.CRITICAL

    def test_missing_baseline(self):
        eng = _engine()
        assert eng.detect_deviation("nope", 100.0) is None

    def test_zero_baseline(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=0.0,
        )
        dev = eng.detect_deviation(b.id, 50.0)
        assert dev is not None
        assert dev.severity == DeviationSeverity.NORMAL


# ===========================================================================
# AutoUpdateBaseline
# ===========================================================================


class TestAutoUpdateBaseline:
    """Test MetricBaselineManager.auto_update_baseline."""

    def test_updates_with_deviations(self):
        eng = _engine(deviation_threshold_pct=10.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        eng.record_metric_value(b.id, 150.0)
        eng.record_metric_value(b.id, 200.0)
        updated = eng.auto_update_baseline(b.id)
        assert updated is not None
        assert updated.baseline_value != 100.0

    def test_no_deviations(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        updated = eng.auto_update_baseline(b.id)
        assert updated is not None
        assert updated.baseline_value == 100.0

    def test_missing_baseline(self):
        eng = _engine()
        assert eng.auto_update_baseline("nope") is None


# ===========================================================================
# IdentifyStaleBaselines
# ===========================================================================


class TestIdentifyStaleBaselines:
    """Test MetricBaselineManager.identify_stale_baselines."""

    def test_no_stale(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        stale = eng.identify_stale_baselines(
            max_age_hours=168,
        )
        assert len(stale) == 0

    def test_all_stale(self):
        eng = _engine()
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        b.last_updated = 0
        stale = eng.identify_stale_baselines(
            max_age_hours=1,
        )
        assert len(stale) == 1
        assert stale[0].id == b.id


# ===========================================================================
# CalculateBaselineAccuracy
# ===========================================================================


class TestCalculateBaselineAccuracy:
    """Test MetricBaselineManager.calculate_baseline_accuracy."""

    def test_no_deviations(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        results = eng.calculate_baseline_accuracy()
        assert len(results) == 1
        assert results[0]["accuracy_pct"] == 100.0

    def test_with_deviations(self):
        eng = _engine(deviation_threshold_pct=10.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        eng.record_metric_value(b.id, 200.0)
        results = eng.calculate_baseline_accuracy()
        assert results[0]["total_checks"] >= 1


# ===========================================================================
# GenerateBaselineReport
# ===========================================================================


class TestGenerateBaselineReport:
    """Test MetricBaselineManager.generate_baseline_report."""

    def test_basic_report(self):
        eng = _engine(deviation_threshold_pct=10.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
            strategy=BaselineStrategy.ROLLING_AVERAGE,
        )
        eng.record_metric_value(b.id, 200.0)
        report = eng.generate_baseline_report()
        assert isinstance(report, BaselineReport)
        assert report.total_baselines == 1
        assert report.total_deviations >= 1
        assert report.generated_at > 0
        assert len(report.by_strategy) >= 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_baseline_report()
        assert report.total_baselines == 0
        assert report.total_deviations == 0

    def test_report_recommendations(self):
        eng = _engine(deviation_threshold_pct=10.0)
        b = eng.create_baseline(
            service_name="api",
            metric_name="lat",
            baseline_value=100.0,
        )
        eng.record_metric_value(b.id, 500.0)
        report = eng.generate_baseline_report()
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test MetricBaselineManager.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
        )
        eng.clear_data()
        assert len(eng.list_baselines()) == 0
        stats = eng.get_stats()
        assert stats["total_baselines"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test MetricBaselineManager.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_baselines"] == 0
        assert stats["unique_services"] == 0
        assert stats["total_deviations"] == 0
        assert stats["total_samples"] == 0
        assert stats["strategy_distribution"] == {}
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.create_baseline(
            service_name="api",
            metric_name="lat",
            metric_type=MetricType.LATENCY,
            strategy=BaselineStrategy.STATIC,
        )
        eng.create_baseline(
            service_name="web",
            metric_name="cpu",
            metric_type=MetricType.CPU,
            strategy=BaselineStrategy.ADAPTIVE,
        )
        stats = eng.get_stats()
        assert stats["total_baselines"] == 2
        assert stats["unique_services"] == 2
        assert stats["strategy_distribution"]["static"] == 1
        assert stats["strategy_distribution"]["adaptive"] == 1
        assert stats["type_distribution"]["latency"] == 1
        assert stats["type_distribution"]["cpu"] == 1
