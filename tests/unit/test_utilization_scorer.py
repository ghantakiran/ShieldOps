"""Tests for shieldops.analytics.utilization_scorer — CapacityUtilizationScorer."""

from __future__ import annotations

from shieldops.analytics.utilization_scorer import (
    CapacityUtilizationScorer,
    ResourceType,
    UtilizationGrade,
    UtilizationMetric,
    UtilizationRecord,
    UtilizationScorerReport,
    UtilizationTrend,
)


def _engine(**kw) -> CapacityUtilizationScorer:
    return CapacityUtilizationScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResourceType (5)
    def test_resource_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_disk(self):
        assert ResourceType.DISK == "disk"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_gpu(self):
        assert ResourceType.GPU == "gpu"

    # UtilizationGrade (5)
    def test_grade_optimal(self):
        assert UtilizationGrade.OPTIMAL == "optimal"

    def test_grade_good(self):
        assert UtilizationGrade.GOOD == "good"

    def test_grade_underutilized(self):
        assert UtilizationGrade.UNDERUTILIZED == "underutilized"

    def test_grade_over_provisioned(self):
        assert UtilizationGrade.OVER_PROVISIONED == "over_provisioned"

    def test_grade_critical(self):
        assert UtilizationGrade.CRITICAL == "critical"

    # UtilizationTrend (5)
    def test_trend_increasing(self):
        assert UtilizationTrend.INCREASING == "increasing"

    def test_trend_stable(self):
        assert UtilizationTrend.STABLE == "stable"

    def test_trend_decreasing(self):
        assert UtilizationTrend.DECREASING == "decreasing"

    def test_trend_volatile(self):
        assert UtilizationTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert UtilizationTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_utilization_record_defaults(self):
        r = UtilizationRecord()
        assert r.id
        assert r.resource_name == ""
        assert r.resource_type == ResourceType.CPU
        assert r.utilization_pct == 0.0
        assert r.grade == UtilizationGrade.GOOD
        assert r.trend == UtilizationTrend.INSUFFICIENT_DATA
        assert r.environment == ""
        assert r.created_at > 0

    def test_utilization_metric_defaults(self):
        m = UtilizationMetric()
        assert m.id
        assert m.metric_name == ""
        assert m.resource_type == ResourceType.CPU
        assert m.threshold_pct == 0.0
        assert m.sample_window_minutes == 60
        assert m.environment == ""
        assert m.created_at > 0

    def test_utilization_scorer_report_defaults(self):
        r = UtilizationScorerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_resource_type == {}
        assert r.by_grade == {}
        assert r.over_provisioned_count == 0
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_utilization
# -------------------------------------------------------------------


class TestRecordUtilization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_utilization("node-1", resource_type=ResourceType.CPU)
        assert r.resource_name == "node-1"
        assert r.resource_type == ResourceType.CPU

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_utilization(
            "gpu-cluster-1",
            resource_type=ResourceType.GPU,
            utilization_pct=95.0,
            grade=UtilizationGrade.CRITICAL,
            trend=UtilizationTrend.INCREASING,
            environment="production",
        )
        assert r.utilization_pct == 95.0
        assert r.grade == UtilizationGrade.CRITICAL
        assert r.trend == UtilizationTrend.INCREASING
        assert r.environment == "production"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_utilization(f"node-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_utilization
# -------------------------------------------------------------------


class TestGetUtilization:
    def test_found(self):
        eng = _engine()
        r = eng.record_utilization("node-1")
        assert eng.get_utilization(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_utilization("nonexistent") is None


# -------------------------------------------------------------------
# list_utilizations
# -------------------------------------------------------------------


class TestListUtilizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_utilization("node-a")
        eng.record_utilization("node-b")
        assert len(eng.list_utilizations()) == 2

    def test_filter_by_resource_type(self):
        eng = _engine()
        eng.record_utilization("node-a", resource_type=ResourceType.CPU)
        eng.record_utilization("node-b", resource_type=ResourceType.MEMORY)
        results = eng.list_utilizations(resource_type=ResourceType.MEMORY)
        assert len(results) == 1
        assert results[0].resource_name == "node-b"

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_utilization("node-a", grade=UtilizationGrade.OPTIMAL)
        eng.record_utilization("node-b", grade=UtilizationGrade.CRITICAL)
        results = eng.list_utilizations(grade=UtilizationGrade.CRITICAL)
        assert len(results) == 1
        assert results[0].resource_name == "node-b"


# -------------------------------------------------------------------
# add_metric
# -------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            "cpu-threshold",
            resource_type=ResourceType.CPU,
            threshold_pct=80.0,
            sample_window_minutes=30,
            environment="production",
        )
        assert m.metric_name == "cpu-threshold"
        assert m.resource_type == ResourceType.CPU
        assert m.threshold_pct == 80.0
        assert m.sample_window_minutes == 30

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_metric(f"metric-{i}")
        assert len(eng._metrics) == 2


# -------------------------------------------------------------------
# analyze_utilization_by_resource
# -------------------------------------------------------------------


class TestAnalyzeUtilizationByResource:
    def test_with_data(self):
        eng = _engine(optimal_utilization_pct=70.0)
        eng.record_utilization("node-a", resource_type=ResourceType.CPU, utilization_pct=65.0)
        eng.record_utilization("node-b", resource_type=ResourceType.CPU, utilization_pct=75.0)
        result = eng.analyze_utilization_by_resource(ResourceType.CPU)
        assert result["record_count"] == 2
        assert result["avg_utilization_pct"] == 70.0
        assert result["near_optimal"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_utilization_by_resource(ResourceType.GPU)
        assert result["status"] == "no_data"

    def test_far_from_optimal(self):
        eng = _engine(optimal_utilization_pct=70.0)
        eng.record_utilization("node-a", resource_type=ResourceType.DISK, utilization_pct=10.0)
        result = eng.analyze_utilization_by_resource(ResourceType.DISK)
        assert result["near_optimal"] is False


# -------------------------------------------------------------------
# identify_over_provisioned
# -------------------------------------------------------------------


class TestIdentifyOverProvisioned:
    def test_with_over_provisioned(self):
        eng = _engine()
        eng.record_utilization(
            "node-a",
            grade=UtilizationGrade.OVER_PROVISIONED,
            utilization_pct=10.0,
        )
        eng.record_utilization("node-b", grade=UtilizationGrade.OPTIMAL, utilization_pct=70.0)
        results = eng.identify_over_provisioned()
        assert len(results) == 1
        assert results[0]["resource_name"] == "node-a"

    def test_underutilized_included(self):
        eng = _engine()
        eng.record_utilization("node-a", grade=UtilizationGrade.UNDERUTILIZED)
        results = eng.identify_over_provisioned()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_provisioned() == []


# -------------------------------------------------------------------
# rank_by_utilization_score
# -------------------------------------------------------------------


class TestRankByUtilizationScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization("node-a", utilization_pct=20.0)
        eng.record_utilization("node-b", utilization_pct=95.0)
        results = eng.rank_by_utilization_score()
        assert results[0]["resource_name"] == "node-b"
        assert results[0]["utilization_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization_score() == []


# -------------------------------------------------------------------
# detect_utilization_trends
# -------------------------------------------------------------------


class TestDetectUtilizationTrends:
    def test_with_volatile(self):
        eng = _engine()
        eng.record_utilization(
            "node-a", resource_type=ResourceType.CPU, trend=UtilizationTrend.VOLATILE
        )
        eng.record_utilization(
            "node-b", resource_type=ResourceType.MEMORY, trend=UtilizationTrend.STABLE
        )
        results = eng.detect_utilization_trends()
        assert len(results) == 1
        assert results[0]["resource_type"] == "cpu"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_utilization_trends() == []

    def test_multiple_increasing(self):
        eng = _engine()
        eng.record_utilization(
            "node-a", resource_type=ResourceType.DISK, trend=UtilizationTrend.INCREASING
        )
        eng.record_utilization(
            "node-b", resource_type=ResourceType.DISK, trend=UtilizationTrend.INCREASING
        )
        results = eng.detect_utilization_trends()
        assert len(results) == 1
        assert results[0]["increasing_count"] == 2


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_utilization(
            "node-a", grade=UtilizationGrade.OVER_PROVISIONED, utilization_pct=10.0
        )
        eng.record_utilization("node-b", grade=UtilizationGrade.CRITICAL, utilization_pct=99.0)
        eng.add_metric("cpu-threshold")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_metrics == 1
        assert report.over_provisioned_count == 1
        assert report.critical_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.avg_utilization_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_utilization("node-a")
        eng.add_metric("cpu-threshold")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["resource_type_distribution"] == {}

    def test_populated(self):
        eng = _engine(optimal_utilization_pct=65.0)
        eng.record_utilization("node-a", resource_type=ResourceType.CPU)
        eng.record_utilization("node-b", resource_type=ResourceType.MEMORY)
        eng.add_metric("cpu-threshold")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_metrics"] == 1
        assert stats["unique_resources"] == 2
        assert stats["optimal_utilization_pct"] == 65.0
