"""Tests for shieldops.security.detection_engineering_pipeline — DetectionEngineeringPipeline."""

from __future__ import annotations

from shieldops.security.detection_engineering_pipeline import (
    DetectionEngineeringPipeline,
    DetectionLanguage,
    PipelineAnalysis,
    PipelineRecord,
    PipelineReport,
    PipelineStage,
    PipelineStatus,
)


def _engine(**kw) -> DetectionEngineeringPipeline:
    return DetectionEngineeringPipeline(**kw)


class TestEnums:
    def test_pipelinestage_val1(self):
        assert PipelineStage.IDEATION == "ideation"

    def test_pipelinestage_val2(self):
        assert PipelineStage.DEVELOPMENT == "development"

    def test_pipelinestage_val3(self):
        assert PipelineStage.TESTING == "testing"

    def test_pipelinestage_val4(self):
        assert PipelineStage.REVIEW == "review"

    def test_pipelinestage_val5(self):
        assert PipelineStage.DEPLOYED == "deployed"

    def test_detectionlanguage_val1(self):
        assert DetectionLanguage.SIGMA == "sigma"

    def test_detectionlanguage_val2(self):
        assert DetectionLanguage.YARA == "yara"

    def test_detectionlanguage_val3(self):
        assert DetectionLanguage.KQL == "kql"

    def test_detectionlanguage_val4(self):
        assert DetectionLanguage.SPL == "spl"

    def test_detectionlanguage_val5(self):
        assert DetectionLanguage.CUSTOM == "custom"

    def test_pipelinestatus_val1(self):
        assert PipelineStatus.ACTIVE == "active"

    def test_pipelinestatus_val2(self):
        assert PipelineStatus.BLOCKED == "blocked"

    def test_pipelinestatus_val3(self):
        assert PipelineStatus.COMPLETED == "completed"

    def test_pipelinestatus_val4(self):
        assert PipelineStatus.ARCHIVED == "archived"

    def test_pipelinestatus_val5(self):
        assert PipelineStatus.FAILED == "failed"


class TestModels:
    def test_record_defaults(self):
        r = PipelineRecord()
        assert r.id
        assert r.rule_name == ""

    def test_analysis_defaults(self):
        a = PipelineAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = PipelineReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pipeline(
            rule_name="test",
            pipeline_stage=PipelineStage.DEVELOPMENT,
            pipeline_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.rule_name == "test"
        assert r.pipeline_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pipeline(rule_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_pipeline(rule_name="test")
        assert eng.get_pipeline(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pipeline("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_pipeline(rule_name="a")
        eng.record_pipeline(rule_name="b")
        assert len(eng.list_pipelines()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_pipeline(rule_name="a", pipeline_stage=PipelineStage.IDEATION)
        eng.record_pipeline(rule_name="b", pipeline_stage=PipelineStage.DEVELOPMENT)
        assert len(eng.list_pipelines(pipeline_stage=PipelineStage.IDEATION)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_pipeline(rule_name="a", detection_language=DetectionLanguage.SIGMA)
        eng.record_pipeline(rule_name="b", detection_language=DetectionLanguage.YARA)
        assert len(eng.list_pipelines(detection_language=DetectionLanguage.SIGMA)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_pipeline(rule_name="a", team="sec")
        eng.record_pipeline(rule_name="b", team="ops")
        assert len(eng.list_pipelines(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pipeline(rule_name=f"t-{i}")
        assert len(eng.list_pipelines(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            rule_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(rule_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pipeline(
            rule_name="a", pipeline_stage=PipelineStage.IDEATION, pipeline_score=90.0
        )
        eng.record_pipeline(
            rule_name="b", pipeline_stage=PipelineStage.IDEATION, pipeline_score=70.0
        )
        result = eng.analyze_distribution()
        assert PipelineStage.IDEATION.value in result
        assert result[PipelineStage.IDEATION.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_pipeline(rule_name="a", pipeline_score=60.0)
        eng.record_pipeline(rule_name="b", pipeline_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_pipeline(rule_name="a", pipeline_score=50.0)
        eng.record_pipeline(rule_name="b", pipeline_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["pipeline_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_pipeline(rule_name="a", service="auth", pipeline_score=90.0)
        eng.record_pipeline(rule_name="b", service="api", pipeline_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(rule_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(rule_name="a", analysis_score=20.0)
        eng.add_analysis(rule_name="b", analysis_score=20.0)
        eng.add_analysis(rule_name="c", analysis_score=80.0)
        eng.add_analysis(rule_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_pipeline(rule_name="test", pipeline_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_pipeline(rule_name="test")
        eng.add_analysis(rule_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_pipeline(rule_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
