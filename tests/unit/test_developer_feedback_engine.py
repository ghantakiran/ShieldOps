"""Tests for developer_feedback_engine — DeveloperFeedbackEngine."""

from __future__ import annotations

from shieldops.knowledge.developer_feedback_engine import (
    DeveloperFeedbackEngine,
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
)


def _engine(**kw) -> DeveloperFeedbackEngine:
    return DeveloperFeedbackEngine(**kw)


class TestEnums:
    def test_feedbackcategory_tooling(self):
        assert FeedbackCategory.TOOLING == "tooling"

    def test_feedbackcategory_documentation(self):
        assert FeedbackCategory.DOCUMENTATION == "documentation"

    def test_feedbackcategory_infrastructure(self):
        assert FeedbackCategory.INFRASTRUCTURE == "infrastructure"

    def test_feedbackcategory_process(self):
        assert FeedbackCategory.PROCESS == "process"

    def test_feedbackcategory_culture(self):
        assert FeedbackCategory.CULTURE == "culture"

    def test_feedbacksentiment_positive(self):
        assert FeedbackSentiment.POSITIVE == "positive"

    def test_feedbacksentiment_neutral(self):
        assert FeedbackSentiment.NEUTRAL == "neutral"

    def test_feedbacksentiment_negative(self):
        assert FeedbackSentiment.NEGATIVE == "negative"

    def test_feedbacksentiment_mixed(self):
        assert FeedbackSentiment.MIXED == "mixed"

    def test_feedbacksentiment_unknown(self):
        assert FeedbackSentiment.UNKNOWN == "unknown"

    def test_feedbackchannel_survey(self):
        assert FeedbackChannel.SURVEY == "survey"

    def test_feedbackchannel_retro(self):
        assert FeedbackChannel.RETRO == "retro"

    def test_feedbackchannel_slack(self):
        assert FeedbackChannel.SLACK == "slack"

    def test_feedbackchannel_ticket(self):
        assert FeedbackChannel.TICKET == "ticket"

    def test_feedbackchannel_interview(self):
        assert FeedbackChannel.INTERVIEW == "interview"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="test-001",
            feedback_category=FeedbackCategory.TOOLING,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.feedback_category == FeedbackCategory.TOOLING
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.add_record(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_feedback_category(self):
        eng = _engine()
        eng.add_record(
            name="a",
            feedback_category=FeedbackCategory.TOOLING,
        )
        eng.add_record(
            name="b",
            feedback_category=FeedbackCategory.DOCUMENTATION,
        )
        result = eng.list_records(
            feedback_category=FeedbackCategory.TOOLING,
        )
        assert len(result) == 1

    def test_filter_by_feedback_sentiment(self):
        eng = _engine()
        eng.add_record(
            name="a",
            feedback_sentiment=FeedbackSentiment.POSITIVE,
        )
        eng.add_record(
            name="b",
            feedback_sentiment=FeedbackSentiment.NEGATIVE,
        )
        result = eng.list_records(
            feedback_sentiment=FeedbackSentiment.POSITIVE,
        )
        assert len(result) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.add_record(name="a", team="sec")
        eng.add_record(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.add_record(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            feedback_category=FeedbackCategory.TOOLING,
            score=90.0,
        )
        eng.add_record(
            name="b",
            feedback_category=FeedbackCategory.TOOLING,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "tooling" in result
        assert result["tooling"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=60.0)
        eng.add_record(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=50.0)
        eng.add_record(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.add_record(
            name="b",
            service="api",
            score=50.0,
        )
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                name="t",
                analysis_score=50.0,
            )
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(
            name="a",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="b",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="c",
            analysis_score=80.0,
        )
        eng.add_analysis(
            name="d",
            analysis_score=80.0,
        )
        result = eng.detect_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_record(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
