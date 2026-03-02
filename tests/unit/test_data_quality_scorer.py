"""Tests for shieldops.analytics.data_quality_scorer — DataQualityScorer."""

from __future__ import annotations

from shieldops.analytics.data_quality_scorer import (
    DataQualityReport,
    DataQualityScorer,
    DataSource,
    QualityAnalysis,
    QualityDimension,
    QualityGrade,
    QualityRecord,
)


def _engine(**kw) -> DataQualityScorer:
    return DataQualityScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_completeness(self):
        assert QualityDimension.COMPLETENESS == "completeness"

    def test_dimension_freshness(self):
        assert QualityDimension.FRESHNESS == "freshness"

    def test_dimension_consistency(self):
        assert QualityDimension.CONSISTENCY == "consistency"

    def test_dimension_accuracy(self):
        assert QualityDimension.ACCURACY == "accuracy"

    def test_dimension_timeliness(self):
        assert QualityDimension.TIMELINESS == "timeliness"

    def test_source_metrics(self):
        assert DataSource.METRICS == "metrics"

    def test_source_logs(self):
        assert DataSource.LOGS == "logs"

    def test_source_traces(self):
        assert DataSource.TRACES == "traces"

    def test_source_events(self):
        assert DataSource.EVENTS == "events"

    def test_source_configurations(self):
        assert DataSource.CONFIGURATIONS == "configurations"

    def test_grade_excellent(self):
        assert QualityGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert QualityGrade.GOOD == "good"

    def test_grade_acceptable(self):
        assert QualityGrade.ACCEPTABLE == "acceptable"

    def test_grade_poor(self):
        assert QualityGrade.POOR == "poor"

    def test_grade_failing(self):
        assert QualityGrade.FAILING == "failing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_quality_record_defaults(self):
        r = QualityRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.quality_dimension == QualityDimension.COMPLETENESS
        assert r.data_source == DataSource.METRICS
        assert r.quality_grade == QualityGrade.EXCELLENT
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_quality_analysis_defaults(self):
        a = QualityAnalysis()
        assert a.id
        assert a.pipeline_name == ""
        assert a.quality_dimension == QualityDimension.COMPLETENESS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_quality_report_defaults(self):
        r = DataQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_quality_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_dimension == {}
        assert r.by_source == {}
        assert r.by_grade == {}
        assert r.top_low_quality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_quality
# ---------------------------------------------------------------------------


class TestRecordQuality:
    def test_basic(self):
        eng = _engine()
        r = eng.record_quality(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            data_source=DataSource.METRICS,
            quality_grade=QualityGrade.GOOD,
            quality_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.pipeline_name == "PL-001"
        assert r.quality_dimension == QualityDimension.COMPLETENESS
        assert r.data_source == DataSource.METRICS
        assert r.quality_grade == QualityGrade.GOOD
        assert r.quality_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(pipeline_name=f"PL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


class TestGetQuality:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(
            pipeline_name="PL-001",
            data_source=DataSource.LOGS,
        )
        result = eng.get_quality(r.id)
        assert result is not None
        assert result.data_source == DataSource.LOGS

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_quality_records
# ---------------------------------------------------------------------------


class TestListQualityRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_quality(pipeline_name="PL-001")
        eng.record_quality(pipeline_name="PL-002")
        assert len(eng.list_quality_records()) == 2

    def test_filter_by_quality_dimension(self):
        eng = _engine()
        eng.record_quality(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.COMPLETENESS,
        )
        eng.record_quality(
            pipeline_name="PL-002",
            quality_dimension=QualityDimension.FRESHNESS,
        )
        results = eng.list_quality_records(quality_dimension=QualityDimension.COMPLETENESS)
        assert len(results) == 1

    def test_filter_by_data_source(self):
        eng = _engine()
        eng.record_quality(
            pipeline_name="PL-001",
            data_source=DataSource.METRICS,
        )
        eng.record_quality(
            pipeline_name="PL-002",
            data_source=DataSource.LOGS,
        )
        results = eng.list_quality_records(data_source=DataSource.METRICS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_quality(pipeline_name="PL-001", team="sre")
        eng.record_quality(pipeline_name="PL-002", team="platform")
        results = eng.list_quality_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(pipeline_name=f"PL-{i}")
        assert len(eng.list_quality_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.ACCURACY,
            analysis_score=72.0,
            threshold=70.0,
            breached=True,
            description="Quality below target",
        )
        assert a.pipeline_name == "PL-001"
        assert a.quality_dimension == QualityDimension.ACCURACY
        assert a.analysis_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(pipeline_name=f"PL-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_quality_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeQualityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_quality(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_score=80.0,
        )
        eng.record_quality(
            pipeline_name="PL-002",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_score=90.0,
        )
        result = eng.analyze_quality_distribution()
        assert "completeness" in result
        assert result["completeness"]["count"] == 2
        assert result["completeness"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_quality_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_quality_pipelines
# ---------------------------------------------------------------------------


class TestIdentifyLowQualityPipelines:
    def test_detects_low(self):
        eng = _engine(quality_score_threshold=80.0)
        eng.record_quality(
            pipeline_name="PL-001",
            quality_score=30.0,
        )
        eng.record_quality(
            pipeline_name="PL-002",
            quality_score=90.0,
        )
        results = eng.identify_low_quality_pipelines()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "PL-001"

    def test_sorted_ascending(self):
        eng = _engine(quality_score_threshold=80.0)
        eng.record_quality(pipeline_name="PL-001", quality_score=40.0)
        eng.record_quality(pipeline_name="PL-002", quality_score=20.0)
        results = eng.identify_low_quality_pipelines()
        assert len(results) == 2
        assert results[0]["quality_score"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_quality_pipelines() == []


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankByQuality:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_quality(pipeline_name="PL-001", quality_score=90.0, service="svc-a")
        eng.record_quality(pipeline_name="PL-002", quality_score=50.0, service="svc-b")
        results = eng.rank_by_quality()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_quality_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality() == []


# ---------------------------------------------------------------------------
# detect_quality_trends
# ---------------------------------------------------------------------------


class TestDetectQualityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(pipeline_name="PL-001", analysis_score=70.0)
        result = eng.detect_quality_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(pipeline_name="PL-001", analysis_score=50.0)
        eng.add_analysis(pipeline_name="PL-002", analysis_score=50.0)
        eng.add_analysis(pipeline_name="PL-003", analysis_score=80.0)
        eng.add_analysis(pipeline_name="PL-004", analysis_score=80.0)
        result = eng.detect_quality_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_quality_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_score_threshold=80.0)
        eng.record_quality(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            data_source=DataSource.METRICS,
            quality_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DataQualityReport)
        assert report.total_records == 1
        assert report.low_quality_count == 1
        assert len(report.top_low_quality) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_quality(pipeline_name="PL-001")
        eng.add_analysis(pipeline_name="PL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["quality_dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            pipeline_name="PL-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "completeness" in stats["quality_dimension_distribution"]
