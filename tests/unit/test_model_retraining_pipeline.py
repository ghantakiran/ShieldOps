"""Tests for shieldops.analytics.model_retraining_pipeline — ModelRetrainingPipeline."""

from __future__ import annotations

from shieldops.analytics.model_retraining_pipeline import (
    ModelRetrainingPipeline,
    PipelineStage,
    PipelineStatus,
    RetrainingAnalysis,
    RetrainingRecord,
    RetrainingReport,
    TriggerType,
)


def _engine(**kw) -> ModelRetrainingPipeline:
    return ModelRetrainingPipeline(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_data_prep(self):
        assert PipelineStage.DATA_PREP == "data_prep"

    def test_stage_feature_eng(self):
        assert PipelineStage.FEATURE_ENG == "feature_eng"

    def test_stage_training(self):
        assert PipelineStage.TRAINING == "training"

    def test_stage_evaluation(self):
        assert PipelineStage.EVALUATION == "evaluation"

    def test_stage_deployment(self):
        assert PipelineStage.DEPLOYMENT == "deployment"

    def test_trigger_scheduled(self):
        assert TriggerType.SCHEDULED == "scheduled"

    def test_trigger_drift_detected(self):
        assert TriggerType.DRIFT_DETECTED == "drift_detected"

    def test_trigger_performance_drop(self):
        assert TriggerType.PERFORMANCE_DROP == "performance_drop"

    def test_trigger_manual(self):
        assert TriggerType.MANUAL == "manual"

    def test_trigger_continuous(self):
        assert TriggerType.CONTINUOUS == "continuous"

    def test_status_running(self):
        assert PipelineStatus.RUNNING == "running"

    def test_status_completed(self):
        assert PipelineStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert PipelineStatus.FAILED == "failed"

    def test_status_queued(self):
        assert PipelineStatus.QUEUED == "queued"

    def test_status_cancelled(self):
        assert PipelineStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_retraining_record_defaults(self):
        r = RetrainingRecord()
        assert r.id
        assert r.model_id == ""
        assert r.pipeline_stage == PipelineStage.DATA_PREP
        assert r.trigger_type == TriggerType.SCHEDULED
        assert r.pipeline_status == PipelineStatus.QUEUED
        assert r.success_rate == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_retraining_analysis_defaults(self):
        a = RetrainingAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.pipeline_stage == PipelineStage.DATA_PREP
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_retraining_report_defaults(self):
        r = RetrainingReport()
        assert r.id
        assert r.total_records == 0
        assert r.failed_count == 0
        assert r.avg_success_rate == 0.0
        assert r.by_stage == {}
        assert r.by_trigger == {}
        assert r.by_status == {}
        assert r.top_failing == []
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
        assert eng._success_rate_threshold == 0.8

    def test_custom_init(self):
        eng = _engine(max_records=500, success_rate_threshold=0.9)
        assert eng._max_records == 500
        assert eng._success_rate_threshold == 0.9

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_pipeline / get_pipeline
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_pipeline(
            model_id="model-001",
            pipeline_stage=PipelineStage.TRAINING,
            trigger_type=TriggerType.DRIFT_DETECTED,
            pipeline_status=PipelineStatus.RUNNING,
            success_rate=0.95,
            service="ml-svc",
            team="ml-team",
        )
        assert r.model_id == "model-001"
        assert r.pipeline_stage == PipelineStage.TRAINING
        assert r.success_rate == 0.95

    def test_get_found(self):
        eng = _engine()
        r = eng.record_pipeline(model_id="m-001", success_rate=0.9)
        assert eng.get_pipeline(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_pipeline("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pipeline(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_pipelines
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001")
        eng.record_pipeline(model_id="m-002")
        assert len(eng.list_pipelines()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001", pipeline_stage=PipelineStage.TRAINING)
        eng.record_pipeline(model_id="m-002", pipeline_stage=PipelineStage.DEPLOYMENT)
        assert len(eng.list_pipelines(pipeline_stage=PipelineStage.TRAINING)) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001", pipeline_status=PipelineStatus.COMPLETED)
        eng.record_pipeline(model_id="m-002", pipeline_status=PipelineStatus.FAILED)
        assert len(eng.list_pipelines(pipeline_status=PipelineStatus.COMPLETED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001", team="ml-team")
        eng.record_pipeline(model_id="m-002", team="data-team")
        assert len(eng.list_pipelines(team="ml-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pipeline(model_id=f"m-{i}")
        assert len(eng.list_pipelines(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            pipeline_stage=PipelineStage.TRAINING,
            analysis_score=60.0,
            threshold=80.0,
            breached=True,
            description="pipeline failure",
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
        assert a.pipeline_stage == PipelineStage.DATA_PREP
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline(
            model_id="m-001", pipeline_stage=PipelineStage.TRAINING, success_rate=0.9
        )
        eng.record_pipeline(
            model_id="m-002", pipeline_stage=PipelineStage.TRAINING, success_rate=0.8
        )
        result = eng.analyze_distribution()
        assert "training" in result
        assert result["training"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(success_rate_threshold=0.8)
        eng.record_pipeline(model_id="m-001", success_rate=0.6)
        eng.record_pipeline(model_id="m-002", success_rate=0.95)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_ascending(self):
        eng = _engine(success_rate_threshold=0.8)
        eng.record_pipeline(model_id="m-001", success_rate=0.7)
        eng.record_pipeline(model_id="m-002", success_rate=0.5)
        results = eng.identify_severe_drifts()
        assert results[0]["success_rate"] == 0.5

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001", success_rate=0.95)
        eng.record_pipeline(model_id="m-002", success_rate=0.50)
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
        eng = _engine(success_rate_threshold=0.8)
        eng.record_pipeline(
            model_id="m-001",
            pipeline_stage=PipelineStage.TRAINING,
            trigger_type=TriggerType.DRIFT_DETECTED,
            pipeline_status=PipelineStatus.FAILED,
            success_rate=0.5,
        )
        report = eng.generate_report()
        assert isinstance(report, RetrainingReport)
        assert report.total_records == 1
        assert report.failed_count == 1
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
        eng.record_pipeline(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["stage_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_pipeline(model_id="m-001", pipeline_stage=PipelineStage.TRAINING, team="ml-team")
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
            eng.record_pipeline(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
