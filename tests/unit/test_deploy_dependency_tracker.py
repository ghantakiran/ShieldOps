"""Tests for shieldops.changes.deploy_dependency_tracker — DeployDependencyTracker."""

from __future__ import annotations

from shieldops.changes.deploy_dependency_tracker import (
    BlockingReason,
    DependencyChain,
    DependencyStatus,
    DependencyType,
    DeployDependencyRecord,
    DeployDependencyReport,
    DeployDependencyTracker,
)


def _engine(**kw) -> DeployDependencyTracker:
    return DeployDependencyTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_service(self):
        assert DependencyType.SERVICE == "service"

    def test_type_database(self):
        assert DependencyType.DATABASE == "database"

    def test_type_config(self):
        assert DependencyType.CONFIG == "config"

    def test_type_infrastructure(self):
        assert DependencyType.INFRASTRUCTURE == "infrastructure"

    def test_type_external_api(self):
        assert DependencyType.EXTERNAL_API == "external_api"

    def test_status_satisfied(self):
        assert DependencyStatus.SATISFIED == "satisfied"

    def test_status_pending(self):
        assert DependencyStatus.PENDING == "pending"

    def test_status_blocked(self):
        assert DependencyStatus.BLOCKED == "blocked"

    def test_status_failed(self):
        assert DependencyStatus.FAILED == "failed"

    def test_status_skipped(self):
        assert DependencyStatus.SKIPPED == "skipped"

    def test_reason_version_mismatch(self):
        assert BlockingReason.VERSION_MISMATCH == "version_mismatch"

    def test_reason_schema_change(self):
        assert BlockingReason.SCHEMA_CHANGE == "schema_change"

    def test_reason_api_incompatible(self):
        assert BlockingReason.API_INCOMPATIBLE == "api_incompatible"

    def test_reason_resource_unavailable(self):
        assert BlockingReason.RESOURCE_UNAVAILABLE == "resource_unavailable"

    def test_reason_approval_pending(self):
        assert BlockingReason.APPROVAL_PENDING == "approval_pending"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_deploy_dependency_record_defaults(self):
        r = DeployDependencyRecord()
        assert r.id
        assert r.deploy_id == ""
        assert r.dependency_type == DependencyType.SERVICE
        assert r.dependency_status == DependencyStatus.PENDING
        assert r.blocking_reason == BlockingReason.VERSION_MISMATCH
        assert r.wait_time_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dependency_chain_defaults(self):
        c = DependencyChain()
        assert c.id
        assert c.deploy_id == ""
        assert c.dependency_type == DependencyType.SERVICE
        assert c.chain_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_deploy_dependency_report_defaults(self):
        r = DeployDependencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_chains == 0
        assert r.blocked_count == 0
        assert r.avg_wait_time_minutes == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_reason == {}
        assert r.top_blocked == []
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
            deploy_id="DEP-001",
            dependency_type=DependencyType.DATABASE,
            dependency_status=DependencyStatus.BLOCKED,
            blocking_reason=BlockingReason.SCHEMA_CHANGE,
            wait_time_minutes=30.0,
            service="auth-svc",
            team="sre",
        )
        assert r.deploy_id == "DEP-001"
        assert r.dependency_type == DependencyType.DATABASE
        assert r.dependency_status == DependencyStatus.BLOCKED
        assert r.blocking_reason == BlockingReason.SCHEMA_CHANGE
        assert r.wait_time_minutes == 30.0
        assert r.service == "auth-svc"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dependency(deploy_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_dependency
# ---------------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        r = eng.record_dependency(
            deploy_id="DEP-001",
            dependency_status=DependencyStatus.BLOCKED,
        )
        result = eng.get_dependency(r.id)
        assert result is not None
        assert result.dependency_status == DependencyStatus.BLOCKED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_dependencies
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_dependency(deploy_id="DEP-001")
        eng.record_dependency(deploy_id="DEP-002")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_type=DependencyType.SERVICE,
        )
        eng.record_dependency(
            deploy_id="DEP-002",
            dependency_type=DependencyType.DATABASE,
        )
        results = eng.list_dependencies(
            dependency_type=DependencyType.SERVICE,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_status=DependencyStatus.BLOCKED,
        )
        eng.record_dependency(
            deploy_id="DEP-002",
            dependency_status=DependencyStatus.SATISFIED,
        )
        results = eng.list_dependencies(
            dependency_status=DependencyStatus.BLOCKED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_dependency(deploy_id="DEP-001", team="sre")
        eng.record_dependency(deploy_id="DEP-002", team="platform")
        results = eng.list_dependencies(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dependency(deploy_id=f"DEP-{i}")
        assert len(eng.list_dependencies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_chain
# ---------------------------------------------------------------------------


class TestAddChain:
    def test_basic(self):
        eng = _engine()
        c = eng.add_chain(
            deploy_id="DEP-001",
            dependency_type=DependencyType.DATABASE,
            chain_score=85.0,
            threshold=70.0,
            breached=True,
            description="Long chain detected",
        )
        assert c.deploy_id == "DEP-001"
        assert c.dependency_type == DependencyType.DATABASE
        assert c.chain_score == 85.0
        assert c.threshold == 70.0
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_chain(deploy_id=f"DEP-{i}")
        assert len(eng._chains) == 2


# ---------------------------------------------------------------------------
# analyze_dependency_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDependencyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_type=DependencyType.SERVICE,
            wait_time_minutes=10.0,
        )
        eng.record_dependency(
            deploy_id="DEP-002",
            dependency_type=DependencyType.SERVICE,
            wait_time_minutes=20.0,
        )
        result = eng.analyze_dependency_distribution()
        assert "service" in result
        assert result["service"]["count"] == 2
        assert result["service"]["avg_wait_time"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_dependency_distribution() == {}


# ---------------------------------------------------------------------------
# identify_blocked_deployments
# ---------------------------------------------------------------------------


class TestIdentifyBlockedDeployments:
    def test_detects_blocked(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_status=DependencyStatus.BLOCKED,
        )
        eng.record_dependency(
            deploy_id="DEP-002",
            dependency_status=DependencyStatus.SATISFIED,
        )
        results = eng.identify_blocked_deployments()
        assert len(results) == 1
        assert results[0]["deploy_id"] == "DEP-001"

    def test_detects_failed(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_status=DependencyStatus.FAILED,
        )
        results = eng.identify_blocked_deployments()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_blocked_deployments() == []


# ---------------------------------------------------------------------------
# rank_by_wait_time
# ---------------------------------------------------------------------------


class TestRankByWaitTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_dependency(deploy_id="DEP-001", service="auth-svc", wait_time_minutes=30.0)
        eng.record_dependency(deploy_id="DEP-002", service="pay-svc", wait_time_minutes=10.0)
        results = eng.rank_by_wait_time()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_wait_time"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_wait_time() == []


# ---------------------------------------------------------------------------
# detect_dependency_trends
# ---------------------------------------------------------------------------


class TestDetectDependencyTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_chain(deploy_id="DEP-001", chain_score=50.0)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_chain(deploy_id="DEP-001", chain_score=30.0)
        eng.add_chain(deploy_id="DEP-002", chain_score=30.0)
        eng.add_chain(deploy_id="DEP-003", chain_score=80.0)
        eng.add_chain(deploy_id="DEP-004", chain_score=80.0)
        result = eng.detect_dependency_trends()
        assert result["trend"] == "improving"
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
            deploy_id="DEP-001",
            dependency_type=DependencyType.DATABASE,
            dependency_status=DependencyStatus.BLOCKED,
            blocking_reason=BlockingReason.SCHEMA_CHANGE,
            wait_time_minutes=90.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DeployDependencyReport)
        assert report.total_records == 1
        assert report.blocked_count == 1
        assert len(report.top_blocked) == 1
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
        eng.record_dependency(deploy_id="DEP-001")
        eng.add_chain(deploy_id="DEP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._chains) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_chains"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_dependency(
            deploy_id="DEP-001",
            dependency_type=DependencyType.SERVICE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_deploys"] == 1
        assert "service" in stats["type_distribution"]
