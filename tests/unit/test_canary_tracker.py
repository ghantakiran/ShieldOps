"""Tests for shieldops.policy.rollback.canary_tracker — CanaryDeploymentTracker.

Covers CanaryPhase and CanaryMetricResult enums, CanaryDeployment / CanaryMetric
models, and all CanaryDeploymentTracker operations including lifecycle management,
metric recording, rollback decisions, and statistics.
"""

from __future__ import annotations

import pytest

from shieldops.policy.rollback.canary_tracker import (
    CanaryDeployment,
    CanaryDeploymentTracker,
    CanaryMetric,
    CanaryMetricResult,
    CanaryPhase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracker(**kw) -> CanaryDeploymentTracker:
    return CanaryDeploymentTracker(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of CanaryPhase and CanaryMetricResult."""

    # -- CanaryPhase (6 members) ---------------------------------------------

    def test_phase_initialized(self):
        assert CanaryPhase.INITIALIZED == "initialized"

    def test_phase_ramping(self):
        assert CanaryPhase.RAMPING == "ramping"

    def test_phase_stable(self):
        assert CanaryPhase.STABLE == "stable"

    def test_phase_promoted(self):
        assert CanaryPhase.PROMOTED == "promoted"

    def test_phase_rolled_back(self):
        assert CanaryPhase.ROLLED_BACK == "rolled_back"

    def test_phase_paused(self):
        assert CanaryPhase.PAUSED == "paused"

    # -- CanaryMetricResult (3 members) --------------------------------------

    def test_metric_result_pass(self):
        assert CanaryMetricResult.PASS == "pass"  # noqa: S105

    def test_metric_result_fail(self):
        assert CanaryMetricResult.FAIL == "fail"

    def test_metric_result_inconclusive(self):
        assert CanaryMetricResult.INCONCLUSIVE == "inconclusive"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_canary_deployment_defaults(self):
        dep = CanaryDeployment(service="svc1", version="v2")
        assert dep.id
        assert dep.baseline_version == ""
        assert dep.traffic_pct == 0.0
        assert dep.target_traffic_pct == 100.0
        assert dep.phase == CanaryPhase.INITIALIZED
        assert dep.steps == [5, 25, 50, 75, 100]
        assert dep.current_step_index == 0
        assert dep.success_threshold == 0.95
        assert dep.error_rate_limit == 0.05
        assert dep.started_at is None
        assert dep.completed_at is None
        assert dep.owner == ""
        assert dep.metadata == {}
        assert dep.created_at > 0

    def test_canary_metric_defaults(self):
        metric = CanaryMetric(deployment_id="d1", metric_name="latency")
        assert metric.id
        assert metric.baseline_value == 0.0
        assert metric.canary_value == 0.0
        assert metric.result == CanaryMetricResult.PASS
        assert metric.recorded_at > 0


# ===========================================================================
# create_deployment
# ===========================================================================


class TestCreateDeployment:
    """Tests for CanaryDeploymentTracker.create_deployment."""

    def test_basic_create(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        assert dep.service == "svc1"
        assert dep.version == "v2"
        assert dep.phase == CanaryPhase.INITIALIZED
        assert t.get_deployment(dep.id) is dep

    def test_create_with_all_fields(self):
        t = _tracker()
        dep = t.create_deployment(
            "svc1",
            "v2",
            baseline_version="v1",
            steps=[10, 50, 100],
            owner="team-deploy",
            metadata={"region": "us-east-1"},
        )
        assert dep.baseline_version == "v1"
        assert dep.steps == [10, 50, 100]
        assert dep.owner == "team-deploy"
        assert dep.metadata["region"] == "us-east-1"

    def test_create_max_limit(self):
        t = _tracker(max_deployments=2)
        t.create_deployment("svc1", "v1")
        t.create_deployment("svc2", "v1")
        with pytest.raises(ValueError, match="Maximum deployments limit reached"):
            t.create_deployment("svc3", "v1")


# ===========================================================================
# start_canary
# ===========================================================================


class TestStartCanary:
    """Tests for CanaryDeploymentTracker.start_canary."""

    def test_sets_ramping(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        result = t.start_canary(dep.id)
        assert result is not None
        assert result.phase == CanaryPhase.RAMPING
        assert result.started_at is not None

    def test_sets_first_step_traffic(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", steps=[10, 50, 100])
        result = t.start_canary(dep.id)
        assert result is not None
        assert result.traffic_pct == 10
        assert result.current_step_index == 0

    def test_not_found(self):
        t = _tracker()
        assert t.start_canary("nonexistent") is None


# ===========================================================================
# advance_canary
# ===========================================================================


class TestAdvanceCanary:
    """Tests for CanaryDeploymentTracker.advance_canary."""

    def test_advances_step(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", steps=[10, 50, 100])
        t.start_canary(dep.id)
        result = t.advance_canary(dep.id)
        assert result is not None
        assert result.current_step_index == 1
        assert result.traffic_pct == 50

    def test_reaches_stable_at_last_step(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", steps=[10, 50, 100])
        t.start_canary(dep.id)
        # Advance to step index 1 (50) -> still RAMPING
        t.advance_canary(dep.id)
        # Advance to step index 2 (100) -> STABLE (last step)
        result = t.advance_canary(dep.id)
        assert result is not None
        assert result.phase == CanaryPhase.STABLE
        assert result.traffic_pct == 100

    def test_not_found(self):
        t = _tracker()
        assert t.advance_canary("nonexistent") is None

    def test_cannot_advance_after_promotion(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        t.promote_canary(dep.id)
        assert t.advance_canary(dep.id) is None


# ===========================================================================
# promote_canary
# ===========================================================================


class TestPromoteCanary:
    """Tests for CanaryDeploymentTracker.promote_canary."""

    def test_sets_promoted(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        result = t.promote_canary(dep.id)
        assert result is not None
        assert result.phase == CanaryPhase.PROMOTED

    def test_traffic_100(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        result = t.promote_canary(dep.id)
        assert result is not None
        assert result.traffic_pct == 100.0
        assert result.completed_at is not None

    def test_not_found(self):
        t = _tracker()
        assert t.promote_canary("nonexistent") is None


# ===========================================================================
# rollback_canary
# ===========================================================================


class TestRollbackCanary:
    """Tests for CanaryDeploymentTracker.rollback_canary."""

    def test_sets_rolled_back(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        result = t.rollback_canary(dep.id)
        assert result is not None
        assert result.phase == CanaryPhase.ROLLED_BACK

    def test_traffic_zero(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        result = t.rollback_canary(dep.id)
        assert result is not None
        assert result.traffic_pct == 0.0
        assert result.completed_at is not None

    def test_not_found(self):
        t = _tracker()
        assert t.rollback_canary("nonexistent") is None


# ===========================================================================
# pause_canary
# ===========================================================================


class TestPauseCanary:
    """Tests for CanaryDeploymentTracker.pause_canary."""

    def test_sets_paused(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.start_canary(dep.id)
        result = t.pause_canary(dep.id)
        assert result is not None
        assert result.phase == CanaryPhase.PAUSED

    def test_not_found(self):
        t = _tracker()
        assert t.pause_canary("nonexistent") is None


# ===========================================================================
# record_metric
# ===========================================================================


class TestRecordMetric:
    """Tests for CanaryDeploymentTracker.record_metric."""

    def test_pass_result(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", error_rate_limit=0.05)
        metric = t.record_metric(dep.id, "latency", baseline_value=100.0, canary_value=100.0)
        assert metric.result == CanaryMetricResult.PASS

    def test_fail_result(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", error_rate_limit=0.05)
        # fail_threshold = 100 * 1.05 = 105; canary 110 > 105 => FAIL
        metric = t.record_metric(dep.id, "latency", baseline_value=100.0, canary_value=110.0)
        assert metric.result == CanaryMetricResult.FAIL

    def test_inconclusive_result(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", error_rate_limit=0.10)
        # fail_threshold = 100 * 1.10 = 110; warn_threshold = 100 * 1.05 = 105
        # canary 107 > 105 but < 110 => INCONCLUSIVE
        metric = t.record_metric(dep.id, "latency", baseline_value=100.0, canary_value=107.0)
        assert metric.result == CanaryMetricResult.INCONCLUSIVE

    def test_not_found(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Deployment not found"):
            t.record_metric("nonexistent", "latency", 100.0, 100.0)


# ===========================================================================
# list_deployments
# ===========================================================================


class TestListDeployments:
    """Tests for CanaryDeploymentTracker.list_deployments."""

    def test_list_all(self):
        t = _tracker()
        t.create_deployment("svc1", "v1")
        t.create_deployment("svc2", "v2")
        assert len(t.list_deployments()) == 2

    def test_by_service(self):
        t = _tracker()
        t.create_deployment("svc1", "v1")
        t.create_deployment("svc2", "v2")
        result = t.list_deployments(service="svc1")
        assert len(result) == 1
        assert result[0].service == "svc1"

    def test_by_phase(self):
        t = _tracker()
        d1 = t.create_deployment("svc1", "v1")
        t.create_deployment("svc2", "v2")
        t.start_canary(d1.id)
        result = t.list_deployments(phase=CanaryPhase.RAMPING)
        assert len(result) == 1
        assert result[0].phase == CanaryPhase.RAMPING

    def test_empty(self):
        t = _tracker()
        assert t.list_deployments() == []


# ===========================================================================
# get_metrics
# ===========================================================================


class TestGetMetrics:
    """Tests for CanaryDeploymentTracker.get_metrics."""

    def test_returns_metrics_for_deployment(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2")
        t.record_metric(dep.id, "latency", 100.0, 100.0)
        t.record_metric(dep.id, "error_rate", 0.01, 0.01)
        metrics = t.get_metrics(dep.id)
        assert len(metrics) == 2
        assert all(m.deployment_id == dep.id for m in metrics)


# ===========================================================================
# should_rollback
# ===========================================================================


class TestShouldRollback:
    """Tests for CanaryDeploymentTracker.should_rollback."""

    def test_true_when_fail(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", error_rate_limit=0.05)
        # Record a FAIL metric
        t.record_metric(dep.id, "latency", baseline_value=100.0, canary_value=200.0)
        assert t.should_rollback(dep.id) is True

    def test_false_when_all_pass(self):
        t = _tracker()
        dep = t.create_deployment("svc1", "v2", error_rate_limit=0.05)
        t.record_metric(dep.id, "latency", baseline_value=100.0, canary_value=100.0)
        assert t.should_rollback(dep.id) is False


# ===========================================================================
# get_stats
# ===========================================================================


class TestGetStats:
    """Tests for CanaryDeploymentTracker.get_stats."""

    def test_empty_stats(self):
        t = _tracker()
        stats = t.get_stats()
        assert stats["total_deployments"] == 0
        assert stats["by_phase"] == {}
        assert stats["total_metrics"] == 0
        assert stats["promotion_rate"] == 0.0
        assert stats["rollback_rate"] == 0.0

    def test_populated_stats(self):
        t = _tracker()
        d1 = t.create_deployment("svc1", "v1")
        d2 = t.create_deployment("svc2", "v2")
        t.start_canary(d1.id)
        t.promote_canary(d1.id)
        t.start_canary(d2.id)
        t.rollback_canary(d2.id)
        t.record_metric(d1.id, "latency", 100.0, 100.0)
        stats = t.get_stats()
        assert stats["total_deployments"] == 2
        assert stats["total_metrics"] == 1
        assert stats["by_phase"]["promoted"] == 1
        assert stats["by_phase"]["rolled_back"] == 1
        assert stats["promotion_rate"] == 50.0
        assert stats["rollback_rate"] == 50.0

    def test_promotion_rate(self):
        t = _tracker()
        d1 = t.create_deployment("svc1", "v1")
        d2 = t.create_deployment("svc2", "v1")
        d3 = t.create_deployment("svc3", "v1")
        t.promote_canary(d1.id)
        t.promote_canary(d2.id)
        t.rollback_canary(d3.id)
        stats = t.get_stats()
        # 2 promoted / 3 completed = 66.67%
        assert abs(stats["promotion_rate"] - 66.66666666666667) < 0.01

    def test_rollback_rate(self):
        t = _tracker()
        d1 = t.create_deployment("svc1", "v1")
        d2 = t.create_deployment("svc2", "v1")
        t.promote_canary(d1.id)
        t.rollback_canary(d2.id)
        stats = t.get_stats()
        # 1 rolled_back / 2 completed = 50%
        assert stats["rollback_rate"] == 50.0
