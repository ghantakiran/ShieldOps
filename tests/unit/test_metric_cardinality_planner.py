"""Tests for shieldops.observability.metric_cardinality_planner — MetricCardinalityPlanner."""

from __future__ import annotations

from shieldops.observability.metric_cardinality_planner import (
    CardinalityLevel,
    CardinalityPlan,
    CardinalityRecord,
    MetricCardinalityPlanner,
    MetricCardinalityReport,
    MetricSource,
    ReductionStrategy,
)


def _engine(**kw) -> MetricCardinalityPlanner:
    return MetricCardinalityPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_critical(self):
        assert CardinalityLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert CardinalityLevel.HIGH == "high"

    def test_level_moderate(self):
        assert CardinalityLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert CardinalityLevel.LOW == "low"

    def test_level_minimal(self):
        assert CardinalityLevel.MINIMAL == "minimal"

    def test_source_application(self):
        assert MetricSource.APPLICATION == "application"

    def test_source_infrastructure(self):
        assert MetricSource.INFRASTRUCTURE == "infrastructure"

    def test_source_custom(self):
        assert MetricSource.CUSTOM == "custom"

    def test_source_synthetic(self):
        assert MetricSource.SYNTHETIC == "synthetic"

    def test_source_external(self):
        assert MetricSource.EXTERNAL == "external"

    def test_strategy_drop_labels(self):
        assert ReductionStrategy.DROP_LABELS == "drop_labels"

    def test_strategy_aggregate(self):
        assert ReductionStrategy.AGGREGATE == "aggregate"

    def test_strategy_sample(self):
        assert ReductionStrategy.SAMPLE == "sample"

    def test_strategy_archive(self):
        assert ReductionStrategy.ARCHIVE == "archive"

    def test_strategy_keep(self):
        assert ReductionStrategy.KEEP == "keep"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cardinality_record_defaults(self):
        r = CardinalityRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.cardinality_level == CardinalityLevel.LOW
        assert r.metric_source == MetricSource.APPLICATION
        assert r.reduction_strategy == ReductionStrategy.KEEP
        assert r.cardinality_count == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_cardinality_plan_defaults(self):
        m = CardinalityPlan()
        assert m.id
        assert m.metric_name == ""
        assert m.cardinality_level == CardinalityLevel.LOW
        assert m.plan_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_metric_cardinality_report_defaults(self):
        r = MetricCardinalityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_plans == 0
        assert r.high_cardinality_count == 0
        assert r.avg_cardinality_count == 0.0
        assert r.by_level == {}
        assert r.by_source == {}
        assert r.by_strategy == {}
        assert r.top_high_cardinality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_cardinality
# ---------------------------------------------------------------------------


class TestRecordCardinality:
    def test_basic(self):
        eng = _engine()
        r = eng.record_cardinality(
            metric_name="http_request_duration",
            cardinality_level=CardinalityLevel.CRITICAL,
            metric_source=MetricSource.APPLICATION,
            reduction_strategy=ReductionStrategy.DROP_LABELS,
            cardinality_count=50000.0,
            service="api-gateway",
            team="sre",
        )
        assert r.metric_name == "http_request_duration"
        assert r.cardinality_level == CardinalityLevel.CRITICAL
        assert r.metric_source == MetricSource.APPLICATION
        assert r.reduction_strategy == ReductionStrategy.DROP_LABELS
        assert r.cardinality_count == 50000.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cardinality(metric_name=f"metric_{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_cardinality
# ---------------------------------------------------------------------------


class TestGetCardinality:
    def test_found(self):
        eng = _engine()
        r = eng.record_cardinality(
            metric_name="http_request_duration",
            cardinality_level=CardinalityLevel.CRITICAL,
        )
        result = eng.get_cardinality(r.id)
        assert result is not None
        assert result.cardinality_level == CardinalityLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_cardinality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_cardinalities
# ---------------------------------------------------------------------------


class TestListCardinalities:
    def test_list_all(self):
        eng = _engine()
        eng.record_cardinality(metric_name="metric_a")
        eng.record_cardinality(metric_name="metric_b")
        assert len(eng.list_cardinalities()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="metric_a",
            cardinality_level=CardinalityLevel.CRITICAL,
        )
        eng.record_cardinality(
            metric_name="metric_b",
            cardinality_level=CardinalityLevel.LOW,
        )
        results = eng.list_cardinalities(
            level=CardinalityLevel.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="metric_a",
            metric_source=MetricSource.APPLICATION,
        )
        eng.record_cardinality(
            metric_name="metric_b",
            metric_source=MetricSource.INFRASTRUCTURE,
        )
        results = eng.list_cardinalities(
            source=MetricSource.APPLICATION,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_cardinality(metric_name="metric_a", service="api-gateway")
        eng.record_cardinality(metric_name="metric_b", service="auth-svc")
        results = eng.list_cardinalities(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_cardinality(metric_name="metric_a", team="sre")
        eng.record_cardinality(metric_name="metric_b", team="platform")
        results = eng.list_cardinalities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cardinality(metric_name=f"metric_{i}")
        assert len(eng.list_cardinalities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_plan
# ---------------------------------------------------------------------------


class TestAddPlan:
    def test_basic(self):
        eng = _engine()
        m = eng.add_plan(
            metric_name="http_request_duration",
            cardinality_level=CardinalityLevel.HIGH,
            plan_score=85.0,
            threshold=90.0,
            breached=True,
            description="High cardinality detected",
        )
        assert m.metric_name == "http_request_duration"
        assert m.cardinality_level == CardinalityLevel.HIGH
        assert m.plan_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "High cardinality detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_plan(metric_name=f"metric_{i}")
        assert len(eng._plans) == 2


# ---------------------------------------------------------------------------
# analyze_cardinality_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCardinalityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="metric_a",
            cardinality_level=CardinalityLevel.CRITICAL,
            cardinality_count=50000.0,
        )
        eng.record_cardinality(
            metric_name="metric_b",
            cardinality_level=CardinalityLevel.CRITICAL,
            cardinality_count=30000.0,
        )
        result = eng.analyze_cardinality_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_cardinality_count"] == 40000.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_cardinality_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_cardinality_metrics
# ---------------------------------------------------------------------------


class TestIdentifyHighCardinalityMetrics:
    def test_detects_high(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="metric_a",
            cardinality_level=CardinalityLevel.CRITICAL,
        )
        eng.record_cardinality(
            metric_name="metric_b",
            cardinality_level=CardinalityLevel.LOW,
        )
        results = eng.identify_high_cardinality_metrics()
        assert len(results) == 1
        assert results[0]["metric_name"] == "metric_a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_cardinality_metrics() == []


# ---------------------------------------------------------------------------
# rank_by_cardinality
# ---------------------------------------------------------------------------


class TestRankByCardinality:
    def test_ranked(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="metric_a",
            service="api-gateway",
            cardinality_count=50000.0,
        )
        eng.record_cardinality(
            metric_name="metric_b",
            service="api-gateway",
            cardinality_count=30000.0,
        )
        eng.record_cardinality(
            metric_name="metric_c",
            service="auth-svc",
            cardinality_count=10000.0,
        )
        results = eng.rank_by_cardinality()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_cardinality_count"] == 40000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cardinality() == []


# ---------------------------------------------------------------------------
# detect_cardinality_trends
# ---------------------------------------------------------------------------


class TestDetectCardinalityTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_plan(metric_name="metric_a", plan_score=val)
        result = eng.detect_cardinality_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_plan(metric_name="metric_a", plan_score=val)
        result = eng.detect_cardinality_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_cardinality_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="http_request_duration",
            cardinality_level=CardinalityLevel.CRITICAL,
            metric_source=MetricSource.APPLICATION,
            reduction_strategy=ReductionStrategy.DROP_LABELS,
            cardinality_count=50000.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, MetricCardinalityReport)
        assert report.total_records == 1
        assert report.high_cardinality_count == 1
        assert len(report.top_high_cardinality) >= 1
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
        eng.record_cardinality(metric_name="metric_a")
        eng.add_plan(metric_name="metric_a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._plans) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_plans"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_cardinality(
            metric_name="http_request_duration",
            cardinality_level=CardinalityLevel.CRITICAL,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "critical" in stats["level_distribution"]
