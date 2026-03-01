"""Tests for shieldops.topology.dependency_freshness_monitor — DependencyFreshnessMonitor."""

from __future__ import annotations

from shieldops.topology.dependency_freshness_monitor import (
    DependencyCategory,
    DependencyFreshnessMonitor,
    DependencyFreshnessReport,
    FreshnessCheck,
    FreshnessLevel,
    FreshnessRecord,
    UpdateUrgency,
)


def _engine(**kw) -> DependencyFreshnessMonitor:
    return DependencyFreshnessMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_current(self):
        assert FreshnessLevel.CURRENT == "current"

    def test_level_recent(self):
        assert FreshnessLevel.RECENT == "recent"

    def test_level_outdated(self):
        assert FreshnessLevel.OUTDATED == "outdated"

    def test_level_stale(self):
        assert FreshnessLevel.STALE == "stale"

    def test_level_abandoned(self):
        assert FreshnessLevel.ABANDONED == "abandoned"

    def test_category_runtime(self):
        assert DependencyCategory.RUNTIME == "runtime"

    def test_category_build(self):
        assert DependencyCategory.BUILD == "build"

    def test_category_test(self):
        assert DependencyCategory.TEST == "test"

    def test_category_security(self):
        assert DependencyCategory.SECURITY == "security"

    def test_category_optional(self):
        assert DependencyCategory.OPTIONAL == "optional"

    def test_urgency_critical_security(self):
        assert UpdateUrgency.CRITICAL_SECURITY == "critical_security"

    def test_urgency_high(self):
        assert UpdateUrgency.HIGH == "high"

    def test_urgency_moderate(self):
        assert UpdateUrgency.MODERATE == "moderate"

    def test_urgency_low(self):
        assert UpdateUrgency.LOW == "low"

    def test_urgency_none(self):
        assert UpdateUrgency.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_freshness_record_defaults(self):
        r = FreshnessRecord()
        assert r.id
        assert r.dependency_id == ""
        assert r.freshness_level == FreshnessLevel.CURRENT
        assert r.dependency_category == DependencyCategory.RUNTIME
        assert r.update_urgency == UpdateUrgency.NONE
        assert r.versions_behind == 0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_freshness_check_defaults(self):
        m = FreshnessCheck()
        assert m.id
        assert m.dependency_id == ""
        assert m.freshness_level == FreshnessLevel.CURRENT
        assert m.staleness_days == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_dependency_freshness_report_defaults(self):
        r = DependencyFreshnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checks == 0
        assert r.stale_dependencies == 0
        assert r.avg_versions_behind == 0.0
        assert r.by_freshness == {}
        assert r.by_category == {}
        assert r.by_urgency == {}
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
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.CURRENT,
            dependency_category=DependencyCategory.RUNTIME,
            update_urgency=UpdateUrgency.NONE,
            versions_behind=0,
            service="api-gateway",
            team="sre",
        )
        assert r.dependency_id == "DEP-001"
        assert r.freshness_level == FreshnessLevel.CURRENT
        assert r.dependency_category == DependencyCategory.RUNTIME
        assert r.update_urgency == UpdateUrgency.NONE
        assert r.versions_behind == 0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_freshness(dependency_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_freshness
# ---------------------------------------------------------------------------


class TestGetFreshness:
    def test_found(self):
        eng = _engine()
        r = eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.STALE,
        )
        result = eng.get_freshness(r.id)
        assert result is not None
        assert result.freshness_level == FreshnessLevel.STALE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_freshness("nonexistent") is None


# ---------------------------------------------------------------------------
# list_freshness
# ---------------------------------------------------------------------------


class TestListFreshness:
    def test_list_all(self):
        eng = _engine()
        eng.record_freshness(dependency_id="DEP-001")
        eng.record_freshness(dependency_id="DEP-002")
        assert len(eng.list_freshness()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.CURRENT,
        )
        eng.record_freshness(
            dependency_id="DEP-002",
            freshness_level=FreshnessLevel.STALE,
        )
        results = eng.list_freshness(
            level=FreshnessLevel.CURRENT,
        )
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            dependency_category=DependencyCategory.RUNTIME,
        )
        eng.record_freshness(
            dependency_id="DEP-002",
            dependency_category=DependencyCategory.BUILD,
        )
        results = eng.list_freshness(
            category=DependencyCategory.RUNTIME,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_freshness(dependency_id="DEP-001", service="api-gateway")
        eng.record_freshness(dependency_id="DEP-002", service="auth-svc")
        results = eng.list_freshness(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_freshness(dependency_id="DEP-001", team="sre")
        eng.record_freshness(dependency_id="DEP-002", team="platform")
        results = eng.list_freshness(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_freshness(dependency_id=f"DEP-{i}")
        assert len(eng.list_freshness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_check
# ---------------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        m = eng.add_check(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.OUTDATED,
            staleness_days=45.0,
            threshold=30.0,
            breached=True,
            description="Dependency outdated beyond threshold",
        )
        assert m.dependency_id == "DEP-001"
        assert m.freshness_level == FreshnessLevel.OUTDATED
        assert m.staleness_days == 45.0
        assert m.threshold == 30.0
        assert m.breached is True
        assert m.description == "Dependency outdated beyond threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_check(dependency_id=f"DEP-{i}")
        assert len(eng._checks) == 2


# ---------------------------------------------------------------------------
# analyze_freshness_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeFreshnessDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.CURRENT,
            versions_behind=0,
        )
        eng.record_freshness(
            dependency_id="DEP-002",
            freshness_level=FreshnessLevel.CURRENT,
            versions_behind=2,
        )
        result = eng.analyze_freshness_distribution()
        assert "current" in result
        assert result["current"]["count"] == 2
        assert result["current"]["avg_versions_behind"] == 1.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_freshness_distribution() == {}


# ---------------------------------------------------------------------------
# identify_stale_dependencies
# ---------------------------------------------------------------------------


class TestIdentifyStaleDependencies:
    def test_detects_stale(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.STALE,
        )
        eng.record_freshness(
            dependency_id="DEP-002",
            freshness_level=FreshnessLevel.CURRENT,
        )
        results = eng.identify_stale_dependencies()
        assert len(results) == 1
        assert results[0]["dependency_id"] == "DEP-001"

    def test_detects_abandoned(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.ABANDONED,
        )
        results = eng.identify_stale_dependencies()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_dependencies() == []


# ---------------------------------------------------------------------------
# rank_by_staleness
# ---------------------------------------------------------------------------


class TestRankByStaleness:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            service="api-gateway",
            versions_behind=10,
        )
        eng.record_freshness(
            dependency_id="DEP-002",
            service="auth-svc",
            versions_behind=2,
        )
        results = eng.rank_by_staleness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_versions_behind"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_staleness() == []


# ---------------------------------------------------------------------------
# detect_freshness_trends
# ---------------------------------------------------------------------------


class TestDetectFreshnessTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_check(dependency_id="DEP-1", staleness_days=val)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 30.0, 30.0]:
            eng.add_check(dependency_id="DEP-1", staleness_days=val)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "increasing"
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
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.STALE,
            dependency_category=DependencyCategory.SECURITY,
            update_urgency=UpdateUrgency.HIGH,
            versions_behind=8,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyFreshnessReport)
        assert report.total_records == 1
        assert report.stale_dependencies == 1
        assert len(report.top_stale) >= 1
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
        eng.record_freshness(dependency_id="DEP-001")
        eng.add_check(dependency_id="DEP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checks"] == 0
        assert stats["freshness_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_freshness(
            dependency_id="DEP-001",
            freshness_level=FreshnessLevel.CURRENT,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "current" in stats["freshness_distribution"]
