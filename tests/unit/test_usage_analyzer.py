"""Tests for shieldops.knowledge.usage_analyzer — KnowledgeUsageAnalyzer."""

from __future__ import annotations

from shieldops.knowledge.usage_analyzer import (
    ContentCategory,
    KnowledgeUsageAnalyzer,
    UsageAnalysisReport,
    UsageRecord,
    UsageRule,
    UsageTrend,
    UsageType,
)


def _engine(**kw) -> KnowledgeUsageAnalyzer:
    return KnowledgeUsageAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_usage_type_view(self):
        assert UsageType.VIEW == "view"

    def test_usage_type_search(self):
        assert UsageType.SEARCH == "search"

    def test_usage_type_reference(self):
        assert UsageType.REFERENCE == "reference"

    def test_usage_type_share(self):
        assert UsageType.SHARE == "share"

    def test_usage_type_feedback(self):
        assert UsageType.FEEDBACK == "feedback"

    def test_content_category_runbook(self):
        assert ContentCategory.RUNBOOK == "runbook"

    def test_content_category_postmortem(self):
        assert ContentCategory.POSTMORTEM == "postmortem"

    def test_content_category_faq(self):
        assert ContentCategory.FAQ == "faq"

    def test_content_category_architecture(self):
        assert ContentCategory.ARCHITECTURE == "architecture"

    def test_content_category_troubleshooting(self):
        assert ContentCategory.TROUBLESHOOTING == "troubleshooting"

    def test_usage_trend_growing(self):
        assert UsageTrend.GROWING == "growing"

    def test_usage_trend_stable(self):
        assert UsageTrend.STABLE == "stable"

    def test_usage_trend_declining(self):
        assert UsageTrend.DECLINING == "declining"

    def test_usage_trend_seasonal(self):
        assert UsageTrend.SEASONAL == "seasonal"

    def test_usage_trend_new(self):
        assert UsageTrend.NEW == "new"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_usage_record_defaults(self):
        r = UsageRecord()
        assert r.id
        assert r.article_id == ""
        assert r.usage_type == UsageType.VIEW
        assert r.content_category == ContentCategory.RUNBOOK
        assert r.usage_trend == UsageTrend.NEW
        assert r.view_count == 0
        assert r.team == ""
        assert r.created_at > 0

    def test_usage_rule_defaults(self):
        p = UsageRule()
        assert p.id
        assert p.category_pattern == ""
        assert p.content_category == ContentCategory.RUNBOOK
        assert p.min_views == 0
        assert p.stale_after_days == 90
        assert p.description == ""
        assert p.created_at > 0

    def test_usage_analysis_report_defaults(self):
        r = UsageAnalysisReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.active_articles == 0
        assert r.avg_view_count == 0.0
        assert r.by_type == {}
        assert r.by_category == {}
        assert r.by_trend == {}
        assert r.underused == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_usage
# ---------------------------------------------------------------------------


class TestRecordUsage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.SEARCH,
            content_category=ContentCategory.POSTMORTEM,
            usage_trend=UsageTrend.GROWING,
            view_count=100,
            team="sre",
        )
        assert r.article_id == "ART-001"
        assert r.usage_type == UsageType.SEARCH
        assert r.content_category == ContentCategory.POSTMORTEM
        assert r.usage_trend == UsageTrend.GROWING
        assert r.view_count == 100
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_usage(article_id=f"ART-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_usage
# ---------------------------------------------------------------------------


class TestGetUsage:
    def test_found(self):
        eng = _engine()
        r = eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.REFERENCE,
        )
        result = eng.get_usage(r.id)
        assert result is not None
        assert result.usage_type == UsageType.REFERENCE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_usage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_usages
# ---------------------------------------------------------------------------


class TestListUsages:
    def test_list_all(self):
        eng = _engine()
        eng.record_usage(article_id="ART-001")
        eng.record_usage(article_id="ART-002")
        assert len(eng.list_usages()) == 2

    def test_filter_by_usage_type(self):
        eng = _engine()
        eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.VIEW,
        )
        eng.record_usage(
            article_id="ART-002",
            usage_type=UsageType.SHARE,
        )
        results = eng.list_usages(usage_type=UsageType.VIEW)
        assert len(results) == 1

    def test_filter_by_content_category(self):
        eng = _engine()
        eng.record_usage(
            article_id="ART-001",
            content_category=ContentCategory.FAQ,
        )
        eng.record_usage(
            article_id="ART-002",
            content_category=ContentCategory.ARCHITECTURE,
        )
        results = eng.list_usages(content_category=ContentCategory.FAQ)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_usage(article_id="ART-001", team="sre")
        eng.record_usage(article_id="ART-002", team="platform")
        results = eng.list_usages(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_usage(article_id=f"ART-{i}")
        assert len(eng.list_usages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            category_pattern="runbook-*",
            content_category=ContentCategory.TROUBLESHOOTING,
            min_views=10,
            stale_after_days=60,
            description="Troubleshooting guide rule",
        )
        assert p.category_pattern == "runbook-*"
        assert p.content_category == ContentCategory.TROUBLESHOOTING
        assert p.min_views == 10
        assert p.stale_after_days == 60

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(category_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_usage_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeUsagePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.VIEW,
            view_count=100,
        )
        eng.record_usage(
            article_id="ART-002",
            usage_type=UsageType.VIEW,
            view_count=200,
        )
        result = eng.analyze_usage_patterns()
        assert "view" in result
        assert result["view"]["count"] == 2
        assert result["view"]["avg_view_count"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_usage_patterns() == {}


# ---------------------------------------------------------------------------
# identify_underused
# ---------------------------------------------------------------------------


class TestIdentifyUnderused:
    def test_detects_underused(self):
        eng = _engine(min_usage_score=50.0)
        eng.record_usage(
            article_id="ART-001",
            view_count=10,
        )
        eng.record_usage(
            article_id="ART-002",
            view_count=200,
        )
        results = eng.identify_underused()
        assert len(results) == 1
        assert results[0]["article_id"] == "ART-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underused() == []


# ---------------------------------------------------------------------------
# rank_by_views
# ---------------------------------------------------------------------------


class TestRankByViews:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_usage(article_id="ART-001", team="sre", view_count=100)
        eng.record_usage(article_id="ART-002", team="sre", view_count=200)
        eng.record_usage(article_id="ART-003", team="platform", view_count=50)
        results = eng.rank_by_views()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_views"] == 300

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_views() == []


# ---------------------------------------------------------------------------
# detect_usage_trends
# ---------------------------------------------------------------------------


class TestDetectUsageTrends:
    def test_stable(self):
        eng = _engine()
        for count in [10, 10, 10, 10]:
            eng.record_usage(article_id="ART", view_count=count)
        result = eng.detect_usage_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for count in [5, 5, 20, 20]:
            eng.record_usage(article_id="ART", view_count=count)
        result = eng.detect_usage_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_usage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_usage_score=50.0)
        eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.VIEW,
            content_category=ContentCategory.RUNBOOK,
            view_count=10,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, UsageAnalysisReport)
        assert report.total_records == 1
        assert report.avg_view_count == 10.0
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
        eng.record_usage(article_id="ART-001")
        eng.add_rule(category_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_usage(
            article_id="ART-001",
            usage_type=UsageType.SEARCH,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_articles"] == 1
        assert "search" in stats["type_distribution"]
