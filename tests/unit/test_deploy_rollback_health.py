"""Tests for shieldops.changes.deploy_rollback_health — DeployRollbackHealthTracker."""

from __future__ import annotations

from shieldops.changes.deploy_rollback_health import (
    DeployRollbackHealthReport,
    DeployRollbackHealthTracker,
    RecoverySpeed,
    RollbackHealthRecord,
    RollbackHealthStatus,
    RollbackMetric,
    RollbackTrigger,
)


def _engine(**kw) -> DeployRollbackHealthTracker:
    return DeployRollbackHealthTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_healthy(self):
        assert RollbackHealthStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert RollbackHealthStatus.DEGRADED == "degraded"

    def test_status_slow(self):
        assert RollbackHealthStatus.SLOW == "slow"

    def test_status_failed(self):
        assert RollbackHealthStatus.FAILED == "failed"

    def test_status_untested(self):
        assert RollbackHealthStatus.UNTESTED == "untested"

    def test_trigger_automated(self):
        assert RollbackTrigger.AUTOMATED == "automated"

    def test_trigger_manual(self):
        assert RollbackTrigger.MANUAL == "manual"

    def test_trigger_policy_violation(self):
        assert RollbackTrigger.POLICY_VIOLATION == "policy_violation"

    def test_trigger_health_check(self):
        assert RollbackTrigger.HEALTH_CHECK == "health_check"

    def test_trigger_timeout(self):
        assert RollbackTrigger.TIMEOUT == "timeout"

    def test_speed_instant(self):
        assert RecoverySpeed.INSTANT == "instant"

    def test_speed_fast(self):
        assert RecoverySpeed.FAST == "fast"

    def test_speed_moderate(self):
        assert RecoverySpeed.MODERATE == "moderate"

    def test_speed_slow(self):
        assert RecoverySpeed.SLOW == "slow"

    def test_speed_manual_intervention(self):
        assert RecoverySpeed.MANUAL_INTERVENTION == "manual_intervention"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rollback_health_record_defaults(self):
        r = RollbackHealthRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.rollback_health_status == RollbackHealthStatus.UNTESTED
        assert r.rollback_trigger == RollbackTrigger.AUTOMATED
        assert r.recovery_speed == RecoverySpeed.MODERATE
        assert r.recovery_time_seconds == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_rollback_metric_defaults(self):
        m = RollbackMetric()
        assert m.id
        assert m.deployment_id == ""
        assert m.rollback_health_status == RollbackHealthStatus.UNTESTED
        assert m.metric_value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_deploy_rollback_health_report_defaults(self):
        r = DeployRollbackHealthReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.unhealthy_rollbacks == 0
        assert r.avg_recovery_time == 0.0
        assert r.by_status == {}
        assert r.by_trigger == {}
        assert r.by_speed == {}
        assert r.top_slow_recoveries == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_rollback
# ---------------------------------------------------------------------------


class TestRecordRollback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
            rollback_trigger=RollbackTrigger.AUTOMATED,
            recovery_speed=RecoverySpeed.FAST,
            recovery_time_seconds=15.0,
            service="api-gateway",
            team="sre",
        )
        assert r.deployment_id == "DEP-001"
        assert r.rollback_health_status == RollbackHealthStatus.HEALTHY
        assert r.rollback_trigger == RollbackTrigger.AUTOMATED
        assert r.recovery_speed == RecoverySpeed.FAST
        assert r.recovery_time_seconds == 15.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rollback(deployment_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_rollback
# ---------------------------------------------------------------------------


class TestGetRollback:
    def test_found(self):
        eng = _engine()
        r = eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
        )
        result = eng.get_rollback(r.id)
        assert result is not None
        assert result.rollback_health_status == RollbackHealthStatus.HEALTHY

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rollback("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rollbacks
# ---------------------------------------------------------------------------


class TestListRollbacks:
    def test_list_all(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001")
        eng.record_rollback(deployment_id="DEP-002")
        assert len(eng.list_rollbacks()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_health_status=RollbackHealthStatus.FAILED,
        )
        results = eng.list_rollbacks(
            status=RollbackHealthStatus.HEALTHY,
        )
        assert len(results) == 1

    def test_filter_by_trigger(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_trigger=RollbackTrigger.AUTOMATED,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_trigger=RollbackTrigger.MANUAL,
        )
        results = eng.list_rollbacks(
            trigger=RollbackTrigger.AUTOMATED,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001", service="api-gateway")
        eng.record_rollback(deployment_id="DEP-002", service="auth-svc")
        results = eng.list_rollbacks(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rollback(deployment_id="DEP-001", team="sre")
        eng.record_rollback(deployment_id="DEP-002", team="platform")
        results = eng.list_rollbacks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rollback(deployment_id=f"DEP-{i}")
        assert len(eng.list_rollbacks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.DEGRADED,
            metric_value=85.0,
            threshold=90.0,
            breached=True,
            description="Recovery time exceeded",
        )
        assert m.deployment_id == "DEP-001"
        assert m.rollback_health_status == RollbackHealthStatus.DEGRADED
        assert m.metric_value == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Recovery time exceeded"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(deployment_id=f"DEP-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_rollback_health
# ---------------------------------------------------------------------------


class TestAnalyzeRollbackHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
            recovery_time_seconds=10.0,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
            recovery_time_seconds=20.0,
        )
        result = eng.analyze_rollback_health()
        assert "healthy" in result
        assert result["healthy"]["count"] == 2
        assert result["healthy"]["avg_recovery_time"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_rollback_health() == {}


# ---------------------------------------------------------------------------
# identify_unhealthy_rollbacks
# ---------------------------------------------------------------------------


class TestIdentifyUnhealthyRollbacks:
    def test_detects_unhealthy(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.FAILED,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
        )
        results = eng.identify_unhealthy_rollbacks()
        assert len(results) == 1
        assert results[0]["deployment_id"] == "DEP-001"

    def test_detects_degraded(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.DEGRADED,
        )
        results = eng.identify_unhealthy_rollbacks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_rollbacks() == []


# ---------------------------------------------------------------------------
# rank_by_recovery_time
# ---------------------------------------------------------------------------


class TestRankByRecoveryTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            service="api-gateway",
            recovery_time_seconds=120.0,
        )
        eng.record_rollback(
            deployment_id="DEP-002",
            service="auth-svc",
            recovery_time_seconds=30.0,
        )
        results = eng.rank_by_recovery_time()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_recovery_time"] == 120.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_recovery_time() == []


# ---------------------------------------------------------------------------
# detect_health_trends
# ---------------------------------------------------------------------------


class TestDetectHealthTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.record_rollback(deployment_id="DEP-1", recovery_time_seconds=val)
        result = eng.detect_health_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [120.0, 120.0, 30.0, 30.0]:
            eng.record_rollback(deployment_id="DEP-1", recovery_time_seconds=val)
        result = eng.detect_health_trends()
        assert result["trend"] == "improving"
        assert result["delta"] < 0

    def test_degrading(self):
        eng = _engine()
        for val in [30.0, 30.0, 120.0, 120.0]:
            eng.record_rollback(deployment_id="DEP-1", recovery_time_seconds=val)
        result = eng.detect_health_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_health_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.FAILED,
            rollback_trigger=RollbackTrigger.HEALTH_CHECK,
            recovery_speed=RecoverySpeed.SLOW,
            recovery_time_seconds=500.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DeployRollbackHealthReport)
        assert report.total_records == 1
        assert report.unhealthy_rollbacks == 1
        assert len(report.top_slow_recoveries) >= 1
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
        eng.record_rollback(deployment_id="DEP-001")
        eng.add_metric(deployment_id="DEP-001")
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
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rollback(
            deployment_id="DEP-001",
            rollback_health_status=RollbackHealthStatus.HEALTHY,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "healthy" in stats["status_distribution"]
