"""Tests for shieldops.observability.alert_impact_scorer — AlertImpactScorer."""

from __future__ import annotations

from shieldops.observability.alert_impact_scorer import (
    AlertCategory,
    AlertImpactRecord,
    AlertImpactScorer,
    ImpactLevel,
    ImpactReport,
    ServiceNode,
    ServiceTier,
)


def _engine(**kw) -> AlertImpactScorer:
    return AlertImpactScorer(**kw)


class TestEnums:
    def test_impact_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    def test_impact_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_impact_medium(self):
        assert ImpactLevel.MEDIUM == "medium"

    def test_impact_low(self):
        assert ImpactLevel.LOW == "low"

    def test_impact_none(self):
        assert ImpactLevel.NONE == "none"

    def test_tier_0(self):
        assert ServiceTier.TIER_0 == "tier_0"

    def test_tier_1(self):
        assert ServiceTier.TIER_1 == "tier_1"

    def test_tier_2(self):
        assert ServiceTier.TIER_2 == "tier_2"

    def test_tier_3(self):
        assert ServiceTier.TIER_3 == "tier_3"

    def test_category_availability(self):
        assert AlertCategory.AVAILABILITY == "availability"

    def test_category_latency(self):
        assert AlertCategory.LATENCY == "latency"

    def test_category_security(self):
        assert AlertCategory.SECURITY == "security"


class TestModels:
    def test_service_node_defaults(self):
        n = ServiceNode()
        assert n.id
        assert n.tier == ServiceTier.TIER_2
        assert n.dependencies == []
        assert n.user_facing is False

    def test_impact_record_defaults(self):
        r = AlertImpactRecord()
        assert r.id
        assert r.impact_level == ImpactLevel.NONE
        assert r.blast_radius == 0

    def test_report_defaults(self):
        r = ImpactReport()
        assert r.total_alerts == 0
        assert r.recommendations == []


class TestAddService:
    def test_basic(self):
        eng = _engine()
        s = eng.add_service("api-gw", tier=ServiceTier.TIER_0, user_facing=True)
        assert s.name == "api-gw"
        assert s.tier == ServiceTier.TIER_0

    def test_with_dependencies(self):
        eng = _engine()
        s = eng.add_service("api", dependencies=["db", "cache"])
        assert len(s.dependencies) == 2

    def test_with_revenue(self):
        eng = _engine()
        s = eng.add_service("checkout", revenue_impact_per_min=500.0)
        assert s.revenue_impact_per_min == 500.0


class TestScoreImpact:
    def test_tier_0_high_score(self):
        eng = _engine()
        eng.add_service("api-gw", tier=ServiceTier.TIER_0)
        r = eng.score_impact("high-cpu", "api-gw")
        assert r.impact_score >= 80

    def test_tier_3_low_score(self):
        eng = _engine()
        eng.add_service("internal-tool", tier=ServiceTier.TIER_3)
        r = eng.score_impact("disk-warn", "internal-tool")
        assert r.impact_score < 80

    def test_unknown_service(self):
        eng = _engine()
        r = eng.score_impact("cpu-alert", "unknown-svc")
        assert r.impact_score > 0

    def test_revenue_impact(self):
        eng = _engine()
        eng.add_service("checkout", tier=ServiceTier.TIER_0, revenue_impact_per_min=100.0)
        r = eng.score_impact("down", "checkout")
        assert r.estimated_revenue_impact > 0

    def test_eviction(self):
        eng = _engine(max_records=3)
        eng.add_service("svc", tier=ServiceTier.TIER_2)
        for i in range(5):
            eng.score_impact(f"a-{i}", "svc")
        assert len(eng._impacts) == 3


class TestMapDependencies:
    def test_no_deps(self):
        eng = _engine()
        eng.add_service("api")
        result = eng.map_dependencies("api")
        assert result["total_depth"] == 0

    def test_direct_deps(self):
        eng = _engine()
        eng.add_service("api", dependencies=["db"])
        eng.add_service("db")
        result = eng.map_dependencies("api")
        assert "db" in result["transitive_deps"]

    def test_unknown_service(self):
        eng = _engine()
        result = eng.map_dependencies("nonexistent")
        assert result["total_depth"] == 0


class TestCalculateBlastRadius:
    def test_no_dependents(self):
        eng = _engine()
        eng.add_service("leaf")
        result = eng.calculate_blast_radius("leaf")
        assert result["affected_count"] == 0

    def test_with_dependents(self):
        eng = _engine()
        eng.add_service("db")
        eng.add_service("api", dependencies=["db"])
        eng.add_service("web", dependencies=["db"])
        result = eng.calculate_blast_radius("db")
        assert result["affected_count"] == 2

    def test_user_facing_count(self):
        eng = _engine()
        eng.add_service("db")
        eng.add_service("api", dependencies=["db"], user_facing=True)
        result = eng.calculate_blast_radius("db")
        assert result["user_facing_affected"] == 1


class TestPrioritizeAlerts:
    def test_empty(self):
        eng = _engine()
        assert eng.prioritize_alerts() == []

    def test_sorted(self):
        eng = _engine()
        eng.add_service("a", tier=ServiceTier.TIER_0)
        eng.add_service("b", tier=ServiceTier.TIER_3)
        eng.score_impact("alert-a", "a")
        eng.score_impact("alert-b", "b")
        prioritized = eng.prioritize_alerts()
        assert prioritized[0].service == "a"


class TestGetImpactReport:
    def test_empty(self):
        eng = _engine()
        report = eng.get_impact_report()
        assert report.total_alerts == 0

    def test_with_critical(self):
        eng = _engine()
        eng.add_service("api", tier=ServiceTier.TIER_0)
        eng.score_impact("critical-alert", "api")
        report = eng.get_impact_report()
        assert report.critical_count >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_service("api")
        eng.score_impact("a", "api")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._services) == 0
        assert len(eng._impacts) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_service("api")
        eng.score_impact("a", "api")
        stats = eng.get_stats()
        assert stats["total_services"] == 1
        assert stats["unique_alerts"] == 1
