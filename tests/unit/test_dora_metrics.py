"""Tests for shieldops.analytics.dora_metrics – DORAMetricsEngine."""

from __future__ import annotations

from shieldops.analytics.dora_metrics import (
    DeploymentRecord,
    DORALevel,
    DORAMetricsEngine,
    DORAMetricType,
    FailureRecord,
    RecoveryRecord,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kwargs) -> DORAMetricsEngine:
    return DORAMetricsEngine(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestDORAEnums:
    def test_dora_level_values(self):
        assert DORALevel.ELITE == "elite"
        assert DORALevel.HIGH == "high"
        assert DORALevel.MEDIUM == "medium"
        assert DORALevel.LOW == "low"

    def test_dora_metric_type_values(self):
        assert DORAMetricType.DEPLOYMENT_FREQUENCY == "deployment_frequency"
        assert DORAMetricType.LEAD_TIME == "lead_time"
        assert DORAMetricType.CHANGE_FAILURE_RATE == "change_failure_rate"
        assert DORAMetricType.MTTR == "mttr"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestDORAModels:
    def test_deployment_record_defaults(self):
        r = DeploymentRecord(service="api")
        assert r.service == "api"
        assert r.environment == "production"
        assert r.lead_time_seconds == 0.0
        assert r.id

    def test_failure_record_defaults(self):
        r = FailureRecord(service="api")
        assert r.service == "api"
        assert r.deployment_id == ""

    def test_recovery_record_defaults(self):
        r = RecoveryRecord(service="api")
        assert r.service == "api"
        assert r.recovery_time_seconds == 0.0


# ---------------------------------------------------------------------------
# Record operations
# ---------------------------------------------------------------------------


class TestRecordOperations:
    def test_record_deployment_basic(self):
        e = _engine()
        r = e.record_deployment(service="api")
        assert r.service == "api"
        assert r.id

    def test_record_deployment_with_metadata(self):
        e = _engine()
        r = e.record_deployment(service="api", commit_sha="abc123", metadata={"env": "prod"})
        assert r.commit_sha == "abc123"
        assert r.metadata["env"] == "prod"

    def test_record_deployment_auto_trim(self):
        e = _engine(max_records=10)
        for _i in range(15):
            e.record_deployment(service="api")
        stats = e.get_stats()
        assert stats["total_deployments"] <= 11  # trimmed to half + new

    def test_record_failure_basic(self):
        e = _engine()
        r = e.record_failure(service="api", description="timeout")
        assert r.service == "api"
        assert r.description == "timeout"

    def test_record_recovery_basic(self):
        e = _engine()
        r = e.record_recovery(service="api", recovery_time_seconds=120.0)
        assert r.recovery_time_seconds == 120.0


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_classify_deployment_frequency_elite(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.DEPLOYMENT_FREQUENCY, 2.0) == DORALevel.ELITE

    def test_classify_deployment_frequency_high(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.DEPLOYMENT_FREQUENCY, 0.2) == DORALevel.HIGH

    def test_classify_deployment_frequency_medium(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.DEPLOYMENT_FREQUENCY, 0.05) == DORALevel.MEDIUM

    def test_classify_deployment_frequency_low(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.DEPLOYMENT_FREQUENCY, 0.01) == DORALevel.LOW

    def test_classify_lead_time_elite(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.LEAD_TIME, 3600) == DORALevel.ELITE

    def test_classify_lead_time_high(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.LEAD_TIME, 259200) == DORALevel.HIGH

    def test_classify_lead_time_low(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.LEAD_TIME, 999999999) == DORALevel.LOW

    def test_classify_change_failure_rate_elite(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.CHANGE_FAILURE_RATE, 0.03) == DORALevel.ELITE

    def test_classify_change_failure_rate_low(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.CHANGE_FAILURE_RATE, 0.5) == DORALevel.LOW

    def test_classify_mttr_elite(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.MTTR, 1800) == DORALevel.ELITE

    def test_classify_mttr_high(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.MTTR, 43200) == DORALevel.HIGH

    def test_classify_mttr_low(self):
        e = _engine()
        assert e.classify_level(DORAMetricType.MTTR, 9999999) == DORALevel.LOW


# ---------------------------------------------------------------------------
# Compute snapshot
# ---------------------------------------------------------------------------


class TestComputeSnapshot:
    def test_snapshot_empty_service(self):
        e = _engine()
        snap = e.compute_snapshot("api")
        assert snap.total_deployments == 0
        assert snap.deployment_frequency == 0.0

    def test_snapshot_with_data(self):
        e = _engine(default_period_days=30)
        for _ in range(10):
            e.record_deployment(service="api", lead_time_seconds=3600)
        e.record_failure(service="api")
        e.record_recovery(service="api", recovery_time_seconds=600)
        snap = e.compute_snapshot("api")
        assert snap.total_deployments == 10
        assert snap.total_failures == 1
        assert snap.total_recoveries == 1
        assert snap.lead_time_seconds == 3600.0
        assert snap.change_failure_rate == 0.1

    def test_snapshot_custom_period(self):
        e = _engine()
        e.record_deployment(service="api")
        snap = e.compute_snapshot("api", period_days=7)
        assert snap.total_deployments == 1

    def test_snapshot_overall_level_elite(self):
        e = _engine()
        # Many deploys, fast lead time
        for _ in range(100):
            e.record_deployment(service="api", lead_time_seconds=100)
        e.record_recovery(service="api", recovery_time_seconds=60)
        snap = e.compute_snapshot("api")
        assert snap.overall_level in (DORALevel.ELITE, DORALevel.HIGH)


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------


class TestTrends:
    def test_trends_empty(self):
        e = _engine()
        trends = e.get_trends("api", periods=3)
        assert len(trends) == 3
        assert all(t.total_deployments == 0 for t in trends)

    def test_trends_with_data(self):
        e = _engine()
        e.record_deployment(service="api")
        trends = e.get_trends("api", periods=2, period_days=30)
        assert len(trends) == 2

    def test_trends_order(self):
        e = _engine()
        trends = e.get_trends("api", periods=4)
        # Should be oldest first
        assert trends[0].period_start <= trends[-1].period_start


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        e = _engine()
        s = e.get_stats()
        assert s["total_deployments"] == 0
        assert s["total_failures"] == 0
        assert s["total_recoveries"] == 0
        assert s["tracked_services"] == 0

    def test_stats_with_data(self):
        e = _engine()
        e.record_deployment(service="api")
        e.record_deployment(service="web")
        e.record_failure(service="api")
        s = e.get_stats()
        assert s["total_deployments"] == 2
        assert s["total_failures"] == 1
        assert s["tracked_services"] == 2

    def test_snapshot_model_fields(self):
        e = _engine()
        e.record_deployment(service="x")
        snap = e.compute_snapshot("x")
        d = snap.model_dump()
        assert "deployment_frequency" in d
        assert "lead_time_seconds" in d
        assert "change_failure_rate" in d
        assert "mttr_seconds" in d
        assert "overall_level" in d
