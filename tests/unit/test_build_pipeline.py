"""Tests for shieldops.analytics.build_pipeline — BuildPipelineAnalyzer."""

from __future__ import annotations

from shieldops.analytics.build_pipeline import (
    BuildOptimization,
    BuildOutcome,
    BuildPipelineAnalyzer,
    BuildPipelineReport,
    BuildRecord,
    OptimizationTarget,
    PipelineStage,
)


def _engine(**kw) -> BuildPipelineAnalyzer:
    return BuildPipelineAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PipelineStage (5)
    def test_stage_checkout(self):
        assert PipelineStage.CHECKOUT == "checkout"

    def test_stage_build(self):
        assert PipelineStage.BUILD == "build"

    def test_stage_test(self):
        assert PipelineStage.TEST == "test"

    def test_stage_security_scan(self):
        assert PipelineStage.SECURITY_SCAN == "security_scan"

    def test_stage_publish(self):
        assert PipelineStage.PUBLISH == "publish"

    # BuildOutcome (5)
    def test_outcome_success(self):
        assert BuildOutcome.SUCCESS == "success"

    def test_outcome_failure(self):
        assert BuildOutcome.FAILURE == "failure"

    def test_outcome_timeout(self):
        assert BuildOutcome.TIMEOUT == "timeout"

    def test_outcome_cancelled(self):
        assert BuildOutcome.CANCELLED == "cancelled"

    def test_outcome_unstable(self):
        assert BuildOutcome.UNSTABLE == "unstable"

    # OptimizationTarget (5)
    def test_target_parallelism(self):
        assert OptimizationTarget.PARALLELISM == "parallelism"

    def test_target_caching(self):
        assert OptimizationTarget.CACHING == "caching"

    def test_target_resource_allocation(self):
        assert OptimizationTarget.RESOURCE_ALLOCATION == "resource_allocation"

    def test_target_stage_elimination(self):
        assert OptimizationTarget.STAGE_ELIMINATION == "stage_elimination"

    def test_target_dependency_reduction(self):
        assert OptimizationTarget.DEPENDENCY_REDUCTION == "dependency_reduction"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_build_record_defaults(self):
        r = BuildRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.stage == PipelineStage.BUILD
        assert r.outcome == BuildOutcome.SUCCESS
        assert r.duration_seconds == 0.0
        assert r.branch == ""
        assert r.commit_sha == ""
        assert r.is_flaky is False
        assert r.details == ""
        assert r.created_at > 0

    def test_build_optimization_defaults(self):
        r = BuildOptimization()
        assert r.id
        assert r.pipeline_name == ""
        assert r.target == OptimizationTarget.CACHING
        assert r.estimated_savings_seconds == 0.0
        assert r.reason == ""
        assert r.created_at > 0

    def test_build_pipeline_report_defaults(self):
        r = BuildPipelineReport()
        assert r.total_builds == 0
        assert r.total_optimizations == 0
        assert r.avg_duration_seconds == 0.0
        assert r.success_rate_pct == 0.0
        assert r.by_outcome == {}
        assert r.by_stage == {}
        assert r.flaky_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_build
# -------------------------------------------------------------------


class TestRecordBuild:
    def test_basic(self):
        eng = _engine()
        r = eng.record_build("ci-main", duration_seconds=120.0)
        assert r.pipeline_name == "ci-main"
        assert r.outcome == BuildOutcome.SUCCESS
        assert r.duration_seconds == 120.0

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_build(
            "ci-main",
            stage=PipelineStage.TEST,
            outcome=BuildOutcome.FAILURE,
            duration_seconds=300.0,
            branch="feat/x",
            commit_sha="abc123",
            is_flaky=True,
            details="Timeout in integration test",
        )
        assert r.stage == PipelineStage.TEST
        assert r.outcome == BuildOutcome.FAILURE
        assert r.is_flaky is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_build(f"pipeline-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_build
# -------------------------------------------------------------------


class TestGetBuild:
    def test_found(self):
        eng = _engine()
        r = eng.record_build("ci-main")
        assert eng.get_build(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_build("nonexistent") is None


# -------------------------------------------------------------------
# list_builds
# -------------------------------------------------------------------


class TestListBuilds:
    def test_list_all(self):
        eng = _engine()
        eng.record_build("p1")
        eng.record_build("p2")
        assert len(eng.list_builds()) == 2

    def test_filter_by_pipeline(self):
        eng = _engine()
        eng.record_build("p1")
        eng.record_build("p2")
        results = eng.list_builds(pipeline_name="p1")
        assert len(results) == 1
        assert results[0].pipeline_name == "p1"

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_build("p1", outcome=BuildOutcome.SUCCESS)
        eng.record_build("p2", outcome=BuildOutcome.FAILURE)
        results = eng.list_builds(outcome=BuildOutcome.FAILURE)
        assert len(results) == 1
        assert results[0].pipeline_name == "p2"


# -------------------------------------------------------------------
# add_optimization
# -------------------------------------------------------------------


class TestAddOptimization:
    def test_basic(self):
        eng = _engine()
        opt = eng.add_optimization(
            "ci-main",
            target=OptimizationTarget.PARALLELISM,
            estimated_savings_seconds=60.0,
            reason="Parallelize test stages",
        )
        assert opt.pipeline_name == "ci-main"
        assert opt.target == OptimizationTarget.PARALLELISM
        assert opt.estimated_savings_seconds == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_optimization(f"p-{i}")
        assert len(eng._optimizations) == 2


# -------------------------------------------------------------------
# analyze_pipeline_performance
# -------------------------------------------------------------------


class TestAnalyzePipelinePerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_build("ci-main", outcome=BuildOutcome.SUCCESS, duration_seconds=100.0)
        eng.record_build("ci-main", outcome=BuildOutcome.FAILURE, duration_seconds=200.0)
        result = eng.analyze_pipeline_performance("ci-main")
        assert result["pipeline_name"] == "ci-main"
        assert result["total_builds"] == 2
        assert result["success_rate_pct"] == 50.0
        assert result["avg_duration_seconds"] == 150.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_pipeline_performance("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_flaky_stages
# -------------------------------------------------------------------


class TestIdentifyFlakyStages:
    def test_with_flaky(self):
        eng = _engine()
        eng.record_build("p1", is_flaky=True, duration_seconds=50.0, stage=PipelineStage.TEST)
        eng.record_build("p2", is_flaky=False, duration_seconds=100.0)
        results = eng.identify_flaky_stages()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "p1"
        assert results[0]["stage"] == "test"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_flaky_stages() == []


# -------------------------------------------------------------------
# rank_slowest_pipelines
# -------------------------------------------------------------------


class TestRankSlowestPipelines:
    def test_with_data(self):
        eng = _engine()
        eng.record_build("fast", duration_seconds=10.0)
        eng.record_build("slow", duration_seconds=300.0)
        eng.record_build("medium", duration_seconds=100.0)
        results = eng.rank_slowest_pipelines()
        assert len(results) == 3
        assert results[0]["pipeline_name"] == "slow"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_slowest_pipelines() == []


# -------------------------------------------------------------------
# estimate_time_savings
# -------------------------------------------------------------------


class TestEstimateTimeSavings:
    def test_with_data(self):
        eng = _engine()
        eng.add_optimization("p1", estimated_savings_seconds=60.0, reason="Cache deps")
        eng.add_optimization("p2", estimated_savings_seconds=120.0, reason="Parallel tests")
        results = eng.estimate_time_savings()
        assert len(results) == 2
        assert results[0]["estimated_savings_seconds"] == 120.0

    def test_empty(self):
        eng = _engine()
        assert eng.estimate_time_savings() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_success_rate_pct=90.0)
        eng.record_build("p1", outcome=BuildOutcome.SUCCESS, duration_seconds=100.0)
        eng.record_build("p2", outcome=BuildOutcome.FAILURE, duration_seconds=200.0, is_flaky=True)
        eng.add_optimization("p2", target=OptimizationTarget.CACHING)
        report = eng.generate_report()
        assert report.total_builds == 2
        assert report.total_optimizations == 1
        assert report.by_outcome != {}
        assert report.flaky_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_builds == 0
        assert report.avg_duration_seconds == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_build("p1")
        eng.add_optimization("p1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._optimizations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_builds"] == 0
        assert stats["total_optimizations"] == 0
        assert stats["outcome_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_build("p1", outcome=BuildOutcome.SUCCESS)
        eng.record_build("p2", outcome=BuildOutcome.FAILURE)
        eng.add_optimization("p1")
        stats = eng.get_stats()
        assert stats["total_builds"] == 2
        assert stats["total_optimizations"] == 1
        assert stats["unique_pipelines"] == 2
        assert stats["min_success_rate_pct"] == 90.0
