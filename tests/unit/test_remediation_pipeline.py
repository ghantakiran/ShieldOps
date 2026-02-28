"""Tests for shieldops.operations.remediation_pipeline — RemediationPipelineOrchestrator."""

from __future__ import annotations

from shieldops.operations.remediation_pipeline import (
    PipelineOrchestratorReport,
    PipelineRecord,
    PipelineStage,
    PipelineStatus,
    PipelineStep,
    RemediationPipelineOrchestrator,
    StepDependency,
)


def _engine(**kw) -> RemediationPipelineOrchestrator:
    return RemediationPipelineOrchestrator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PipelineStage (5)
    def test_stage_validation(self):
        assert PipelineStage.VALIDATION == "validation"

    def test_stage_preparation(self):
        assert PipelineStage.PREPARATION == "preparation"

    def test_stage_execution(self):
        assert PipelineStage.EXECUTION == "execution"

    def test_stage_verification(self):
        assert PipelineStage.VERIFICATION == "verification"

    def test_stage_rollback(self):
        assert PipelineStage.ROLLBACK == "rollback"

    # PipelineStatus (5)
    def test_status_queued(self):
        assert PipelineStatus.QUEUED == "queued"

    def test_status_running(self):
        assert PipelineStatus.RUNNING == "running"

    def test_status_succeeded(self):
        assert PipelineStatus.SUCCEEDED == "succeeded"

    def test_status_failed(self):
        assert PipelineStatus.FAILED == "failed"

    def test_status_rolled_back(self):
        assert PipelineStatus.ROLLED_BACK == "rolled_back"

    # StepDependency (5)
    def test_dep_sequential(self):
        assert StepDependency.SEQUENTIAL == "sequential"

    def test_dep_parallel(self):
        assert StepDependency.PARALLEL == "parallel"

    def test_dep_conditional(self):
        assert StepDependency.CONDITIONAL == "conditional"

    def test_dep_on_failure(self):
        assert StepDependency.ON_FAILURE == "on_failure"

    def test_dep_optional(self):
        assert StepDependency.OPTIONAL == "optional"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_pipeline_record_defaults(self):
        r = PipelineRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.pipeline_stage == PipelineStage.VALIDATION
        assert r.pipeline_status == PipelineStatus.QUEUED
        assert r.step_dependency == StepDependency.SEQUENTIAL
        assert r.step_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_pipeline_step_defaults(self):
        r = PipelineStep()
        assert r.id
        assert r.step_name == ""
        assert r.pipeline_stage == PipelineStage.EXECUTION
        assert r.pipeline_status == PipelineStatus.RUNNING
        assert r.duration_seconds == 0.0
        assert r.created_at > 0

    def test_pipeline_orchestrator_report_defaults(self):
        r = PipelineOrchestratorReport()
        assert r.total_pipelines == 0
        assert r.total_steps == 0
        assert r.success_rate_pct == 0.0
        assert r.by_stage == {}
        assert r.by_status == {}
        assert r.rollback_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_pipeline
# -------------------------------------------------------------------


class TestRecordPipeline:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pipeline(
            "pipeline-a",
            pipeline_stage=PipelineStage.EXECUTION,
            pipeline_status=PipelineStatus.RUNNING,
        )
        assert r.pipeline_name == "pipeline-a"
        assert r.pipeline_stage == PipelineStage.EXECUTION

    def test_with_dependency(self):
        eng = _engine()
        r = eng.record_pipeline("pipeline-b", step_dependency=StepDependency.PARALLEL)
        assert r.step_dependency == StepDependency.PARALLEL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pipeline(f"pipeline-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_pipeline
# -------------------------------------------------------------------


class TestGetPipeline:
    def test_found(self):
        eng = _engine()
        r = eng.record_pipeline("pipeline-a")
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
        eng.record_pipeline("pipeline-a")
        eng.record_pipeline("pipeline-b")
        assert len(eng.list_pipelines()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a")
        eng.record_pipeline("pipeline-b")
        results = eng.list_pipelines(pipeline_name="pipeline-a")
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.SUCCEEDED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.FAILED)
        results = eng.list_pipelines(pipeline_status=PipelineStatus.SUCCEEDED)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_step
# -------------------------------------------------------------------


class TestAddStep:
    def test_basic(self):
        eng = _engine()
        s = eng.add_step(
            "validate-config",
            pipeline_stage=PipelineStage.VALIDATION,
            pipeline_status=PipelineStatus.SUCCEEDED,
            duration_seconds=5.0,
        )
        assert s.step_name == "validate-config"
        assert s.duration_seconds == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_step(f"step-{i}")
        assert len(eng._steps) == 2


# -------------------------------------------------------------------
# analyze_pipeline_efficiency
# -------------------------------------------------------------------


class TestAnalyzePipelineEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline(
            "pipeline-a",
            pipeline_status=PipelineStatus.SUCCEEDED,
            step_count=10,
        )
        eng.record_pipeline(
            "pipeline-a",
            pipeline_status=PipelineStatus.FAILED,
            step_count=20,
        )
        result = eng.analyze_pipeline_efficiency("pipeline-a")
        assert result["pipeline_name"] == "pipeline-a"
        assert result["total_pipelines"] == 2
        assert result["success_rate_pct"] == 50.0
        assert result["avg_step_count"] == 15.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_pipeline_efficiency("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_pipelines
# -------------------------------------------------------------------


class TestIdentifyFailedPipelines:
    def test_with_failures(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.FAILED)
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.FAILED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.SUCCEEDED)
        results = eng.identify_failed_pipelines()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipeline-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_pipelines() == []


# -------------------------------------------------------------------
# rank_by_completion_rate
# -------------------------------------------------------------------


class TestRankByCompletionRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.SUCCEEDED)
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.SUCCEEDED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.FAILED)
        results = eng.rank_by_completion_rate()
        assert results[0]["pipeline_name"] == "pipeline-a"
        assert results[0]["completion_rate_pct"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completion_rate() == []


# -------------------------------------------------------------------
# detect_pipeline_bottlenecks
# -------------------------------------------------------------------


class TestDetectPipelineBottlenecks:
    def test_with_bottlenecks(self):
        eng = _engine()
        for _ in range(5):
            eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.FAILED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.SUCCEEDED)
        results = eng.detect_pipeline_bottlenecks()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipeline-a"
        assert results[0]["bottleneck_detected"] is True

    def test_no_bottlenecks(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.FAILED)
        assert eng.detect_pipeline_bottlenecks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_status=PipelineStatus.SUCCEEDED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.FAILED)
        eng.record_pipeline("pipeline-b", pipeline_status=PipelineStatus.FAILED)
        eng.add_step("step-1")
        report = eng.generate_report()
        assert report.total_pipelines == 3
        assert report.total_steps == 1
        assert report.by_stage != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_pipelines == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a")
        eng.add_step("step-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._steps) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_pipelines"] == 0
        assert stats["total_steps"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_pipeline("pipeline-a", pipeline_stage=PipelineStage.EXECUTION)
        eng.record_pipeline("pipeline-b", pipeline_stage=PipelineStage.VALIDATION)
        eng.add_step("s1")
        stats = eng.get_stats()
        assert stats["total_pipelines"] == 2
        assert stats["total_steps"] == 1
        assert stats["unique_pipelines"] == 2
