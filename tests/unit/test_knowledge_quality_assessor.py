"""Tests for shieldops.knowledge.knowledge_quality_assessor — KnowledgeQualityAssessor."""

from __future__ import annotations

from shieldops.knowledge.knowledge_quality_assessor import (
    ContentCategory,
    KnowledgeQualityAssessor,
    KnowledgeQualityReport,
    QualityAspect,
    QualityMetric,
    QualityRating,
    QualityRecord,
)


def _engine(**kw) -> KnowledgeQualityAssessor:
    return KnowledgeQualityAssessor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_aspect_accuracy(self):
        assert QualityAspect.ACCURACY == "accuracy"

    def test_aspect_completeness(self):
        assert QualityAspect.COMPLETENESS == "completeness"

    def test_aspect_clarity(self):
        assert QualityAspect.CLARITY == "clarity"

    def test_aspect_relevance(self):
        assert QualityAspect.RELEVANCE == "relevance"

    def test_aspect_consistency(self):
        assert QualityAspect.CONSISTENCY == "consistency"

    def test_rating_excellent(self):
        assert QualityRating.EXCELLENT == "excellent"

    def test_rating_good(self):
        assert QualityRating.GOOD == "good"

    def test_rating_acceptable(self):
        assert QualityRating.ACCEPTABLE == "acceptable"

    def test_rating_poor(self):
        assert QualityRating.POOR == "poor"

    def test_rating_unacceptable(self):
        assert QualityRating.UNACCEPTABLE == "unacceptable"

    def test_category_technical(self):
        assert ContentCategory.TECHNICAL == "technical"

    def test_category_procedural(self):
        assert ContentCategory.PROCEDURAL == "procedural"

    def test_category_architectural(self):
        assert ContentCategory.ARCHITECTURAL == "architectural"

    def test_category_operational(self):
        assert ContentCategory.OPERATIONAL == "operational"

    def test_category_reference(self):
        assert ContentCategory.REFERENCE == "reference"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_quality_record_defaults(self):
        r = QualityRecord()
        assert r.id
        assert r.article_id == ""
        assert r.quality_aspect == QualityAspect.ACCURACY
        assert r.quality_rating == QualityRating.ACCEPTABLE
        assert r.content_category == ContentCategory.TECHNICAL
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_quality_metric_defaults(self):
        m = QualityMetric()
        assert m.id
        assert m.article_id == ""
        assert m.quality_aspect == QualityAspect.ACCURACY
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_quality_report_defaults(self):
        r = KnowledgeQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.poor_quality_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_aspect == {}
        assert r.by_rating == {}
        assert r.by_category == {}
        assert r.top_poor == []
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
            article_id="ART-001",
            quality_aspect=QualityAspect.ACCURACY,
            quality_rating=QualityRating.GOOD,
            content_category=ContentCategory.TECHNICAL,
            quality_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.article_id == "ART-001"
        assert r.quality_aspect == QualityAspect.ACCURACY
        assert r.quality_rating == QualityRating.GOOD
        assert r.content_category == ContentCategory.TECHNICAL
        assert r.quality_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(article_id=f"ART-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


class TestGetQuality:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(
            article_id="ART-001",
            quality_rating=QualityRating.EXCELLENT,
        )
        result = eng.get_quality(r.id)
        assert result is not None
        assert result.quality_rating == QualityRating.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_qualities
# ---------------------------------------------------------------------------


class TestListQualities:
    def test_list_all(self):
        eng = _engine()
        eng.record_quality(article_id="ART-001")
        eng.record_quality(article_id="ART-002")
        assert len(eng.list_qualities()) == 2

    def test_filter_by_aspect(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_aspect=QualityAspect.ACCURACY,
        )
        eng.record_quality(
            article_id="ART-002",
            quality_aspect=QualityAspect.CLARITY,
        )
        results = eng.list_qualities(aspect=QualityAspect.ACCURACY)
        assert len(results) == 1

    def test_filter_by_rating(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_rating=QualityRating.EXCELLENT,
        )
        eng.record_quality(
            article_id="ART-002",
            quality_rating=QualityRating.POOR,
        )
        results = eng.list_qualities(rating=QualityRating.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_quality(article_id="ART-001", team="sre")
        eng.record_quality(article_id="ART-002", team="platform")
        results = eng.list_qualities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(article_id=f"ART-{i}")
        assert len(eng.list_qualities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            article_id="ART-001",
            quality_aspect=QualityAspect.COMPLETENESS,
            metric_score=72.0,
            threshold=70.0,
            breached=True,
            description="Completeness below target",
        )
        assert m.article_id == "ART-001"
        assert m.quality_aspect == QualityAspect.COMPLETENESS
        assert m.metric_score == 72.0
        assert m.threshold == 70.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(article_id=f"ART-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_quality_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeQualityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_aspect=QualityAspect.ACCURACY,
            quality_score=80.0,
        )
        eng.record_quality(
            article_id="ART-002",
            quality_aspect=QualityAspect.ACCURACY,
            quality_score=90.0,
        )
        result = eng.analyze_quality_distribution()
        assert "accuracy" in result
        assert result["accuracy"]["count"] == 2
        assert result["accuracy"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_quality_distribution() == {}


# ---------------------------------------------------------------------------
# identify_poor_quality
# ---------------------------------------------------------------------------


class TestIdentifyPoorQuality:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_rating=QualityRating.POOR,
        )
        eng.record_quality(
            article_id="ART-002",
            quality_rating=QualityRating.EXCELLENT,
        )
        results = eng.identify_poor_quality()
        assert len(results) == 1
        assert results[0]["article_id"] == "ART-001"

    def test_detects_unacceptable(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_rating=QualityRating.UNACCEPTABLE,
        )
        results = eng.identify_poor_quality()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_quality() == []


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankByQuality:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_quality(article_id="ART-001", quality_score=90.0, service="svc-a")
        eng.record_quality(article_id="ART-002", quality_score=50.0, service="svc-b")
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
            eng.add_metric(article_id="ART-001", metric_score=70.0)
        result = eng.detect_quality_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(article_id="ART-001", metric_score=50.0)
        eng.add_metric(article_id="ART-002", metric_score=50.0)
        eng.add_metric(article_id="ART-003", metric_score=80.0)
        eng.add_metric(article_id="ART-004", metric_score=80.0)
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
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_aspect=QualityAspect.ACCURACY,
            quality_rating=QualityRating.POOR,
            quality_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeQualityReport)
        assert report.total_records == 1
        assert report.poor_quality_count == 1
        assert len(report.top_poor) == 1
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
        eng.record_quality(article_id="ART-001")
        eng.add_metric(article_id="ART-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["aspect_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            article_id="ART-001",
            quality_aspect=QualityAspect.ACCURACY,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "accuracy" in stats["aspect_distribution"]
