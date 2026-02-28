"""Tests for shieldops.incidents.postmortem_quality — PostmortemQualityScorer."""

from __future__ import annotations

from shieldops.incidents.postmortem_quality import (
    DimensionScore,
    PostmortemQualityReport,
    PostmortemQualityScorer,
    PostmortemRecord,
    QualityDimension,
    QualityGrade,
    QualityTrend,
)


def _engine(**kw) -> PostmortemQualityScorer:
    return PostmortemQualityScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # QualityDimension (5)
    def test_dimension_timeline_accuracy(self):
        assert QualityDimension.TIMELINE_ACCURACY == "timeline_accuracy"

    def test_dimension_root_cause_depth(self):
        assert QualityDimension.ROOT_CAUSE_DEPTH == "root_cause_depth"

    def test_dimension_action_item_clarity(self):
        assert QualityDimension.ACTION_ITEM_CLARITY == "action_item_clarity"

    def test_dimension_blamelessness(self):
        assert QualityDimension.BLAMELESSNESS == "blamelessness"

    def test_dimension_learning_value(self):
        assert QualityDimension.LEARNING_VALUE == "learning_value"

    # QualityGrade (5)
    def test_grade_excellent(self):
        assert QualityGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert QualityGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert QualityGrade.ADEQUATE == "adequate"

    def test_grade_poor(self):
        assert QualityGrade.POOR == "poor"

    def test_grade_incomplete(self):
        assert QualityGrade.INCOMPLETE == "incomplete"

    # QualityTrend (5)
    def test_trend_improving(self):
        assert QualityTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert QualityTrend.STABLE == "stable"

    def test_trend_declining(self):
        assert QualityTrend.DECLINING == "declining"

    def test_trend_volatile(self):
        assert QualityTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert QualityTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_postmortem_record_defaults(self):
        r = PostmortemRecord()
        assert r.id
        assert r.service_name == ""
        assert r.dimension == QualityDimension.TIMELINE_ACCURACY
        assert r.grade == QualityGrade.ADEQUATE
        assert r.quality_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_dimension_score_defaults(self):
        r = DimensionScore()
        assert r.id
        assert r.dimension_name == ""
        assert r.dimension == QualityDimension.TIMELINE_ACCURACY
        assert r.grade == QualityGrade.ADEQUATE
        assert r.score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_postmortem_quality_report_defaults(self):
        r = PostmortemQualityReport()
        assert r.total_records == 0
        assert r.total_dimensions == 0
        assert r.avg_quality_score_pct == 0.0
        assert r.by_dimension == {}
        assert r.by_grade == {}
        assert r.poor_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_postmortem
# -------------------------------------------------------------------


class TestRecordPostmortem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_postmortem("auth-svc", dimension=QualityDimension.ROOT_CAUSE_DEPTH)
        assert r.service_name == "auth-svc"
        assert r.dimension == QualityDimension.ROOT_CAUSE_DEPTH

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_postmortem(
            "api-gw",
            dimension=QualityDimension.BLAMELESSNESS,
            grade=QualityGrade.EXCELLENT,
            quality_score=95.0,
            details="exemplary blameless postmortem",
        )
        assert r.grade == QualityGrade.EXCELLENT
        assert r.quality_score == 95.0
        assert r.details == "exemplary blameless postmortem"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_postmortem(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_postmortem
# -------------------------------------------------------------------


class TestGetPostmortem:
    def test_found(self):
        eng = _engine()
        r = eng.record_postmortem("auth-svc")
        assert eng.get_postmortem(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_postmortem("nonexistent") is None


# -------------------------------------------------------------------
# list_postmortems
# -------------------------------------------------------------------


class TestListPostmortems:
    def test_list_all(self):
        eng = _engine()
        eng.record_postmortem("svc-a")
        eng.record_postmortem("svc-b")
        assert len(eng.list_postmortems()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_postmortem("svc-a")
        eng.record_postmortem("svc-b")
        results = eng.list_postmortems(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_postmortem("svc-a", dimension=QualityDimension.TIMELINE_ACCURACY)
        eng.record_postmortem("svc-b", dimension=QualityDimension.LEARNING_VALUE)
        results = eng.list_postmortems(dimension=QualityDimension.LEARNING_VALUE)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_dimension_score
# -------------------------------------------------------------------


class TestAddDimensionScore:
    def test_basic(self):
        eng = _engine()
        d = eng.add_dimension_score(
            "timeline-review",
            dimension=QualityDimension.TIMELINE_ACCURACY,
            grade=QualityGrade.GOOD,
            score=82.0,
        )
        assert d.dimension_name == "timeline-review"
        assert d.grade == QualityGrade.GOOD
        assert d.score == 82.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_dimension_score(f"dim-{i}")
        assert len(eng._dimensions) == 2


# -------------------------------------------------------------------
# analyze_postmortem_quality
# -------------------------------------------------------------------


class TestAnalyzePostmortemQuality:
    def test_with_data(self):
        eng = _engine(min_score=70.0)
        eng.record_postmortem("svc-a", quality_score=80.0)
        eng.record_postmortem("svc-a", quality_score=90.0)
        result = eng.analyze_postmortem_quality("svc-a")
        assert result["avg_quality_score"] == 85.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_postmortem_quality("unknown-svc")
        assert result["status"] == "no_data"

    def test_below_threshold(self):
        eng = _engine(min_score=70.0)
        eng.record_postmortem("svc-a", quality_score=50.0)
        eng.record_postmortem("svc-a", quality_score=60.0)
        result = eng.analyze_postmortem_quality("svc-a")
        assert result["meets_threshold"] is False


# -------------------------------------------------------------------
# identify_poor_postmortems
# -------------------------------------------------------------------


class TestIdentifyPoorPostmortems:
    def test_with_poor(self):
        eng = _engine()
        eng.record_postmortem("svc-a", grade=QualityGrade.POOR)
        eng.record_postmortem("svc-a", grade=QualityGrade.INCOMPLETE)
        eng.record_postmortem("svc-b", grade=QualityGrade.GOOD)
        results = eng.identify_poor_postmortems()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["poor_incomplete_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_postmortems() == []

    def test_single_poor_not_returned(self):
        eng = _engine()
        eng.record_postmortem("svc-a", grade=QualityGrade.POOR)
        assert eng.identify_poor_postmortems() == []


# -------------------------------------------------------------------
# rank_by_quality_score
# -------------------------------------------------------------------


class TestRankByQualityScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_postmortem("svc-a", quality_score=60.0)
        eng.record_postmortem("svc-b", quality_score=95.0)
        results = eng.rank_by_quality_score()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_quality_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# -------------------------------------------------------------------
# detect_quality_trends
# -------------------------------------------------------------------


class TestDetectQualityTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_postmortem("svc-a")
        eng.record_postmortem("svc-b")
        results = eng.detect_quality_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_quality_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_postmortem("svc-a")
        assert eng.detect_quality_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_postmortem("svc-a", grade=QualityGrade.POOR, quality_score=40.0)
        eng.record_postmortem("svc-b", grade=QualityGrade.EXCELLENT, quality_score=95.0)
        eng.add_dimension_score("dim-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_dimensions == 1
        assert report.poor_count == 1
        assert report.by_dimension != {}
        assert report.by_grade != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.avg_quality_score_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_postmortem("svc-a")
        eng.add_dimension_score("dim-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._dimensions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_dimensions"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_score=70.0)
        eng.record_postmortem("svc-a", dimension=QualityDimension.ROOT_CAUSE_DEPTH)
        eng.record_postmortem("svc-b", dimension=QualityDimension.LEARNING_VALUE)
        eng.add_dimension_score("dim-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_dimensions"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_score"] == 70.0
