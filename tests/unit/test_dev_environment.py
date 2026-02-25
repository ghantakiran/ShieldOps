"""Tests for shieldops.operations.dev_environment — DevEnvironmentHealthMonitor."""

from __future__ import annotations

from shieldops.operations.dev_environment import (
    DevEnvironmentHealthMonitor,
    DevEnvironmentReport,
    EnvironmentBaseline,
    EnvironmentIssueRecord,
    EnvironmentType,
    HealthIssueType,
    IssueImpact,
)


def _engine(**kw) -> DevEnvironmentHealthMonitor:
    return DevEnvironmentHealthMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EnvironmentType (5)
    def test_env_local(self):
        assert EnvironmentType.LOCAL == "local"

    def test_env_codespace(self):
        assert EnvironmentType.CODESPACE == "codespace"

    def test_env_container(self):
        assert EnvironmentType.CONTAINER == "container"

    def test_env_vm(self):
        assert EnvironmentType.VM == "vm"

    def test_env_remote(self):
        assert EnvironmentType.REMOTE == "remote"

    # HealthIssueType (5)
    def test_issue_dependency_conflict(self):
        assert HealthIssueType.DEPENDENCY_CONFLICT == "dependency_conflict"

    def test_issue_tool_version_drift(self):
        assert HealthIssueType.TOOL_VERSION_DRIFT == "tool_version_drift"

    def test_issue_build_failure(self):
        assert HealthIssueType.BUILD_FAILURE == "build_failure"

    def test_issue_config_mismatch(self):
        assert HealthIssueType.CONFIG_MISMATCH == "config_mismatch"

    def test_issue_resource_exhaustion(self):
        assert HealthIssueType.RESOURCE_EXHAUSTION == "resource_exhaustion"

    # IssueImpact (5)
    def test_impact_blocking(self):
        assert IssueImpact.BLOCKING == "blocking"

    def test_impact_degraded(self):
        assert IssueImpact.DEGRADED == "degraded"

    def test_impact_minor(self):
        assert IssueImpact.MINOR == "minor"

    def test_impact_cosmetic(self):
        assert IssueImpact.COSMETIC == "cosmetic"

    def test_impact_none(self):
        assert IssueImpact.NONE == "none"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_environment_issue_record_defaults(self):
        r = EnvironmentIssueRecord()
        assert r.id
        assert r.developer == ""
        assert r.env_type == EnvironmentType.LOCAL
        assert r.issue_type == HealthIssueType.DEPENDENCY_CONFLICT
        assert r.impact == IssueImpact.MINOR
        assert r.tool_name == ""
        assert r.expected_version == ""
        assert r.actual_version == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_environment_baseline_defaults(self):
        r = EnvironmentBaseline()
        assert r.id
        assert r.env_type == EnvironmentType.LOCAL
        assert r.tool_name == ""
        assert r.required_version == ""
        assert r.max_drift_days == 14
        assert r.details == ""
        assert r.created_at > 0

    def test_dev_environment_report_defaults(self):
        r = DevEnvironmentReport()
        assert r.total_issues == 0
        assert r.total_baselines == 0
        assert r.by_issue_type == {}
        assert r.by_impact == {}
        assert r.blocking_count == 0
        assert r.drift_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_issue
# -------------------------------------------------------------------


class TestRecordIssue:
    def test_basic(self):
        eng = _engine()
        r = eng.record_issue("alice", tool_name="python")
        assert r.developer == "alice"
        assert r.tool_name == "python"
        assert r.impact == IssueImpact.MINOR

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_issue(
            "bob",
            env_type=EnvironmentType.CONTAINER,
            issue_type=HealthIssueType.TOOL_VERSION_DRIFT,
            impact=IssueImpact.BLOCKING,
            tool_name="node",
            expected_version="20.0.0",
            actual_version="18.0.0",
            details="Major version mismatch",
        )
        assert r.env_type == EnvironmentType.CONTAINER
        assert r.issue_type == HealthIssueType.TOOL_VERSION_DRIFT
        assert r.impact == IssueImpact.BLOCKING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_issue(f"dev-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_issue
# -------------------------------------------------------------------


class TestGetIssue:
    def test_found(self):
        eng = _engine()
        r = eng.record_issue("alice")
        assert eng.get_issue(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_issue("nonexistent") is None


# -------------------------------------------------------------------
# list_issues
# -------------------------------------------------------------------


class TestListIssues:
    def test_list_all(self):
        eng = _engine()
        eng.record_issue("alice")
        eng.record_issue("bob")
        assert len(eng.list_issues()) == 2

    def test_filter_by_developer(self):
        eng = _engine()
        eng.record_issue("alice")
        eng.record_issue("bob")
        results = eng.list_issues(developer="alice")
        assert len(results) == 1
        assert results[0].developer == "alice"

    def test_filter_by_issue_type(self):
        eng = _engine()
        eng.record_issue("alice", issue_type=HealthIssueType.BUILD_FAILURE)
        eng.record_issue("bob", issue_type=HealthIssueType.CONFIG_MISMATCH)
        results = eng.list_issues(issue_type=HealthIssueType.BUILD_FAILURE)
        assert len(results) == 1
        assert results[0].developer == "alice"


# -------------------------------------------------------------------
# set_baseline
# -------------------------------------------------------------------


class TestSetBaseline:
    def test_basic(self):
        eng = _engine()
        bl = eng.set_baseline(
            env_type=EnvironmentType.LOCAL,
            tool_name="python",
            required_version="3.12.0",
            max_drift_days=7,
            details="Must use 3.12+",
        )
        assert bl.tool_name == "python"
        assert bl.required_version == "3.12.0"
        assert bl.max_drift_days == 7

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.set_baseline(tool_name=f"tool-{i}")
        assert len(eng._baselines) == 2


# -------------------------------------------------------------------
# detect_version_drift
# -------------------------------------------------------------------


class TestDetectVersionDrift:
    def test_with_drift(self):
        eng = _engine()
        eng.record_issue(
            "alice",
            issue_type=HealthIssueType.TOOL_VERSION_DRIFT,
            tool_name="python",
            expected_version="3.12.0",
            actual_version="3.10.0",
        )
        eng.record_issue(
            "bob",
            issue_type=HealthIssueType.BUILD_FAILURE,
            tool_name="node",
        )
        results = eng.detect_version_drift()
        assert len(results) == 1
        assert results[0]["developer"] == "alice"
        assert results[0]["tool_name"] == "python"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_version_drift() == []


# -------------------------------------------------------------------
# identify_blocking_issues
# -------------------------------------------------------------------


class TestIdentifyBlockingIssues:
    def test_with_blocking(self):
        eng = _engine()
        eng.record_issue("alice", impact=IssueImpact.BLOCKING, tool_name="docker")
        eng.record_issue("bob", impact=IssueImpact.MINOR)
        results = eng.identify_blocking_issues()
        assert len(results) == 1
        assert results[0]["developer"] == "alice"
        assert results[0]["tool_name"] == "docker"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_blocking_issues() == []


# -------------------------------------------------------------------
# rank_most_affected_developers
# -------------------------------------------------------------------


class TestRankMostAffectedDevelopers:
    def test_with_data(self):
        eng = _engine()
        eng.record_issue("alice")
        eng.record_issue("alice")
        eng.record_issue("bob")
        eng.record_issue("carol")
        eng.record_issue("carol")
        eng.record_issue("carol")
        results = eng.rank_most_affected_developers()
        assert len(results) == 3
        assert results[0]["developer"] == "carol"
        assert results[0]["issue_count"] == 3

    def test_empty(self):
        eng = _engine()
        assert eng.rank_most_affected_developers() == []


# -------------------------------------------------------------------
# compare_to_baseline
# -------------------------------------------------------------------


class TestCompareToBaseline:
    def test_with_mismatch(self):
        eng = _engine()
        eng.set_baseline(
            env_type=EnvironmentType.LOCAL,
            tool_name="python",
            required_version="3.12.0",
        )
        eng.record_issue(
            "alice",
            env_type=EnvironmentType.LOCAL,
            tool_name="python",
            actual_version="3.10.0",
        )
        results = eng.compare_to_baseline()
        assert len(results) == 1
        assert results[0]["required_version"] == "3.12.0"
        assert results[0]["actual_version"] == "3.10.0"

    def test_no_mismatch(self):
        eng = _engine()
        eng.set_baseline(
            env_type=EnvironmentType.LOCAL,
            tool_name="python",
            required_version="3.12.0",
        )
        eng.record_issue(
            "alice",
            env_type=EnvironmentType.LOCAL,
            tool_name="python",
            actual_version="3.12.0",
        )
        results = eng.compare_to_baseline()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.compare_to_baseline() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_issue(
            "alice", impact=IssueImpact.BLOCKING, issue_type=HealthIssueType.BUILD_FAILURE
        )
        eng.record_issue(
            "bob", impact=IssueImpact.MINOR, issue_type=HealthIssueType.TOOL_VERSION_DRIFT
        )
        eng.set_baseline(tool_name="python", required_version="3.12.0")
        report = eng.generate_report()
        assert report.total_issues == 2
        assert report.total_baselines == 1
        assert report.by_issue_type != {}
        assert report.by_impact != {}
        assert report.blocking_count == 1
        assert report.drift_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_issues == 0
        assert report.blocking_count == 0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_issue("alice")
        eng.set_baseline(tool_name="python")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_issues"] == 0
        assert stats["total_baselines"] == 0
        assert stats["issue_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_issue("alice", issue_type=HealthIssueType.BUILD_FAILURE)
        eng.record_issue("bob", issue_type=HealthIssueType.CONFIG_MISMATCH)
        eng.set_baseline(tool_name="python")
        stats = eng.get_stats()
        assert stats["total_issues"] == 2
        assert stats["total_baselines"] == 1
        assert stats["unique_developers"] == 2
        assert stats["max_drift_days"] == 14
