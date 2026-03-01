"""Tests for shieldops.knowledge.feedback_loop — KnowledgeFeedbackAnalyzer."""

from __future__ import annotations

from shieldops.knowledge.feedback_loop import (
    ContentQuality,
    FeedbackRecord,
    FeedbackSource,
    FeedbackSummary,
    FeedbackType,
    KnowledgeFeedbackAnalyzer,
    KnowledgeFeedbackReport,
)


def _engine(**kw) -> KnowledgeFeedbackAnalyzer:
    return KnowledgeFeedbackAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_feedback_type_helpful(self):
        assert FeedbackType.HELPFUL == "helpful"

    def test_feedback_type_outdated(self):
        assert FeedbackType.OUTDATED == "outdated"

    def test_feedback_type_inaccurate(self):
        assert FeedbackType.INACCURATE == "inaccurate"

    def test_feedback_type_incomplete(self):
        assert FeedbackType.INCOMPLETE == "incomplete"

    def test_feedback_type_confusing(self):
        assert FeedbackType.CONFUSING == "confusing"

    def test_feedback_source_incident_response(self):
        assert FeedbackSource.INCIDENT_RESPONSE == "incident_response"

    def test_feedback_source_training(self):
        assert FeedbackSource.TRAINING == "training"

    def test_feedback_source_onboarding(self):
        assert FeedbackSource.ONBOARDING == "onboarding"

    def test_feedback_source_self_service(self):
        assert FeedbackSource.SELF_SERVICE == "self_service"

    def test_feedback_source_review(self):
        assert FeedbackSource.REVIEW == "review"

    def test_content_quality_excellent(self):
        assert ContentQuality.EXCELLENT == "excellent"

    def test_content_quality_good(self):
        assert ContentQuality.GOOD == "good"

    def test_content_quality_adequate(self):
        assert ContentQuality.ADEQUATE == "adequate"

    def test_content_quality_poor(self):
        assert ContentQuality.POOR == "poor"

    def test_content_quality_needs_rewrite(self):
        assert ContentQuality.NEEDS_REWRITE == "needs_rewrite"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_feedback_record_defaults(self):
        r = FeedbackRecord()
        assert r.id
        assert r.article_id == ""
        assert r.feedback_type == FeedbackType.HELPFUL
        assert r.feedback_source == FeedbackSource.SELF_SERVICE
        assert r.content_quality == ContentQuality.ADEQUATE
        assert r.satisfaction_score == 0.0
        assert r.reviewer == ""
        assert r.created_at > 0

    def test_feedback_summary_defaults(self):
        s = FeedbackSummary()
        assert s.id
        assert s.summary_name == ""
        assert s.feedback_type == FeedbackType.HELPFUL
        assert s.avg_satisfaction == 0.0
        assert s.total_feedbacks == 0
        assert s.description == ""
        assert s.created_at > 0

    def test_knowledge_feedback_report_defaults(self):
        r = KnowledgeFeedbackReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_summaries == 0
        assert r.reviewed_articles == 0
        assert r.avg_satisfaction_score == 0.0
        assert r.by_type == {}
        assert r.by_source == {}
        assert r.by_quality == {}
        assert r.poor_articles == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.HELPFUL,
            feedback_source=FeedbackSource.INCIDENT_RESPONSE,
            content_quality=ContentQuality.EXCELLENT,
            satisfaction_score=95.0,
            reviewer="alice",
        )
        assert r.article_id == "kb-001"
        assert r.feedback_type == FeedbackType.HELPFUL
        assert r.feedback_source == FeedbackSource.INCIDENT_RESPONSE
        assert r.content_quality == ContentQuality.EXCELLENT
        assert r.satisfaction_score == 95.0
        assert r.reviewer == "alice"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_feedback(article_id=f"kb-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_feedback
# ---------------------------------------------------------------------------


class TestGetFeedback:
    def test_found(self):
        eng = _engine()
        r = eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.OUTDATED,
        )
        result = eng.get_feedback(r.id)
        assert result is not None
        assert result.feedback_type == FeedbackType.OUTDATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_feedback("nonexistent") is None


# ---------------------------------------------------------------------------
# list_feedbacks
# ---------------------------------------------------------------------------


class TestListFeedbacks:
    def test_list_all(self):
        eng = _engine()
        eng.record_feedback(article_id="kb-001")
        eng.record_feedback(article_id="kb-002")
        assert len(eng.list_feedbacks()) == 2

    def test_filter_by_feedback_type(self):
        eng = _engine()
        eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.HELPFUL,
        )
        eng.record_feedback(
            article_id="kb-002",
            feedback_type=FeedbackType.OUTDATED,
        )
        results = eng.list_feedbacks(feedback_type=FeedbackType.HELPFUL)
        assert len(results) == 1

    def test_filter_by_feedback_source(self):
        eng = _engine()
        eng.record_feedback(
            article_id="kb-001",
            feedback_source=FeedbackSource.INCIDENT_RESPONSE,
        )
        eng.record_feedback(
            article_id="kb-002",
            feedback_source=FeedbackSource.TRAINING,
        )
        results = eng.list_feedbacks(feedback_source=FeedbackSource.INCIDENT_RESPONSE)
        assert len(results) == 1

    def test_filter_by_reviewer(self):
        eng = _engine()
        eng.record_feedback(article_id="kb-001", reviewer="alice")
        eng.record_feedback(article_id="kb-002", reviewer="bob")
        results = eng.list_feedbacks(reviewer="alice")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_feedback(article_id=f"kb-{i}")
        assert len(eng.list_feedbacks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_summary
# ---------------------------------------------------------------------------


class TestAddSummary:
    def test_basic(self):
        eng = _engine()
        s = eng.add_summary(
            summary_name="q1-feedback-review",
            feedback_type=FeedbackType.INCOMPLETE,
            avg_satisfaction=72.5,
            total_feedbacks=15,
            description="Quarterly feedback summary",
        )
        assert s.summary_name == "q1-feedback-review"
        assert s.feedback_type == FeedbackType.INCOMPLETE
        assert s.avg_satisfaction == 72.5
        assert s.total_feedbacks == 15

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_summary(summary_name=f"summary-{i}")
        assert len(eng._summaries) == 2


# ---------------------------------------------------------------------------
# analyze_feedback_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeFeedbackPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.HELPFUL,
            satisfaction_score=90.0,
        )
        eng.record_feedback(
            article_id="kb-002",
            feedback_type=FeedbackType.HELPFUL,
            satisfaction_score=80.0,
        )
        result = eng.analyze_feedback_patterns()
        assert "helpful" in result
        assert result["helpful"]["count"] == 2
        assert result["helpful"]["avg_satisfaction_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_feedback_patterns() == {}


# ---------------------------------------------------------------------------
# identify_poor_articles
# ---------------------------------------------------------------------------


class TestIdentifyPoorArticles:
    def test_detects_poor(self):
        eng = _engine(min_satisfaction_score=70.0)
        eng.record_feedback(
            article_id="kb-001",
            satisfaction_score=50.0,
        )
        eng.record_feedback(
            article_id="kb-002",
            satisfaction_score=95.0,
        )
        results = eng.identify_poor_articles()
        assert len(results) == 1
        assert results[0]["article_id"] == "kb-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_articles() == []


# ---------------------------------------------------------------------------
# rank_by_satisfaction
# ---------------------------------------------------------------------------


class TestRankBySatisfaction:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_feedback(article_id="kb-001", satisfaction_score=90.0)
        eng.record_feedback(article_id="kb-001", satisfaction_score=80.0)
        eng.record_feedback(article_id="kb-002", satisfaction_score=50.0)
        results = eng.rank_by_satisfaction()
        assert len(results) == 2
        assert results[0]["article_id"] == "kb-001"
        assert results[0]["total_satisfaction"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_satisfaction() == []


# ---------------------------------------------------------------------------
# detect_feedback_trends
# ---------------------------------------------------------------------------


class TestDetectFeedbackTrends:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.record_feedback(article_id="kb-001", satisfaction_score=score)
        result = eng.detect_feedback_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [50.0, 50.0, 90.0, 90.0]:
            eng.record_feedback(article_id="kb-001", satisfaction_score=score)
        result = eng.detect_feedback_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_feedback_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_satisfaction_score=70.0)
        eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.HELPFUL,
            feedback_source=FeedbackSource.INCIDENT_RESPONSE,
            satisfaction_score=50.0,
            reviewer="alice",
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeFeedbackReport)
        assert report.total_records == 1
        assert report.avg_satisfaction_score == 50.0
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
        eng.record_feedback(article_id="kb-001")
        eng.add_summary(summary_name="s1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._summaries) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_summaries"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_feedback(
            article_id="kb-001",
            feedback_type=FeedbackType.OUTDATED,
            reviewer="alice",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_articles"] == 1
        assert stats["unique_reviewers"] == 1
        assert "outdated" in stats["type_distribution"]
