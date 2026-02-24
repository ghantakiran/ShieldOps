"""Tests for shieldops.changes.change_failure_tracker — ChangeFailureRateTracker."""

from __future__ import annotations

from shieldops.changes.change_failure_tracker import (
    ChangeFailureRateTracker,
    ChangeFailureReport,
    ChangeScope,
    DeploymentRecord,
    DeploymentResult,
    FailureRateScore,
    FailureTrend,
)


def _engine(**kw) -> ChangeFailureRateTracker:
    return ChangeFailureRateTracker(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestDeploymentResult:
    """Test every DeploymentResult member."""

    def test_success(self):
        assert DeploymentResult.SUCCESS == "success"

    def test_partial_failure(self):
        assert DeploymentResult.PARTIAL_FAILURE == "partial_failure"

    def test_full_failure(self):
        assert DeploymentResult.FULL_FAILURE == "full_failure"

    def test_rollback(self):
        assert DeploymentResult.ROLLBACK == "rollback"

    def test_hotfix_required(self):
        assert DeploymentResult.HOTFIX_REQUIRED == "hotfix_required"


class TestFailureTrend:
    """Test every FailureTrend member."""

    def test_improving(self):
        assert FailureTrend.IMPROVING == "improving"

    def test_stable(self):
        assert FailureTrend.STABLE == "stable"

    def test_degrading(self):
        assert FailureTrend.DEGRADING == "degrading"

    def test_critical_degradation(self):
        assert FailureTrend.CRITICAL_DEGRADATION == "critical_degradation"

    def test_insufficient_data(self):
        assert FailureTrend.INSUFFICIENT_DATA == "insufficient_data"


class TestChangeScope:
    """Test every ChangeScope member."""

    def test_patch(self):
        assert ChangeScope.PATCH == "patch"

    def test_minor(self):
        assert ChangeScope.MINOR == "minor"

    def test_major(self):
        assert ChangeScope.MAJOR == "major"

    def test_infrastructure(self):
        assert ChangeScope.INFRASTRUCTURE == "infrastructure"

    def test_configuration(self):
        assert ChangeScope.CONFIGURATION == "configuration"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_deployment_record_defaults(self):
        m = DeploymentRecord()
        assert m.id
        assert m.service_name == ""
        assert m.result == DeploymentResult.SUCCESS
        assert m.scope == ChangeScope.PATCH
        assert m.recovery_time_minutes == 0.0

    def test_failure_rate_score_defaults(self):
        m = FailureRateScore()
        assert m.id
        assert m.total_deployments == 0
        assert m.failure_rate_pct == 0.0
        assert m.trend == FailureTrend.INSUFFICIENT_DATA
        assert m.window_days == 30

    def test_change_failure_report_defaults(self):
        m = ChangeFailureReport()
        assert m.total_deployments == 0
        assert m.total_failures == 0
        assert m.overall_failure_rate == 0.0
        assert m.by_result == {}
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# record_deployment
# ---------------------------------------------------------------------------


class TestRecordDeployment:
    """Test ChangeFailureRateTracker.record_deployment."""

    def test_basic(self):
        eng = _engine()
        rec = eng.record_deployment(
            service_name="api", team="platform", result=DeploymentResult.SUCCESS
        )
        assert rec.service_name == "api"
        assert rec.team == "platform"
        assert rec.result == DeploymentResult.SUCCESS
        assert rec.id

    def test_eviction(self):
        eng = _engine(max_deployments=2)
        eng.record_deployment(service_name="a")
        eng.record_deployment(service_name="b")
        eng.record_deployment(service_name="c")
        deps = eng.list_deployments()
        assert len(deps) == 2
        assert deps[0].service_name == "b"
        assert deps[1].service_name == "c"


# ---------------------------------------------------------------------------
# get_deployment
# ---------------------------------------------------------------------------


class TestGetDeployment:
    """Test ChangeFailureRateTracker.get_deployment."""

    def test_found(self):
        eng = _engine()
        rec = eng.record_deployment(service_name="web")
        found = eng.get_deployment(rec.id)
        assert found is not None
        assert found.service_name == "web"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_deployment("nonexistent-id") is None


# ---------------------------------------------------------------------------
# list_deployments
# ---------------------------------------------------------------------------


class TestListDeployments:
    """Test ChangeFailureRateTracker.list_deployments."""

    def test_all(self):
        eng = _engine()
        eng.record_deployment(service_name="a")
        eng.record_deployment(service_name="b")
        assert len(eng.list_deployments()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_deployment(service_name="api")
        eng.record_deployment(service_name="web")
        eng.record_deployment(service_name="api")
        result = eng.list_deployments(service_name="api")
        assert len(result) == 2
        assert all(d.service_name == "api" for d in result)

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_deployment(result=DeploymentResult.SUCCESS)
        eng.record_deployment(result=DeploymentResult.ROLLBACK)
        eng.record_deployment(result=DeploymentResult.SUCCESS)
        result = eng.list_deployments(result=DeploymentResult.ROLLBACK)
        assert len(result) == 1
        assert result[0].result == DeploymentResult.ROLLBACK


# ---------------------------------------------------------------------------
# calculate_failure_rate
# ---------------------------------------------------------------------------


class TestCalculateFailureRate:
    """Test ChangeFailureRateTracker.calculate_failure_rate."""

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_deployment(service_name="svc", result=DeploymentResult.SUCCESS)
        eng.record_deployment(service_name="svc", result=DeploymentResult.SUCCESS)
        score = eng.calculate_failure_rate("svc")
        assert score.trend == FailureTrend.INSUFFICIENT_DATA
        assert score.total_deployments == 2

    def test_low_rate_improving(self):
        eng = _engine()
        # 3 successes, 0 failures -> 0% failure rate -> IMPROVING
        for _ in range(3):
            eng.record_deployment(service_name="svc", result=DeploymentResult.SUCCESS)
        score = eng.calculate_failure_rate("svc")
        assert score.failure_rate_pct < 5.0
        assert score.trend == FailureTrend.IMPROVING

    def test_high_rate_critical_degradation(self):
        eng = _engine()
        # 1 success, 3 failures -> 75% failure rate -> CRITICAL_DEGRADATION
        eng.record_deployment(service_name="svc", result=DeploymentResult.SUCCESS)
        eng.record_deployment(service_name="svc", result=DeploymentResult.FULL_FAILURE)
        eng.record_deployment(service_name="svc", result=DeploymentResult.ROLLBACK)
        eng.record_deployment(service_name="svc", result=DeploymentResult.HOTFIX_REQUIRED)
        score = eng.calculate_failure_rate("svc")
        assert score.failure_rate_pct >= 30.0
        assert score.trend == FailureTrend.CRITICAL_DEGRADATION


# ---------------------------------------------------------------------------
# detect_failure_trend
# ---------------------------------------------------------------------------


class TestDetectFailureTrend:
    """Test ChangeFailureRateTracker.detect_failure_trend."""

    def test_basic_trend_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_deployment(service_name="api", result=DeploymentResult.SUCCESS)
        result = eng.detect_failure_trend("api")
        assert result["service_name"] == "api"
        assert result["trend"] == FailureTrend.IMPROVING.value
        assert result["failure_rate_pct"] == 0.0
        assert result["total_deployments"] == 5
        assert result["recent_failures"] == 0

    def test_trend_with_mixed_results(self):
        eng = _engine()
        eng.record_deployment(service_name="web", result=DeploymentResult.SUCCESS)
        eng.record_deployment(service_name="web", result=DeploymentResult.ROLLBACK)
        eng.record_deployment(service_name="web", result=DeploymentResult.SUCCESS)
        result = eng.detect_failure_trend("web")
        assert result["recent_failures"] == 1
        assert result["failure_rate_pct"] > 0


# ---------------------------------------------------------------------------
# rank_services_by_reliability
# ---------------------------------------------------------------------------


class TestRankServicesByReliability:
    """Test ChangeFailureRateTracker.rank_services_by_reliability."""

    def test_multiple_services_sorted_ascending(self):
        eng = _engine()
        # svc-good: 4 success, 0 failures = 0%
        for _ in range(4):
            eng.record_deployment(service_name="svc-good", result=DeploymentResult.SUCCESS)
        # svc-bad: 1 success, 3 failures = 75%
        eng.record_deployment(service_name="svc-bad", result=DeploymentResult.SUCCESS)
        eng.record_deployment(service_name="svc-bad", result=DeploymentResult.FULL_FAILURE)
        eng.record_deployment(service_name="svc-bad", result=DeploymentResult.FULL_FAILURE)
        eng.record_deployment(service_name="svc-bad", result=DeploymentResult.FULL_FAILURE)
        ranked = eng.rank_services_by_reliability()
        assert len(ranked) == 2
        assert ranked[0].service_name == "svc-good"
        assert ranked[1].service_name == "svc-bad"
        assert ranked[0].failure_rate_pct < ranked[1].failure_rate_pct


# ---------------------------------------------------------------------------
# identify_risky_change_types
# ---------------------------------------------------------------------------


class TestIdentifyRiskyChangeTypes:
    """Test ChangeFailureRateTracker.identify_risky_change_types."""

    def test_multiple_scopes_sorted_descending(self):
        eng = _engine()
        # PATCH: 2 success = 0% failure
        eng.record_deployment(scope=ChangeScope.PATCH, result=DeploymentResult.SUCCESS)
        eng.record_deployment(scope=ChangeScope.PATCH, result=DeploymentResult.SUCCESS)
        # MAJOR: 1 success, 1 failure = 50%
        eng.record_deployment(scope=ChangeScope.MAJOR, result=DeploymentResult.SUCCESS)
        eng.record_deployment(scope=ChangeScope.MAJOR, result=DeploymentResult.FULL_FAILURE)
        risky = eng.identify_risky_change_types()
        assert len(risky) == 2
        assert risky[0]["scope"] == "major"
        assert risky[0]["failure_rate_pct"] == 50.0
        assert risky[1]["scope"] == "patch"
        assert risky[1]["failure_rate_pct"] == 0.0


# ---------------------------------------------------------------------------
# calculate_recovery_time
# ---------------------------------------------------------------------------


class TestCalculateRecoveryTime:
    """Test ChangeFailureRateTracker.calculate_recovery_time."""

    def test_with_failures(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api", result=DeploymentResult.FULL_FAILURE, recovery_time_minutes=30.0
        )
        eng.record_deployment(
            service_name="api", result=DeploymentResult.ROLLBACK, recovery_time_minutes=60.0
        )
        result = eng.calculate_recovery_time()
        assert result["total_failures"] == 2
        assert result["avg_recovery_minutes"] == 45.0
        assert result["min_recovery_minutes"] == 30.0
        assert result["max_recovery_minutes"] == 60.0

    def test_no_failures(self):
        eng = _engine()
        eng.record_deployment(result=DeploymentResult.SUCCESS)
        result = eng.calculate_recovery_time()
        assert result["total_failures"] == 0
        assert result["avg_recovery_minutes"] == 0.0

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api", result=DeploymentResult.FULL_FAILURE, recovery_time_minutes=20.0
        )
        eng.record_deployment(
            service_name="web", result=DeploymentResult.FULL_FAILURE, recovery_time_minutes=80.0
        )
        result = eng.calculate_recovery_time(service_name="api")
        assert result["service_name"] == "api"
        assert result["total_failures"] == 1
        assert result["avg_recovery_minutes"] == 20.0


# ---------------------------------------------------------------------------
# generate_failure_report
# ---------------------------------------------------------------------------


class TestGenerateFailureReport:
    """Test ChangeFailureRateTracker.generate_failure_report."""

    def test_basic(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api", result=DeploymentResult.SUCCESS, scope=ChangeScope.PATCH
        )
        eng.record_deployment(
            service_name="web",
            result=DeploymentResult.FULL_FAILURE,
            scope=ChangeScope.MAJOR,
            recovery_time_minutes=45.0,
        )
        report = eng.generate_failure_report()
        assert isinstance(report, ChangeFailureReport)
        assert report.total_deployments == 2
        assert report.total_failures == 1
        assert report.overall_failure_rate == 50.0
        assert "success" in report.by_result
        assert "full_failure" in report.by_result
        assert report.avg_recovery_minutes == 45.0

    def test_report_includes_recommendations_for_high_failure_rate(self):
        eng = _engine()
        # Create > 30% failure rate to trigger critical recommendation
        eng.record_deployment(result=DeploymentResult.FULL_FAILURE)
        eng.record_deployment(result=DeploymentResult.FULL_FAILURE)
        eng.record_deployment(result=DeploymentResult.SUCCESS)
        report = eng.generate_failure_report()
        assert any("30%" in r for r in report.recommendations)

    def test_report_by_scope_and_by_service(self):
        eng = _engine()
        eng.record_deployment(service_name="api", scope=ChangeScope.MINOR)
        eng.record_deployment(service_name="web", scope=ChangeScope.PATCH)
        report = eng.generate_failure_report()
        assert "minor" in report.by_scope
        assert "patch" in report.by_scope
        assert "api" in report.by_service
        assert "web" in report.by_service


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test ChangeFailureRateTracker.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.record_deployment(service_name="x")
        eng.record_deployment(service_name="y")
        eng.clear_data()
        assert eng.list_deployments() == []
        assert eng.get_stats()["total_deployments"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test ChangeFailureRateTracker.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_deployments"] == 0
        assert stats["unique_services"] == 0
        assert stats["unique_teams"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_deployment(service_name="api", team="platform", result=DeploymentResult.SUCCESS)
        eng.record_deployment(
            service_name="web", team="frontend", result=DeploymentResult.FULL_FAILURE
        )
        eng.record_deployment(service_name="api", team="platform", result=DeploymentResult.ROLLBACK)
        stats = eng.get_stats()
        assert stats["total_deployments"] == 3
        assert stats["unique_services"] == 2
        assert stats["unique_teams"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 2
