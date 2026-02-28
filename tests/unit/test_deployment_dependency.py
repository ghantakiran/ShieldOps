"""Tests for shieldops.changes.deployment_dependency — DeploymentDependencyTracker."""

from __future__ import annotations

from shieldops.changes.deployment_dependency import (
    DependencyConstraint,
    DependencyDirection,
    DependencyRisk,
    DependencyType,
    DeployDependencyRecord,
    DeployDependencyReport,
    DeploymentDependencyTracker,
)


def _engine(**kw) -> DeploymentDependencyTracker:
    return DeploymentDependencyTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DependencyType (5)
    def test_type_api_contract(self):
        assert DependencyType.API_CONTRACT == "api_contract"

    def test_type_schema_migration(self):
        assert DependencyType.SCHEMA_MIGRATION == "schema_migration"

    def test_type_config_change(self):
        assert DependencyType.CONFIG_CHANGE == "config_change"

    def test_type_shared_library(self):
        assert DependencyType.SHARED_LIBRARY == "shared_library"

    def test_type_infrastructure(self):
        assert DependencyType.INFRASTRUCTURE == "infrastructure"

    # DependencyDirection (5)
    def test_direction_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_direction_bidirectional(self):
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_direction_transitive(self):
        assert DependencyDirection.TRANSITIVE == "transitive"

    def test_direction_optional(self):
        assert DependencyDirection.OPTIONAL == "optional"

    # DependencyRisk (5)
    def test_risk_breaking(self):
        assert DependencyRisk.BREAKING == "breaking"

    def test_risk_high(self):
        assert DependencyRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert DependencyRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert DependencyRisk.LOW == "low"

    def test_risk_safe(self):
        assert DependencyRisk.SAFE == "safe"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_deploy_dependency_record_defaults(self):
        r = DeployDependencyRecord()
        assert r.id
        assert r.service_name == ""
        assert r.dep_type == DependencyType.API_CONTRACT
        assert r.direction == DependencyDirection.UPSTREAM
        assert r.risk == DependencyRisk.LOW
        assert r.depth == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_dependency_constraint_defaults(self):
        r = DependencyConstraint()
        assert r.id
        assert r.constraint_name == ""
        assert r.dep_type == DependencyType.API_CONTRACT
        assert r.direction == DependencyDirection.UPSTREAM
        assert r.priority == 0
        assert r.description == ""
        assert r.created_at > 0

    def test_deploy_dependency_report_defaults(self):
        r = DeployDependencyReport()
        assert r.total_records == 0
        assert r.total_constraints == 0
        assert r.avg_depth == 0.0
        assert r.by_type == {}
        assert r.by_direction == {}
        assert r.breaking_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_dependency
# -------------------------------------------------------------------


class TestRecordDependency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dependency("order-svc", dep_type=DependencyType.API_CONTRACT)
        assert r.service_name == "order-svc"
        assert r.dep_type == DependencyType.API_CONTRACT

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_dependency(
            "payment-svc",
            dep_type=DependencyType.SCHEMA_MIGRATION,
            direction=DependencyDirection.DOWNSTREAM,
            risk=DependencyRisk.BREAKING,
            depth=3,
            details="schema v2 migration",
        )
        assert r.risk == DependencyRisk.BREAKING
        assert r.depth == 3
        assert r.details == "schema v2 migration"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dependency(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_dependency
# -------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        r = eng.record_dependency("order-svc")
        assert eng.get_dependency(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


# -------------------------------------------------------------------
# list_dependencies
# -------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_dependency("svc-a")
        eng.record_dependency("svc-b")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_dependency("svc-a")
        eng.record_dependency("svc-b")
        results = eng.list_dependencies(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_dep_type(self):
        eng = _engine()
        eng.record_dependency("svc-a", dep_type=DependencyType.API_CONTRACT)
        eng.record_dependency("svc-b", dep_type=DependencyType.INFRASTRUCTURE)
        results = eng.list_dependencies(dep_type=DependencyType.INFRASTRUCTURE)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_constraint
# -------------------------------------------------------------------


class TestAddConstraint:
    def test_basic(self):
        eng = _engine()
        c = eng.add_constraint(
            "deploy-order-rule",
            dep_type=DependencyType.SHARED_LIBRARY,
            direction=DependencyDirection.BIDIRECTIONAL,
            priority=5,
        )
        assert c.constraint_name == "deploy-order-rule"
        assert c.dep_type == DependencyType.SHARED_LIBRARY
        assert c.priority == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_constraint(f"constraint-{i}")
        assert len(eng._constraints) == 2


# -------------------------------------------------------------------
# analyze_service_dependencies
# -------------------------------------------------------------------


class TestAnalyzeServiceDependencies:
    def test_with_data(self):
        eng = _engine(max_depth=5)
        eng.record_dependency("svc-a", depth=3)
        eng.record_dependency("svc-a", depth=4)
        result = eng.analyze_service_dependencies("svc-a")
        assert result["avg_depth"] == 3.5
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_dependencies("unknown-svc")
        assert result["status"] == "no_data"

    def test_exceeds_threshold(self):
        eng = _engine(max_depth=3)
        eng.record_dependency("svc-a", depth=5)
        eng.record_dependency("svc-a", depth=6)
        result = eng.analyze_service_dependencies("svc-a")
        assert result["meets_threshold"] is False


# -------------------------------------------------------------------
# identify_breaking_dependencies
# -------------------------------------------------------------------


class TestIdentifyBreakingDependencies:
    def test_with_breaking(self):
        eng = _engine()
        eng.record_dependency("svc-a", risk=DependencyRisk.BREAKING)
        eng.record_dependency("svc-a", risk=DependencyRisk.HIGH)
        eng.record_dependency("svc-b", risk=DependencyRisk.LOW)
        results = eng.identify_breaking_dependencies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["breaking_high_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_breaking_dependencies() == []

    def test_single_breaking_not_returned(self):
        eng = _engine()
        eng.record_dependency("svc-a", risk=DependencyRisk.BREAKING)
        assert eng.identify_breaking_dependencies() == []


# -------------------------------------------------------------------
# rank_by_dependency_depth
# -------------------------------------------------------------------


class TestRankByDependencyDepth:
    def test_with_data(self):
        eng = _engine()
        eng.record_dependency("svc-a", depth=2)
        eng.record_dependency("svc-b", depth=7)
        results = eng.rank_by_dependency_depth()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_depth"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_dependency_depth() == []


# -------------------------------------------------------------------
# detect_dependency_cycles
# -------------------------------------------------------------------


class TestDetectDependencyCycles:
    def test_with_cycles(self):
        eng = _engine()
        for _ in range(5):
            eng.record_dependency("svc-a")
        eng.record_dependency("svc-b")
        results = eng.detect_dependency_cycles()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_dependency_cycles() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_dependency("svc-a")
        assert eng.detect_dependency_cycles() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_dependency("svc-a", risk=DependencyRisk.BREAKING, depth=4)
        eng.record_dependency("svc-b", risk=DependencyRisk.LOW, depth=1)
        eng.add_constraint("rule-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_constraints == 1
        assert report.breaking_count == 1
        assert report.by_type != {}
        assert report.by_direction != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.avg_depth == 0.0
        assert "good" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_dependency("svc-a")
        eng.add_constraint("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._constraints) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_constraints"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_depth=5)
        eng.record_dependency("svc-a", dep_type=DependencyType.API_CONTRACT)
        eng.record_dependency("svc-b", dep_type=DependencyType.INFRASTRUCTURE)
        eng.add_constraint("rule-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_constraints"] == 1
        assert stats["unique_services"] == 2
        assert stats["max_depth"] == 5
