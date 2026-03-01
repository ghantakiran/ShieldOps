"""Tests for shieldops.knowledge.knowledge_freshness_scorer — KnowledgeFreshnessScorer."""

from __future__ import annotations

from shieldops.knowledge.knowledge_freshness_scorer import (
    ArticleType,
    FreshnessLevel,
    FreshnessMetric,
    FreshnessRecord,
    KnowledgeFreshnessReport,
    KnowledgeFreshnessScorer,
    UpdateFrequency,
)


def _engine(**kw) -> KnowledgeFreshnessScorer:
    return KnowledgeFreshnessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_current(self):
        assert FreshnessLevel.CURRENT == "current"

    def test_level_recent(self):
        assert FreshnessLevel.RECENT == "recent"

    def test_level_aging(self):
        assert FreshnessLevel.AGING == "aging"

    def test_level_stale(self):
        assert FreshnessLevel.STALE == "stale"

    def test_level_obsolete(self):
        assert FreshnessLevel.OBSOLETE == "obsolete"

    def test_type_runbook(self):
        assert ArticleType.RUNBOOK == "runbook"

    def test_type_playbook(self):
        assert ArticleType.PLAYBOOK == "playbook"

    def test_type_faq(self):
        assert ArticleType.FAQ == "faq"

    def test_type_architecture(self):
        assert ArticleType.ARCHITECTURE == "architecture"

    def test_type_onboarding(self):
        assert ArticleType.ONBOARDING == "onboarding"

    def test_freq_weekly(self):
        assert UpdateFrequency.WEEKLY == "weekly"

    def test_freq_monthly(self):
        assert UpdateFrequency.MONTHLY == "monthly"

    def test_freq_quarterly(self):
        assert UpdateFrequency.QUARTERLY == "quarterly"

    def test_freq_annually(self):
        assert UpdateFrequency.ANNUALLY == "annually"

    def test_freq_never(self):
        assert UpdateFrequency.NEVER == "never"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_freshness_record_defaults(self):
        r = FreshnessRecord()
        assert r.id
        assert r.article_id == ""
        assert r.freshness_level == FreshnessLevel.CURRENT
        assert r.article_type == ArticleType.RUNBOOK
        assert r.update_frequency == UpdateFrequency.MONTHLY
        assert r.freshness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_freshness_metric_defaults(self):
        m = FreshnessMetric()
        assert m.id
        assert m.article_id == ""
        assert m.freshness_level == FreshnessLevel.CURRENT
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.created_at > 0

    def test_freshness_report_defaults(self):
        r = KnowledgeFreshnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.stale_count == 0
        assert r.avg_freshness_score == 0.0
        assert r.by_level == {}
        assert r.by_type == {}
        assert r.by_frequency == {}
        assert r.top_stale == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_freshness
# ---------------------------------------------------------------------------


class TestRecordFreshness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.STALE,
            article_type=ArticleType.RUNBOOK,
            update_frequency=UpdateFrequency.MONTHLY,
            freshness_score=35.0,
            service="api-gw",
            team="sre",
        )
        assert r.article_id == "ART-001"
        assert r.freshness_level == FreshnessLevel.STALE
        assert r.article_type == ArticleType.RUNBOOK
        assert r.update_frequency == UpdateFrequency.MONTHLY
        assert r.freshness_score == 35.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_freshness(article_id=f"ART-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_freshness
# ---------------------------------------------------------------------------


class TestGetFreshness:
    def test_found(self):
        eng = _engine()
        r = eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.CURRENT,
        )
        result = eng.get_freshness(r.id)
        assert result is not None
        assert result.freshness_level == FreshnessLevel.CURRENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_freshness("nonexistent") is None


# ---------------------------------------------------------------------------
# list_freshness
# ---------------------------------------------------------------------------


class TestListFreshness:
    def test_list_all(self):
        eng = _engine()
        eng.record_freshness(article_id="ART-001")
        eng.record_freshness(article_id="ART-002")
        assert len(eng.list_freshness()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.CURRENT,
        )
        eng.record_freshness(
            article_id="ART-002",
            freshness_level=FreshnessLevel.STALE,
        )
        results = eng.list_freshness(level=FreshnessLevel.CURRENT)
        assert len(results) == 1

    def test_filter_by_article_type(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            article_type=ArticleType.RUNBOOK,
        )
        eng.record_freshness(
            article_id="ART-002",
            article_type=ArticleType.FAQ,
        )
        results = eng.list_freshness(article_type=ArticleType.RUNBOOK)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_freshness(article_id="ART-001", team="sre")
        eng.record_freshness(article_id="ART-002", team="platform")
        results = eng.list_freshness(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_freshness(article_id=f"ART-{i}")
        assert len(eng.list_freshness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            article_id="ART-001",
            freshness_level=FreshnessLevel.AGING,
            metric_score=55.0,
            threshold=60.0,
            breached=True,
            description="Below threshold",
        )
        assert m.article_id == "ART-001"
        assert m.freshness_level == FreshnessLevel.AGING
        assert m.metric_score == 55.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(article_id=f"ART-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_freshness_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeFreshnessDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.CURRENT,
            freshness_score=90.0,
        )
        eng.record_freshness(
            article_id="ART-002",
            freshness_level=FreshnessLevel.CURRENT,
            freshness_score=80.0,
        )
        result = eng.analyze_freshness_distribution()
        assert "current" in result
        assert result["current"]["count"] == 2
        assert result["current"]["avg_freshness_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_freshness_distribution() == {}


# ---------------------------------------------------------------------------
# identify_stale_articles
# ---------------------------------------------------------------------------


class TestIdentifyStaleArticles:
    def test_detects_stale(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.STALE,
        )
        eng.record_freshness(
            article_id="ART-002",
            freshness_level=FreshnessLevel.CURRENT,
        )
        results = eng.identify_stale_articles()
        assert len(results) == 1
        assert results[0]["article_id"] == "ART-001"

    def test_detects_obsolete(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.OBSOLETE,
        )
        results = eng.identify_stale_articles()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_articles() == []


# ---------------------------------------------------------------------------
# rank_by_freshness
# ---------------------------------------------------------------------------


class TestRankByFreshness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            service="api-gw",
            freshness_score=90.0,
        )
        eng.record_freshness(
            article_id="ART-002",
            service="auth",
            freshness_score=40.0,
        )
        results = eng.rank_by_freshness()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_freshness_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_freshness() == []


# ---------------------------------------------------------------------------
# detect_freshness_trends
# ---------------------------------------------------------------------------


class TestDetectFreshnessTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(article_id="ART-001", metric_score=50.0)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(article_id="ART-001", metric_score=30.0)
        eng.add_metric(article_id="ART-002", metric_score=30.0)
        eng.add_metric(article_id="ART-003", metric_score=50.0)
        eng.add_metric(article_id="ART-004", metric_score=50.0)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_freshness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.STALE,
            article_type=ArticleType.RUNBOOK,
            freshness_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeFreshnessReport)
        assert report.total_records == 1
        assert report.stale_count == 1
        assert len(report.top_stale) == 1
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
        eng.record_freshness(article_id="ART-001")
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
        assert stats["freshness_level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_freshness(
            article_id="ART-001",
            freshness_level=FreshnessLevel.CURRENT,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "current" in stats["freshness_level_distribution"]
