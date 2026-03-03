"""Tests for shieldops.analytics.model_lineage_tracker — ModelLineageTracker."""

from __future__ import annotations

from shieldops.analytics.model_lineage_tracker import (
    ArtifactType,
    LineageAnalysis,
    LineageRecord,
    LineageReport,
    LineageStage,
    LineageStatus,
    ModelLineageTracker,
)


def _engine(**kw) -> ModelLineageTracker:
    return ModelLineageTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_data_collection(self):
        assert LineageStage.DATA_COLLECTION == "data_collection"

    def test_stage_preprocessing(self):
        assert LineageStage.PREPROCESSING == "preprocessing"

    def test_stage_training(self):
        assert LineageStage.TRAINING == "training"

    def test_stage_validation(self):
        assert LineageStage.VALIDATION == "validation"

    def test_stage_deployment(self):
        assert LineageStage.DEPLOYMENT == "deployment"

    def test_artifact_dataset(self):
        assert ArtifactType.DATASET == "dataset"

    def test_artifact_feature_store(self):
        assert ArtifactType.FEATURE_STORE == "feature_store"

    def test_artifact_model_weights(self):
        assert ArtifactType.MODEL_WEIGHTS == "model_weights"

    def test_artifact_checkpoint(self):
        assert ArtifactType.CHECKPOINT == "checkpoint"

    def test_artifact_config(self):
        assert ArtifactType.CONFIG == "config"

    def test_status_tracked(self):
        assert LineageStatus.TRACKED == "tracked"

    def test_status_missing(self):
        assert LineageStatus.MISSING == "missing"

    def test_status_corrupted(self):
        assert LineageStatus.CORRUPTED == "corrupted"

    def test_status_archived(self):
        assert LineageStatus.ARCHIVED == "archived"

    def test_status_unknown(self):
        assert LineageStatus.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_lineage_record_defaults(self):
        r = LineageRecord()
        assert r.id
        assert r.model_id == ""
        assert r.lineage_stage == LineageStage.DATA_COLLECTION
        assert r.artifact_type == ArtifactType.DATASET
        assert r.lineage_status == LineageStatus.UNKNOWN
        assert r.lineage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_lineage_analysis_defaults(self):
        a = LineageAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.lineage_stage == LineageStage.DATA_COLLECTION
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_lineage_report_defaults(self):
        r = LineageReport()
        assert r.id
        assert r.total_records == 0
        assert r.gap_count == 0
        assert r.avg_lineage_score == 0.0
        assert r.by_stage == {}
        assert r.by_artifact == {}
        assert r.by_status == {}
        assert r.top_gaps == []
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
        assert eng._lineage_gap_threshold == 0.6

    def test_custom_init(self):
        eng = _engine(max_records=100, lineage_gap_threshold=0.75)
        assert eng._max_records == 100
        assert eng._lineage_gap_threshold == 0.75

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_lineage / get_lineage
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_lineage(
            model_id="model-001",
            lineage_stage=LineageStage.TRAINING,
            artifact_type=ArtifactType.MODEL_WEIGHTS,
            lineage_status=LineageStatus.TRACKED,
            lineage_score=0.9,
            service="ml-svc",
            team="ml-team",
        )
        assert r.model_id == "model-001"
        assert r.lineage_stage == LineageStage.TRAINING
        assert r.lineage_score == 0.9

    def test_get_found(self):
        eng = _engine()
        r = eng.record_lineage(model_id="m-001", lineage_score=0.85)
        assert eng.get_lineage(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_lineage("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lineage(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_lineages
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001")
        eng.record_lineage(model_id="m-002")
        assert len(eng.list_lineages()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001", lineage_stage=LineageStage.TRAINING)
        eng.record_lineage(model_id="m-002", lineage_stage=LineageStage.DEPLOYMENT)
        assert len(eng.list_lineages(lineage_stage=LineageStage.TRAINING)) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001", lineage_status=LineageStatus.TRACKED)
        eng.record_lineage(model_id="m-002", lineage_status=LineageStatus.MISSING)
        assert len(eng.list_lineages(lineage_status=LineageStatus.TRACKED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001", team="ml-team")
        eng.record_lineage(model_id="m-002", team="data-team")
        assert len(eng.list_lineages(team="ml-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_lineage(model_id=f"m-{i}")
        assert len(eng.list_lineages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            lineage_stage=LineageStage.TRAINING,
            analysis_score=55.0,
            threshold=60.0,
            breached=True,
            description="lineage gap",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 55.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.lineage_stage == LineageStage.DATA_COLLECTION
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001", lineage_stage=LineageStage.TRAINING, lineage_score=0.8)
        eng.record_lineage(model_id="m-002", lineage_stage=LineageStage.TRAINING, lineage_score=0.9)
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
        eng = _engine(lineage_gap_threshold=0.6)
        eng.record_lineage(model_id="m-001", lineage_score=0.4)
        eng.record_lineage(model_id="m-002", lineage_score=0.9)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_ascending(self):
        eng = _engine(lineage_gap_threshold=0.6)
        eng.record_lineage(model_id="m-001", lineage_score=0.5)
        eng.record_lineage(model_id="m-002", lineage_score=0.3)
        results = eng.identify_severe_drifts()
        assert results[0]["lineage_score"] == 0.3

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001", lineage_score=0.9)
        eng.record_lineage(model_id="m-002", lineage_score=0.4)
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
        eng = _engine(lineage_gap_threshold=0.6)
        eng.record_lineage(
            model_id="m-001",
            lineage_stage=LineageStage.TRAINING,
            artifact_type=ArtifactType.DATASET,
            lineage_status=LineageStatus.MISSING,
            lineage_score=0.3,
        )
        report = eng.generate_report()
        assert isinstance(report, LineageReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "complete" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_lineage(model_id="m-001")
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
        eng.record_lineage(model_id="m-001", lineage_stage=LineageStage.TRAINING, team="ml-team")
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
            eng.record_lineage(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
