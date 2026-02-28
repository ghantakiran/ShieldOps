"""Tests for shieldops.changes.pipeline_analyzer — DeploymentPipelineAnalyzer."""

from __future__ import annotations

from shieldops.changes.pipeline_analyzer import (
    BottleneckType,
    DeploymentPipelineAnalyzer,
    PipelineAnalyzerReport,
    PipelineHealth,
    PipelineRecord,
    PipelineStage,
    StageMetric,
)


def _engine(**kw) -> DeploymentPipelineAnalyzer:
    return DeploymentPipelineAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PipelineStage (5)
    def test_stage_build(self):
        assert PipelineStage.BUILD == "build"

    def test_stage_test(self):
        assert PipelineStage.TEST == "test"

    def test_stage_security_scan(self):
        assert PipelineStage.SECURITY_SCAN == "security_scan"

    def test_stage_staging(self):
        assert PipelineStage.STAGING == "staging"

    def test_stage_production(self):
        assert PipelineStage.PRODUCTION == "production"

    # BottleneckType (5)
    def test_bottleneck_queue_wait(self):
        assert BottleneckType.QUEUE_WAIT == "queue_wait"

    def test_bottleneck_slow_step(self):
        assert BottleneckType.SLOW_STEP == "slow_step"

    def test_bottleneck_flaky_test(self):
        assert BottleneckType.FLAKY_TEST == "flaky_test"

    def test_bottleneck_resource_contention(self):
        assert BottleneckType.RESOURCE_CONTENTION == "resource_contention"

    def test_bottleneck_approval_delay(self):
        assert BottleneckType.APPROVAL_DELAY == "approval_delay"

    # PipelineHealth (5)
    def test_health_healthy(self):
        assert PipelineHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert PipelineHealth.DEGRADED == "degraded"

    def test_health_slow(self):
        assert PipelineHealth.SLOW == "slow"

    def test_health_broken(self):
        assert PipelineHealth.BROKEN == "broken"

    def test_health_unknown(self):
        assert PipelineHealth.UNKNOWN == "unknown"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_pipeline_record_defaults(self):
        r = PipelineRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.stage == PipelineStage.BUILD
        assert r.bottleneck == BottleneckType.QUEUE_WAIT
        assert r.health == PipelineHealth.HEALTHY
        assert r.duration_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_stage_metric_defaults(self):
        r = StageMetric()
        assert r.id
        assert r.metric_name == ""
        assert r.stage == PipelineStage.BUILD
        assert r.bottleneck == BottleneckType.QUEUE_WAIT
        assert r.avg_duration_minutes == 0.0
        assert r.failure_rate_pct == 0.0
        assert r.created_at > 0

    def test_pipeline_analyzer_report_defaults(self):
        r = PipelineAnalyzerReport()
        assert r.total_pipelines == 0
        assert r.total_metrics == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_stage == {}
        assert r.by_health == {}
        assert r.bottleneck_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_pipeline
# -------------------------------------------------------------------


class TestRecordPipeline:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pipeline("deploy-main", stage=PipelineStage.BUILD)
        assert r.pipeline_name == "deploy-main"
        assert r.stage == PipelineStage.BUILD

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_pipeline(
            "deploy-staging",
            stage=PipelineStage.STAGING,
            bottleneck=BottleneckType.SLOW_STEP,
            health=PipelineHealth.DEGRADED,
            duration_minutes=25.0,
            details="Slow integration tests",
        )
        assert r.health == PipelineHealth.DEGRADED
        assert r.bottleneck == BottleneckType.SLOW_STEP
        assert r.duration_minutes == 25.0
        assert r.details == "Slow integration tests"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pipeline(f"pipe-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_pipeline
# -------------------------------------------------------------------


class TestGetPipeline:
    def test_found(self):
        eng = _engine()
        r = eng.record_pipeline("deploy-main")
        assert eng.get_pipeline(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pipeline("nonexistent") is None


# -------------------------------------------------------------------
# list_pipelines
# -------------------------------------------------------------------


class TestListPipelines:
    def test_list_all(self):
        eng = _engine()
        eng.record_pipeline("pipe-a")
        eng.record_pipeline("pipe-b")
        assert len(eng.list_pipelines()) == 2

    def test_filter_by_pipeline_name(self):
        eng = _engine()
        eng.record_pipeline("pipe-a")
        eng.record_pipeline("pipe-b")
        results = eng.list_pipelines(pipeline_name="pipe-a")
        assert len(results) == 1
        assert results[0].pipeline_name == "pipe-a"

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_pipeline("pipe-a", stage=PipelineStage.BUILD)
        eng.record_pipeline("pipe-b", stage=PipelineStage.PRODUCTION)
        results = eng.list_pipelines(stage=PipelineStage.PRODUCTION)
        assert len(results) == 1
        assert results[0].pipeline_name == "pipe-b"


# -------------------------------------------------------------------
# add_stage_metric
# -------------------------------------------------------------------


class TestAddStageMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_stage_metric(
            "build-time",
            stage=PipelineStage.BUILD,
            bottleneck=BottleneckType.QUEUE_WAIT,
            avg_duration_minutes=5.0,
            failure_rate_pct=2.0,
        )
        assert m.metric_name == "build-time"
        assert m.stage == PipelineStage.BUILD
        assert m.avg_duration_minutes == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_stage_metric(f"metric-{i}")
        assert len(eng._metrics) == 2


# -------------------------------------------------------------------
# analyze_pipeline_health
# -------------------------------------------------------------------


class TestAnalyzePipelineHealth:
    def test_with_data(self):
        eng = _engine(max_duration_minutes=30.0)
        eng.record_pipeline("pipe-a", duration_minutes=20.0)
        eng.record_pipeline("pipe-a", duration_minutes=10.0)
        eng.record_pipeline("pipe-a", duration_minutes=15.0)
        result = eng.analyze_pipeline_health("pipe-a")
        assert result["avg_duration"] == 15.0
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_pipeline_health("unknown-pipe")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_duration_minutes=30.0)
        eng.record_pipeline("pipe-a", duration_minutes=10.0)
        eng.record_pipeline("pipe-a", duration_minutes=20.0)
        result = eng.analyze_pipeline_health("pipe-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_bottlenecks
# -------------------------------------------------------------------


class TestIdentifyBottlenecks:
    def test_with_bottlenecks(self):
        eng = _engine()
        eng.record_pipeline("pipe-a", bottleneck=BottleneckType.SLOW_STEP)
        eng.record_pipeline("pipe-a", bottleneck=BottleneckType.FLAKY_TEST)
        eng.record_pipeline("pipe-b", bottleneck=BottleneckType.QUEUE_WAIT)
        results = eng.identify_bottlenecks()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipe-a"
        assert results[0]["bottleneck_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_bottlenecks() == []

    def test_single_bottleneck_not_returned(self):
        eng = _engine()
        eng.record_pipeline("pipe-a", bottleneck=BottleneckType.SLOW_STEP)
        assert eng.identify_bottlenecks() == []


# -------------------------------------------------------------------
# rank_by_throughput
# -------------------------------------------------------------------


class TestRankByThroughput:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline("pipe-a", duration_minutes=50.0)
        eng.record_pipeline("pipe-b", duration_minutes=10.0)
        results = eng.rank_by_throughput()
        assert results[0]["pipeline_name"] == "pipe-b"
        assert results[0]["avg_duration_minutes"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_throughput() == []


# -------------------------------------------------------------------
# detect_pipeline_trends
# -------------------------------------------------------------------


class TestDetectPipelineTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_pipeline("pipe-a")
        eng.record_pipeline("pipe-b")
        results = eng.detect_pipeline_trends()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipe-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_pipeline_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_pipeline("pipe-a")
        assert eng.detect_pipeline_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline("pipe-a", health=PipelineHealth.BROKEN)
        eng.record_pipeline("pipe-b", health=PipelineHealth.HEALTHY)
        eng.add_stage_metric("metric-1")
        report = eng.generate_report()
        assert report.total_pipelines == 2
        assert report.total_metrics == 1
        assert report.by_stage != {}
        assert report.by_health != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_pipelines == 0
        assert report.healthy_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_pipeline("pipe-a")
        eng.add_stage_metric("metric-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_pipelines"] == 0
        assert stats["total_metrics"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_duration_minutes=30.0)
        eng.record_pipeline("pipe-a", stage=PipelineStage.BUILD)
        eng.record_pipeline("pipe-b", stage=PipelineStage.PRODUCTION)
        eng.add_stage_metric("metric-1")
        stats = eng.get_stats()
        assert stats["total_pipelines"] == 2
        assert stats["total_metrics"] == 1
        assert stats["unique_pipelines"] == 2
        assert stats["max_duration_minutes"] == 30.0
