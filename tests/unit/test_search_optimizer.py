"""Tests for shieldops.knowledge.search_optimizer — KnowledgeSearchOptimizer."""

from __future__ import annotations

from shieldops.knowledge.search_optimizer import (
    ContentType,
    KnowledgeSearchOptimizer,
    KnowledgeSearchReport,
    SearchPattern,
    SearchQuality,
    SearchRecord,
    UsageFrequency,
)


def _engine(**kw) -> KnowledgeSearchOptimizer:
    return KnowledgeSearchOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_quality_excellent(self):
        assert SearchQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert SearchQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert SearchQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert SearchQuality.POOR == "poor"

    def test_quality_no_results(self):
        assert SearchQuality.NO_RESULTS == "no_results"

    def test_content_runbook(self):
        assert ContentType.RUNBOOK == "runbook"

    def test_content_playbook(self):
        assert ContentType.PLAYBOOK == "playbook"

    def test_content_postmortem(self):
        assert ContentType.POSTMORTEM == "postmortem"

    def test_content_faq(self):
        assert ContentType.FAQ == "faq"

    def test_content_troubleshooting(self):
        assert ContentType.TROUBLESHOOTING == "troubleshooting"

    def test_frequency_daily(self):
        assert UsageFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert UsageFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert UsageFrequency.MONTHLY == "monthly"

    def test_frequency_rarely(self):
        assert UsageFrequency.RARELY == "rarely"

    def test_frequency_never(self):
        assert UsageFrequency.NEVER == "never"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_search_record_defaults(self):
        r = SearchRecord()
        assert r.id
        assert r.query == ""
        assert r.content_type == ContentType.RUNBOOK
        assert r.search_quality == SearchQuality.ADEQUATE
        assert r.usage_frequency == UsageFrequency.MONTHLY
        assert r.relevance_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_search_pattern_defaults(self):
        p = SearchPattern()
        assert p.id
        assert p.query_pattern == ""
        assert p.content_type == ContentType.RUNBOOK
        assert p.search_quality == SearchQuality.ADEQUATE
        assert p.hit_count == 0
        assert p.avg_relevance == 0.0
        assert p.created_at > 0

    def test_search_report_defaults(self):
        r = KnowledgeSearchReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.poor_search_count == 0
        assert r.avg_relevance_score == 0.0
        assert r.by_quality == {}
        assert r.by_content == {}
        assert r.by_frequency == {}
        assert r.low_relevance_queries == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_search
# ---------------------------------------------------------------------------


class TestRecordSearch:
    def test_basic(self):
        eng = _engine()
        r = eng.record_search(
            query="restart pod",
            content_type=ContentType.RUNBOOK,
            search_quality=SearchQuality.GOOD,
            relevance_score=85.0,
            team="sre",
        )
        assert r.query == "restart pod"
        assert r.content_type == ContentType.RUNBOOK
        assert r.search_quality == SearchQuality.GOOD
        assert r.relevance_score == 85.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_search(query=f"query-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_search
# ---------------------------------------------------------------------------


class TestGetSearch:
    def test_found(self):
        eng = _engine()
        r = eng.record_search(query="deploy issue", relevance_score=90.0)
        result = eng.get_search(r.id)
        assert result is not None
        assert result.relevance_score == 90.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_search("nonexistent") is None


# ---------------------------------------------------------------------------
# list_searches
# ---------------------------------------------------------------------------


class TestListSearches:
    def test_list_all(self):
        eng = _engine()
        eng.record_search(query="q1")
        eng.record_search(query="q2")
        assert len(eng.list_searches()) == 2

    def test_filter_by_content_type(self):
        eng = _engine()
        eng.record_search(query="q1", content_type=ContentType.RUNBOOK)
        eng.record_search(query="q2", content_type=ContentType.FAQ)
        results = eng.list_searches(content_type=ContentType.RUNBOOK)
        assert len(results) == 1

    def test_filter_by_quality(self):
        eng = _engine()
        eng.record_search(query="q1", search_quality=SearchQuality.POOR)
        eng.record_search(query="q2", search_quality=SearchQuality.GOOD)
        results = eng.list_searches(quality=SearchQuality.POOR)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_search(query="q1", team="sre")
        eng.record_search(query="q2", team="platform")
        results = eng.list_searches(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_search(query=f"q-{i}")
        assert len(eng.list_searches(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_pattern
# ---------------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            query_pattern="restart*",
            content_type=ContentType.RUNBOOK,
            hit_count=42,
            avg_relevance=78.5,
        )
        assert p.query_pattern == "restart*"
        assert p.content_type == ContentType.RUNBOOK
        assert p.hit_count == 42
        assert p.avg_relevance == 78.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_pattern(query_pattern=f"pat-{i}")
        assert len(eng._patterns) == 2


# ---------------------------------------------------------------------------
# analyze_search_quality
# ---------------------------------------------------------------------------


class TestAnalyzeSearchQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_search(
            query="q1",
            search_quality=SearchQuality.GOOD,
            relevance_score=80.0,
        )
        eng.record_search(
            query="q2",
            search_quality=SearchQuality.GOOD,
            relevance_score=60.0,
        )
        result = eng.analyze_search_quality()
        assert "good" in result
        assert result["good"]["count"] == 2
        assert result["good"]["avg_relevance"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_search_quality() == {}


# ---------------------------------------------------------------------------
# identify_poor_searches
# ---------------------------------------------------------------------------


class TestIdentifyPoorSearches:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_search(
            query="broken",
            search_quality=SearchQuality.POOR,
        )
        eng.record_search(
            query="good q",
            search_quality=SearchQuality.GOOD,
        )
        results = eng.identify_poor_searches()
        assert len(results) == 1
        assert results[0]["search_quality"] == "poor"

    def test_detects_no_results(self):
        eng = _engine()
        eng.record_search(
            query="missing",
            search_quality=SearchQuality.NO_RESULTS,
        )
        results = eng.identify_poor_searches()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_searches() == []


# ---------------------------------------------------------------------------
# rank_by_relevance
# ---------------------------------------------------------------------------


class TestRankByRelevance:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_search(
            query="q1",
            content_type=ContentType.RUNBOOK,
            relevance_score=90.0,
        )
        eng.record_search(
            query="q2",
            content_type=ContentType.FAQ,
            relevance_score=60.0,
        )
        results = eng.rank_by_relevance()
        assert len(results) == 2
        assert results[0]["content_type"] == "runbook"
        assert results[0]["avg_relevance"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_relevance() == []


# ---------------------------------------------------------------------------
# detect_search_trends
# ---------------------------------------------------------------------------


class TestDetectSearchTrends:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.record_search(query="q", relevance_score=score)
        result = eng.detect_search_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [50.0, 50.0, 90.0, 90.0]:
            eng.record_search(query="q", relevance_score=score)
        result = eng.detect_search_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_search_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_search(
            query="restart pod",
            search_quality=SearchQuality.POOR,
            relevance_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeSearchReport)
        assert report.total_records == 1
        assert report.poor_search_count == 1
        assert len(report.low_relevance_queries) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_search(query="q1")
        eng.add_pattern(query_pattern="pat1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["quality_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_search(
            query="restart pod",
            search_quality=SearchQuality.GOOD,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_queries"] == 1
        assert "good" in stats["quality_distribution"]
