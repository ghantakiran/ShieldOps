"""Tests for shieldops.operations.runbook_dependency — RunbookDependencyMapper."""

from __future__ import annotations

from shieldops.operations.runbook_dependency import (
    DependencyCheck,
    DependencyHealth,
    DependencyType,
    RunbookDependencyMapper,
    RunbookDependencyReport,
    RunbookDepRecord,
    RunbookScope,
)


def _engine(**kw) -> RunbookDependencyMapper:
    return RunbookDependencyMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_prerequisite(self):
        assert DependencyType.PREREQUISITE == "prerequisite"

    def test_type_sequential(self):
        assert DependencyType.SEQUENTIAL == "sequential"

    def test_type_parallel(self):
        assert DependencyType.PARALLEL == "parallel"

    def test_type_optional(self):
        assert DependencyType.OPTIONAL == "optional"

    def test_type_fallback(self):
        assert DependencyType.FALLBACK == "fallback"

    def test_health_healthy(self):
        assert DependencyHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert DependencyHealth.DEGRADED == "degraded"

    def test_health_broken(self):
        assert DependencyHealth.BROKEN == "broken"

    def test_health_circular(self):
        assert DependencyHealth.CIRCULAR == "circular"

    def test_health_unknown(self):
        assert DependencyHealth.UNKNOWN == "unknown"

    def test_scope_service(self):
        assert RunbookScope.SERVICE == "service"

    def test_scope_team(self):
        assert RunbookScope.TEAM == "team"

    def test_scope_platform(self):
        assert RunbookScope.PLATFORM == "platform"

    def test_scope_region(self):
        assert RunbookScope.REGION == "region"

    def test_scope_global(self):
        assert RunbookScope.GLOBAL == "global"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_runbook_dep_record_defaults(self):
        r = RunbookDepRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.dependency_type == DependencyType.PREREQUISITE
        assert r.dependency_health == DependencyHealth.UNKNOWN
        assert r.runbook_scope == RunbookScope.SERVICE
        assert r.dependency_count == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dependency_check_defaults(self):
        m = DependencyCheck()
        assert m.id
        assert m.runbook_id == ""
        assert m.dependency_type == DependencyType.PREREQUISITE
        assert m.check_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_runbook_dependency_report_defaults(self):
        r = RunbookDependencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checks == 0
        assert r.broken_count == 0
        assert r.avg_dependency_count == 0.0
        assert r.by_type == {}
        assert r.by_health == {}
        assert r.by_scope == {}
        assert r.top_broken == []
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
            runbook_id="RB-001",
            dependency_type=DependencyType.SEQUENTIAL,
            dependency_health=DependencyHealth.BROKEN,
            runbook_scope=RunbookScope.PLATFORM,
            dependency_count=5.0,
            service="api-gateway",
            team="sre",
        )
        assert r.runbook_id == "RB-001"
        assert r.dependency_type == DependencyType.SEQUENTIAL
        assert r.dependency_health == DependencyHealth.BROKEN
        assert r.runbook_scope == RunbookScope.PLATFORM
        assert r.dependency_count == 5.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dependency(runbook_id=f"RB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_dependency
# ---------------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        r = eng.record_dependency(
            runbook_id="RB-001",
            dependency_health=DependencyHealth.BROKEN,
        )
        result = eng.get_dependency(r.id)
        assert result is not None
        assert result.dependency_health == DependencyHealth.BROKEN

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_dependencies
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_dependency(runbook_id="RB-001")
        eng.record_dependency(runbook_id="RB-002")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_dep_type(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            dependency_type=DependencyType.PREREQUISITE,
        )
        eng.record_dependency(
            runbook_id="RB-002",
            dependency_type=DependencyType.PARALLEL,
        )
        results = eng.list_dependencies(dep_type=DependencyType.PREREQUISITE)
        assert len(results) == 1

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            dependency_health=DependencyHealth.HEALTHY,
        )
        eng.record_dependency(
            runbook_id="RB-002",
            dependency_health=DependencyHealth.BROKEN,
        )
        results = eng.list_dependencies(health=DependencyHealth.BROKEN)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_dependency(runbook_id="RB-001", service="api-gateway")
        eng.record_dependency(runbook_id="RB-002", service="auth-svc")
        results = eng.list_dependencies(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_dependency(runbook_id="RB-001", team="sre")
        eng.record_dependency(runbook_id="RB-002", team="platform")
        results = eng.list_dependencies(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dependency(runbook_id=f"RB-{i}")
        assert len(eng.list_dependencies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_check
# ---------------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        m = eng.add_check(
            runbook_id="RB-001",
            dependency_type=DependencyType.SEQUENTIAL,
            check_score=85.0,
            threshold=90.0,
            breached=True,
            description="Dependency chain broken",
        )
        assert m.runbook_id == "RB-001"
        assert m.dependency_type == DependencyType.SEQUENTIAL
        assert m.check_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Dependency chain broken"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_check(runbook_id=f"RB-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_dependency_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDependencyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            dependency_type=DependencyType.PREREQUISITE,
            dependency_count=3.0,
        )
        eng.record_dependency(
            runbook_id="RB-002",
            dependency_type=DependencyType.PREREQUISITE,
            dependency_count=7.0,
        )
        result = eng.analyze_dependency_distribution()
        assert "prerequisite" in result
        assert result["prerequisite"]["count"] == 2
        assert result["prerequisite"]["avg_dependency_count"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_dependency_distribution() == {}


# ---------------------------------------------------------------------------
# identify_broken_dependencies
# ---------------------------------------------------------------------------


class TestIdentifyBrokenDependencies:
    def test_detects(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            dependency_health=DependencyHealth.BROKEN,
        )
        eng.record_dependency(
            runbook_id="RB-002",
            dependency_health=DependencyHealth.HEALTHY,
        )
        results = eng.identify_broken_dependencies()
        assert len(results) == 1
        assert results[0]["runbook_id"] == "RB-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_broken_dependencies() == []


# ---------------------------------------------------------------------------
# rank_by_dependency_count
# ---------------------------------------------------------------------------


class TestRankByDependencyCount:
    def test_ranked(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            service="api-gateway",
            dependency_count=10.0,
        )
        eng.record_dependency(
            runbook_id="RB-002",
            service="auth-svc",
            dependency_count=3.0,
        )
        eng.record_dependency(
            runbook_id="RB-003",
            service="api-gateway",
            dependency_count=5.0,
        )
        results = eng.rank_by_dependency_count()
        assert len(results) == 2
        # descending: api-gateway (15.0) first, auth-svc (3.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["total_dependency_count"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_dependency_count() == []


# ---------------------------------------------------------------------------
# detect_dependency_trends
# ---------------------------------------------------------------------------


class TestDetectDependencyTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_check(runbook_id="RB-1", check_score=val)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_check(runbook_id="RB-1", check_score=val)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_check(runbook_id="RB-1", check_score=val)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

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
            runbook_id="RB-001",
            dependency_type=DependencyType.SEQUENTIAL,
            dependency_health=DependencyHealth.BROKEN,
            runbook_scope=RunbookScope.PLATFORM,
            dependency_count=5.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, RunbookDependencyReport)
        assert report.total_records == 1
        assert report.broken_count == 1
        assert len(report.top_broken) >= 1
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
        eng.record_dependency(runbook_id="RB-001")
        eng.add_check(runbook_id="RB-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_dependency(
            runbook_id="RB-001",
            dependency_type=DependencyType.PREREQUISITE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "prerequisite" in stats["type_distribution"]
