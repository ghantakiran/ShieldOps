"""Tests for shieldops.observability.metric_quality — MetricQualityScorer."""

from __future__ import annotations

from shieldops.observability.metric_quality import (
    MetricQualityRecord,
    MetricQualityReport,
    MetricQualityScorer,
    QualityAssessment,
    QualityDimension,
    QualityIssue,
    QualityLevel,
)


def _engine(**kw) -> MetricQualityScorer:
    return MetricQualityScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_completeness(self):
        assert QualityDimension.COMPLETENESS == "completeness"

    def test_dimension_accuracy(self):
        assert QualityDimension.ACCURACY == "accuracy"

    def test_dimension_timeliness(self):
        assert QualityDimension.TIMELINESS == "timeliness"

    def test_dimension_consistency(self):
        assert QualityDimension.CONSISTENCY == "consistency"

    def test_dimension_relevance(self):
        assert QualityDimension.RELEVANCE == "relevance"

    def test_level_excellent(self):
        assert QualityLevel.EXCELLENT == "excellent"

    def test_level_good(self):
        assert QualityLevel.GOOD == "good"

    def test_level_acceptable(self):
        assert QualityLevel.ACCEPTABLE == "acceptable"

    def test_level_poor(self):
        assert QualityLevel.POOR == "poor"

    def test_level_unusable(self):
        assert QualityLevel.UNUSABLE == "unusable"

    def test_issue_missing_data(self):
        assert QualityIssue.MISSING_DATA == "missing_data"

    def test_issue_stale_data(self):
        assert QualityIssue.STALE_DATA == "stale_data"

    def test_issue_high_cardinality(self):
        assert QualityIssue.HIGH_CARDINALITY == "high_cardinality"

    def test_issue_inconsistent_labels(self):
        assert QualityIssue.INCONSISTENT_LABELS == "inconsistent_labels"

    def test_issue_low_resolution(self):
        assert QualityIssue.LOW_RESOLUTION == "low_resolution"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_metric_quality_record_defaults(self):
        r = MetricQualityRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.quality_dimension == QualityDimension.COMPLETENESS
        assert r.quality_level == QualityLevel.ACCEPTABLE
        assert r.quality_issue == QualityIssue.MISSING_DATA
        assert r.quality_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_quality_assessment_defaults(self):
        a = QualityAssessment()
        assert a.id
        assert a.assessment_name == ""
        assert a.quality_dimension == QualityDimension.COMPLETENESS
        assert a.score_threshold == 0.0
        assert a.avg_quality_score == 0.0
        assert a.description == ""
        assert a.created_at > 0

    def test_metric_quality_report_defaults(self):
        r = MetricQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.poor_metrics == 0
        assert r.avg_quality_score == 0.0
        assert r.by_dimension == {}
        assert r.by_level == {}
        assert r.by_issue == {}
        assert r.top_items == []
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
            metric_name="cpu_usage",
            quality_dimension=QualityDimension.ACCURACY,
            quality_level=QualityLevel.EXCELLENT,
            quality_issue=QualityIssue.STALE_DATA,
            quality_score=95.0,
            team="sre",
        )
        assert r.metric_name == "cpu_usage"
        assert r.quality_dimension == QualityDimension.ACCURACY
        assert r.quality_level == QualityLevel.EXCELLENT
        assert r.quality_issue == QualityIssue.STALE_DATA
        assert r.quality_score == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(metric_name=f"metric-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


class TestGetQuality:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(
            metric_name="cpu_usage",
            quality_level=QualityLevel.EXCELLENT,
        )
        result = eng.get_quality(r.id)
        assert result is not None
        assert result.quality_level == QualityLevel.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_qualities
# ---------------------------------------------------------------------------


class TestListQualities:
    def test_list_all(self):
        eng = _engine()
        eng.record_quality(metric_name="cpu_usage")
        eng.record_quality(metric_name="mem_usage")
        assert len(eng.list_qualities()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_dimension=QualityDimension.ACCURACY,
        )
        eng.record_quality(
            metric_name="mem_usage",
            quality_dimension=QualityDimension.TIMELINESS,
        )
        results = eng.list_qualities(dimension=QualityDimension.ACCURACY)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_level=QualityLevel.EXCELLENT,
        )
        eng.record_quality(
            metric_name="mem_usage",
            quality_level=QualityLevel.POOR,
        )
        results = eng.list_qualities(level=QualityLevel.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_quality(metric_name="cpu_usage", team="sre")
        eng.record_quality(metric_name="mem_usage", team="platform")
        results = eng.list_qualities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(metric_name=f"metric-{i}")
        assert len(eng.list_qualities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            assessment_name="completeness-check",
            quality_dimension=QualityDimension.COMPLETENESS,
            score_threshold=0.8,
            avg_quality_score=85.0,
            description="Completeness assessment",
        )
        assert a.assessment_name == "completeness-check"
        assert a.quality_dimension == QualityDimension.COMPLETENESS
        assert a.score_threshold == 0.8
        assert a.avg_quality_score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(assessment_name=f"assess-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_metric_quality
# ---------------------------------------------------------------------------


class TestAnalyzeMetricQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_dimension=QualityDimension.ACCURACY,
            quality_score=90.0,
        )
        eng.record_quality(
            metric_name="mem_usage",
            quality_dimension=QualityDimension.ACCURACY,
            quality_score=80.0,
        )
        result = eng.analyze_metric_quality()
        assert "accuracy" in result
        assert result["accuracy"]["count"] == 2
        assert result["accuracy"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_metric_quality() == {}


# ---------------------------------------------------------------------------
# identify_poor_metrics
# ---------------------------------------------------------------------------


class TestIdentifyPoorMetrics:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_level=QualityLevel.POOR,
            quality_score=20.0,
        )
        eng.record_quality(
            metric_name="mem_usage",
            quality_level=QualityLevel.EXCELLENT,
        )
        results = eng.identify_poor_metrics()
        assert len(results) == 1
        assert results[0]["metric_name"] == "cpu_usage"

    def test_detects_unusable(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_level=QualityLevel.UNUSABLE,
        )
        results = eng.identify_poor_metrics()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_metrics() == []


# ---------------------------------------------------------------------------
# rank_by_quality_score
# ---------------------------------------------------------------------------


class TestRankByQualityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_quality(metric_name="m1", team="sre", quality_score=90.0)
        eng.record_quality(metric_name="m2", team="sre", quality_score=80.0)
        eng.record_quality(metric_name="m3", team="platform", quality_score=70.0)
        results = eng.rank_by_quality_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# ---------------------------------------------------------------------------
# detect_quality_degradation
# ---------------------------------------------------------------------------


class TestDetectQualityDegradation:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_assessment(assessment_name="a", avg_quality_score=s)
        result = eng.detect_quality_degradation()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_assessment(assessment_name="a", avg_quality_score=s)
        result = eng.detect_quality_degradation()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_quality_degradation()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_dimension=QualityDimension.ACCURACY,
            quality_level=QualityLevel.POOR,
            quality_score=30.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, MetricQualityReport)
        assert report.total_records == 1
        assert report.poor_metrics == 1
        assert report.avg_quality_score == 30.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_quality(metric_name="cpu_usage")
        eng.add_assessment(assessment_name="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            metric_name="cpu_usage",
            quality_dimension=QualityDimension.ACCURACY,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_metrics"] == 1
        assert "accuracy" in stats["dimension_distribution"]
