"""Tests for shieldops.topology.service_dependency_scorer — ServiceDependencyScorer."""

from __future__ import annotations

from shieldops.topology.service_dependency_scorer import (
    CouplingLevel,
    DependencyDirection,
    DependencyHealth,
    DependencyMetric,
    DependencyScoreRecord,
    ServiceDependencyReport,
    ServiceDependencyScorer,
)


def _engine(**kw) -> ServiceDependencyScorer:
    return ServiceDependencyScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_coupling_tight(self):
        assert CouplingLevel.TIGHT == "tight"

    def test_coupling_moderate(self):
        assert CouplingLevel.MODERATE == "moderate"

    def test_coupling_loose(self):
        assert CouplingLevel.LOOSE == "loose"

    def test_coupling_async(self):
        assert CouplingLevel.ASYNC == "async"

    def test_coupling_independent(self):
        assert CouplingLevel.INDEPENDENT == "independent"

    def test_health_healthy(self):
        assert DependencyHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert DependencyHealth.DEGRADED == "degraded"

    def test_health_fragile(self):
        assert DependencyHealth.FRAGILE == "fragile"

    def test_health_broken(self):
        assert DependencyHealth.BROKEN == "broken"

    def test_health_unknown(self):
        assert DependencyHealth.UNKNOWN == "unknown"

    def test_direction_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_direction_bidirectional(self):
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_direction_circular(self):
        assert DependencyDirection.CIRCULAR == "circular"

    def test_direction_optional(self):
        assert DependencyDirection.OPTIONAL == "optional"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_score_record_defaults(self):
        r = DependencyScoreRecord()
        assert r.id
        assert r.dependency_id == ""
        assert r.coupling_level == CouplingLevel.LOOSE
        assert r.dependency_health == DependencyHealth.UNKNOWN
        assert r.dependency_direction == DependencyDirection.DOWNSTREAM
        assert r.health_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dependency_metric_defaults(self):
        m = DependencyMetric()
        assert m.id
        assert m.dependency_id == ""
        assert m.coupling_level == CouplingLevel.LOOSE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_service_dependency_report_defaults(self):
        r = ServiceDependencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.fragile_count == 0
        assert r.avg_health_score == 0.0
        assert r.by_coupling == {}
        assert r.by_health == {}
        assert r.by_direction == {}
        assert r.top_fragile == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_dependency
# ---------------------------------------------------------------------------


class TestRecordDependency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
            dependency_health=DependencyHealth.FRAGILE,
            dependency_direction=DependencyDirection.UPSTREAM,
            health_score=35.0,
            service="api-gateway",
            team="sre",
        )
        assert r.dependency_id == "DEP-001"
        assert r.coupling_level == CouplingLevel.TIGHT
        assert r.dependency_health == DependencyHealth.FRAGILE
        assert r.dependency_direction == DependencyDirection.UPSTREAM
        assert r.health_score == 35.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dependency(dependency_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_dependency
# ---------------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        r = eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
        )
        result = eng.get_dependency(r.id)
        assert result is not None
        assert result.coupling_level == CouplingLevel.TIGHT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_dependencies
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_dependency(dependency_id="DEP-001")
        eng.record_dependency(dependency_id="DEP-002")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_coupling(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
        )
        eng.record_dependency(
            dependency_id="DEP-002",
            coupling_level=CouplingLevel.LOOSE,
        )
        results = eng.list_dependencies(coupling_level=CouplingLevel.TIGHT)
        assert len(results) == 1

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            dependency_health=DependencyHealth.FRAGILE,
        )
        eng.record_dependency(
            dependency_id="DEP-002",
            dependency_health=DependencyHealth.HEALTHY,
        )
        results = eng.list_dependencies(
            dependency_health=DependencyHealth.FRAGILE,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_dependency(dependency_id="DEP-001", service="api-gateway")
        eng.record_dependency(dependency_id="DEP-002", service="auth")
        results = eng.list_dependencies(service="api-gateway")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dependency(dependency_id=f"DEP-{i}")
        assert len(eng.list_dependencies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
            metric_score=45.0,
            threshold=50.0,
            breached=True,
            description="Below health threshold",
        )
        assert m.dependency_id == "DEP-001"
        assert m.coupling_level == CouplingLevel.TIGHT
        assert m.metric_score == 45.0
        assert m.threshold == 50.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(dependency_id=f"DEP-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_dependency_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDependencyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
            health_score=40.0,
        )
        eng.record_dependency(
            dependency_id="DEP-002",
            coupling_level=CouplingLevel.TIGHT,
            health_score=60.0,
        )
        result = eng.analyze_dependency_distribution()
        assert "tight" in result
        assert result["tight"]["count"] == 2
        assert result["tight"]["avg_health_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_dependency_distribution() == {}


# ---------------------------------------------------------------------------
# identify_fragile_dependencies
# ---------------------------------------------------------------------------


class TestIdentifyFragileDependencies:
    def test_detects_fragile(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            dependency_health=DependencyHealth.FRAGILE,
        )
        eng.record_dependency(
            dependency_id="DEP-002",
            dependency_health=DependencyHealth.HEALTHY,
        )
        results = eng.identify_fragile_dependencies()
        assert len(results) == 1
        assert results[0]["dependency_id"] == "DEP-001"

    def test_detects_broken(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            dependency_health=DependencyHealth.BROKEN,
        )
        results = eng.identify_fragile_dependencies()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_fragile_dependencies() == []


# ---------------------------------------------------------------------------
# rank_by_health_score
# ---------------------------------------------------------------------------


class TestRankByHealthScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            service="api-gateway",
            health_score=90.0,
        )
        eng.record_dependency(
            dependency_id="DEP-002",
            service="auth",
            health_score=30.0,
        )
        results = eng.rank_by_health_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_health_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_health_score() == []


# ---------------------------------------------------------------------------
# detect_dependency_trends
# ---------------------------------------------------------------------------


class TestDetectDependencyTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(dependency_id="DEP-001", metric_score=50.0)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        eng.add_metric(dependency_id="DEP-001", metric_score=10.0)
        eng.add_metric(dependency_id="DEP-002", metric_score=10.0)
        eng.add_metric(dependency_id="DEP-003", metric_score=80.0)
        eng.add_metric(dependency_id="DEP-004", metric_score=80.0)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_dependency_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
            dependency_health=DependencyHealth.FRAGILE,
            health_score=35.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceDependencyReport)
        assert report.total_records == 1
        assert report.fragile_count == 1
        assert len(report.top_fragile) == 1
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
        eng.record_dependency(dependency_id="DEP-001")
        eng.add_metric(dependency_id="DEP-001")
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
        assert stats["coupling_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_dependency(
            dependency_id="DEP-001",
            coupling_level=CouplingLevel.TIGHT,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "tight" in stats["coupling_distribution"]
