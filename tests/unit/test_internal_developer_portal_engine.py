"""Tests for internal_developer_portal_engine — InternalDeveloperPortalEngine."""

from __future__ import annotations

from shieldops.topology.internal_developer_portal_engine import (
    ContentFreshness,
    InternalDeveloperPortalEngine,
    PortalAdoption,
    PortalComponent,
)


def _engine(**kw) -> InternalDeveloperPortalEngine:
    return InternalDeveloperPortalEngine(**kw)


class TestEnums:
    def test_portalcomponent_service_catalog(self):
        assert PortalComponent.SERVICE_CATALOG == "service_catalog"

    def test_portalcomponent_api_docs(self):
        assert PortalComponent.API_DOCS == "api_docs"

    def test_portalcomponent_scaffolder(self):
        assert PortalComponent.SCAFFOLDER == "scaffolder"

    def test_portalcomponent_tech_radar(self):
        assert PortalComponent.TECH_RADAR == "tech_radar"

    def test_portalcomponent_search(self):
        assert PortalComponent.SEARCH == "search"

    def test_portaladoption_high(self):
        assert PortalAdoption.HIGH == "high"

    def test_portaladoption_medium(self):
        assert PortalAdoption.MEDIUM == "medium"

    def test_portaladoption_low(self):
        assert PortalAdoption.LOW == "low"

    def test_portaladoption_none(self):
        assert PortalAdoption.NONE == "none"

    def test_portaladoption_unknown(self):
        assert PortalAdoption.UNKNOWN == "unknown"

    def test_contentfreshness_current(self):
        assert ContentFreshness.CURRENT == "current"

    def test_contentfreshness_stale(self):
        assert ContentFreshness.STALE == "stale"

    def test_contentfreshness_outdated(self):
        assert ContentFreshness.OUTDATED == "outdated"

    def test_contentfreshness_missing(self):
        assert ContentFreshness.MISSING == "missing"

    def test_contentfreshness_archived(self):
        assert ContentFreshness.ARCHIVED == "archived"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            portal_component=PortalComponent.SERVICE_CATALOG,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.portal_component == PortalComponent.SERVICE_CATALOG
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_portal_component(self):
        eng = _engine()
        eng.record_item(
            name="a",
            portal_component=PortalComponent.SERVICE_CATALOG,
        )
        eng.record_item(
            name="b",
            portal_component=PortalComponent.API_DOCS,
        )
        result = eng.list_records(
            portal_component=PortalComponent.SERVICE_CATALOG,
        )
        assert len(result) == 1

    def test_filter_by_portal_adoption(self):
        eng = _engine()
        eng.record_item(
            name="a",
            portal_adoption=PortalAdoption.HIGH,
        )
        eng.record_item(
            name="b",
            portal_adoption=PortalAdoption.LOW,
        )
        result = eng.list_records(
            portal_adoption=PortalAdoption.HIGH,
        )
        assert len(result) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
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
        eng.record_item(
            name="a",
            portal_component=PortalComponent.SERVICE_CATALOG,
            score=90.0,
        )
        eng.record_item(
            name="b",
            portal_component=PortalComponent.SERVICE_CATALOG,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "service_catalog" in result
        assert result["service_catalog"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.record_item(
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
