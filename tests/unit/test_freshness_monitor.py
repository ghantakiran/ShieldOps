"""Tests for shieldops.knowledge.freshness_monitor — KnowledgeFreshnessMonitor."""

from __future__ import annotations

from shieldops.knowledge.freshness_monitor import (
    ContentType,
    FreshnessAlert,
    FreshnessLevel,
    FreshnessRecord,
    KnowledgeFreshnessMonitor,
    KnowledgeFreshnessReport,
    UpdatePriority,
)


def _engine(**kw) -> KnowledgeFreshnessMonitor:
    return KnowledgeFreshnessMonitor(**kw)


class TestEnums:
    def test_freshness_current(self):
        assert FreshnessLevel.CURRENT == "current"

    def test_freshness_recent(self):
        assert FreshnessLevel.RECENT == "recent"

    def test_freshness_aging(self):
        assert FreshnessLevel.AGING == "aging"

    def test_freshness_stale(self):
        assert FreshnessLevel.STALE == "stale"

    def test_freshness_expired(self):
        assert FreshnessLevel.EXPIRED == "expired"

    def test_content_runbook(self):
        assert ContentType.RUNBOOK == "runbook"

    def test_content_documentation(self):
        assert ContentType.DOCUMENTATION == "documentation"

    def test_content_playbook(self):
        assert ContentType.PLAYBOOK == "playbook"

    def test_content_faq(self):
        assert ContentType.FAQ == "faq"

    def test_content_architecture_diagram(self):
        assert ContentType.ARCHITECTURE_DIAGRAM == "architecture_diagram"

    def test_priority_urgent(self):
        assert UpdatePriority.URGENT == "urgent"

    def test_priority_high(self):
        assert UpdatePriority.HIGH == "high"

    def test_priority_medium(self):
        assert UpdatePriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert UpdatePriority.LOW == "low"

    def test_priority_optional(self):
        assert UpdatePriority.OPTIONAL == "optional"


class TestModels:
    def test_freshness_record_defaults(self):
        r = FreshnessRecord()
        assert r.id
        assert r.article_id == ""
        assert r.freshness == FreshnessLevel.CURRENT
        assert r.content_type == ContentType.DOCUMENTATION
        assert r.priority == UpdatePriority.MEDIUM
        assert r.age_days == 0.0
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_freshness_alert_defaults(self):
        a = FreshnessAlert()
        assert a.id
        assert a.record_id == ""
        assert a.alert_reason == ""
        assert a.priority == UpdatePriority.MEDIUM
        assert a.recommended_action == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = KnowledgeFreshnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_alerts == 0
        assert r.stale_count == 0
        assert r.expired_count == 0
        assert r.avg_age_days == 0.0
        assert r.by_freshness == {}
        assert r.by_content_type == {}
        assert r.by_priority == {}
        assert r.most_stale == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecordFreshness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_freshness("article-1", age_days=30.0)
        assert r.article_id == "article-1"
        assert r.age_days == 30.0

    def test_with_freshness_level(self):
        eng = _engine()
        r = eng.record_freshness("article-2", freshness=FreshnessLevel.STALE)
        assert r.freshness == FreshnessLevel.STALE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_freshness(f"article-{i}")
        assert len(eng._records) == 3


class TestGetFreshness:
    def test_found(self):
        eng = _engine()
        r = eng.record_freshness("article-1")
        assert eng.get_freshness(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_freshness("nonexistent") is None


class TestListFreshnessRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_freshness("a1")
        eng.record_freshness("a2")
        assert len(eng.list_freshness_records()) == 2

    def test_filter_by_freshness(self):
        eng = _engine()
        eng.record_freshness("a1", freshness=FreshnessLevel.STALE)
        eng.record_freshness("a2", freshness=FreshnessLevel.CURRENT)
        results = eng.list_freshness_records(freshness=FreshnessLevel.STALE)
        assert len(results) == 1

    def test_filter_by_content_type(self):
        eng = _engine()
        eng.record_freshness("a1", content_type=ContentType.RUNBOOK)
        eng.record_freshness("a2", content_type=ContentType.FAQ)
        results = eng.list_freshness_records(content_type=ContentType.RUNBOOK)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_freshness("a1", team="sre")
        eng.record_freshness("a2", team="dev")
        results = eng.list_freshness_records(team="sre")
        assert len(results) == 1


class TestAddAlert:
    def test_basic(self):
        eng = _engine()
        a = eng.add_alert("rec-1", alert_reason="Too old", priority=UpdatePriority.URGENT)
        assert a.record_id == "rec-1"
        assert a.alert_reason == "Too old"
        assert a.priority == UpdatePriority.URGENT

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_alert(f"rec-{i}")
        assert len(eng._alerts) == 2


class TestAnalyzeFreshnessDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness("a1", content_type=ContentType.RUNBOOK, age_days=20.0)
        eng.record_freshness("a2", content_type=ContentType.RUNBOOK, age_days=40.0)
        eng.record_freshness("a3", content_type=ContentType.FAQ, age_days=10.0)
        result = eng.analyze_freshness_distribution()
        assert "runbook" in result
        assert result["runbook"]["count"] == 2
        assert result["runbook"]["avg_age_days"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_freshness_distribution() == {}


class TestIdentifyStaleContent:
    def test_with_stale(self):
        eng = _engine(max_stale_days=60.0)
        eng.record_freshness("old-article", age_days=100.0, team="sre")
        eng.record_freshness("new-article", age_days=10.0, team="sre")
        results = eng.identify_stale_content()
        assert len(results) == 1
        assert results[0]["article_id"] == "old-article"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_content() == []


class TestRankByAge:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness("a1", team="sre", age_days=80.0)
        eng.record_freshness("a2", team="dev", age_days=20.0)
        results = eng.rank_by_age()
        assert results[0]["team"] == "sre"
        assert results[0]["avg_age_days"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_age() == []


class TestDetectFreshnessTrends:
    def test_worsening(self):
        eng = _engine()
        for age in [10.0, 10.0, 80.0, 80.0]:
            eng.record_freshness("a", age_days=age)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "worsening"

    def test_improving(self):
        eng = _engine()
        for age in [80.0, 80.0, 10.0, 10.0]:
            eng.record_freshness("a", age_days=age)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_freshness("a1", age_days=10.0)
        result = eng.detect_freshness_trends()
        assert result["status"] == "insufficient_data"


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness("a1", freshness=FreshnessLevel.STALE, age_days=95.0)
        eng.record_freshness("a2", freshness=FreshnessLevel.EXPIRED, age_days=200.0)
        eng.add_alert("rec-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_alerts == 1
        assert report.stale_count == 1
        assert report.expired_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_freshness("a1")
        eng.add_alert("rec-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._alerts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_alerts"] == 0
        assert stats["freshness_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_freshness("a1", freshness=FreshnessLevel.STALE, team="sre")
        eng.record_freshness("a2", freshness=FreshnessLevel.CURRENT, team="dev")
        eng.add_alert("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_alerts"] == 1
        assert stats["unique_teams"] == 2
