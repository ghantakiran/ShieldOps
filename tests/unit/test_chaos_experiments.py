"""Tests for shieldops.observability.chaos_experiments — ChaosExperimentTracker."""

from __future__ import annotations

import pytest

from shieldops.observability.chaos_experiments import (
    ChaosExperiment,
    ChaosExperimentTracker,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
)


def _tracker(**kw) -> ChaosExperimentTracker:
    return ChaosExperimentTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ExperimentType (6 values)

    def test_experiment_type_latency_injection(self):
        assert ExperimentType.LATENCY_INJECTION == "latency_injection"

    def test_experiment_type_fault_injection(self):
        assert ExperimentType.FAULT_INJECTION == "fault_injection"

    def test_experiment_type_resource_stress(self):
        assert ExperimentType.RESOURCE_STRESS == "resource_stress"

    def test_experiment_type_network_partition(self):
        assert ExperimentType.NETWORK_PARTITION == "network_partition"

    def test_experiment_type_node_failure(self):
        assert ExperimentType.NODE_FAILURE == "node_failure"

    def test_experiment_type_dependency_failure(self):
        assert ExperimentType.DEPENDENCY_FAILURE == "dependency_failure"

    # ExperimentStatus (5 values)

    def test_experiment_status_planned(self):
        assert ExperimentStatus.PLANNED == "planned"

    def test_experiment_status_running(self):
        assert ExperimentStatus.RUNNING == "running"

    def test_experiment_status_completed(self):
        assert ExperimentStatus.COMPLETED == "completed"

    def test_experiment_status_aborted(self):
        assert ExperimentStatus.ABORTED == "aborted"

    def test_experiment_status_failed(self):
        assert ExperimentStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_chaos_experiment_defaults(self):
        exp = ChaosExperiment(
            name="cpu-stress",
            experiment_type=ExperimentType.RESOURCE_STRESS,
            target_service="web",
        )
        assert exp.id
        assert exp.hypothesis == ""
        assert exp.blast_radius == "single-service"
        assert exp.status == ExperimentStatus.PLANNED
        assert exp.started_at is None
        assert exp.completed_at is None
        assert exp.findings == []
        assert exp.steady_state_met is None
        assert exp.rollback_triggered is False
        assert exp.owner == ""
        assert exp.metadata == {}
        assert exp.created_at > 0

    def test_experiment_result_defaults(self):
        r = ExperimentResult(experiment_id="e1", metric_name="latency_p99")
        assert r.id
        assert r.baseline_value == 0.0
        assert r.observed_value == 0.0
        assert r.impact_pct == 0.0
        assert r.within_tolerance is True
        assert r.recorded_at > 0


# ---------------------------------------------------------------------------
# create_experiment
# ---------------------------------------------------------------------------


class TestCreateExperiment:
    def test_basic_create(self):
        t = _tracker()
        exp = t.create_experiment("cpu-stress", ExperimentType.RESOURCE_STRESS, "web-svc")
        assert exp.name == "cpu-stress"
        assert exp.experiment_type == ExperimentType.RESOURCE_STRESS
        assert exp.target_service == "web-svc"
        assert exp.status == ExperimentStatus.PLANNED

    def test_create_all_fields(self):
        t = _tracker()
        exp = t.create_experiment(
            "net-partition",
            ExperimentType.NETWORK_PARTITION,
            "db-svc",
            hypothesis="DB failover completes in < 30s",
            blast_radius="multi-service",
            owner="sre-team",
        )
        assert exp.hypothesis == "DB failover completes in < 30s"
        assert exp.blast_radius == "multi-service"
        assert exp.owner == "sre-team"

    def test_create_max_limit(self):
        t = _tracker(max_experiments=2)
        t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "svc1")
        t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "svc2")
        with pytest.raises(ValueError, match="Max experiments limit reached"):
            t.create_experiment("e3", ExperimentType.NODE_FAILURE, "svc3")


# ---------------------------------------------------------------------------
# start_experiment
# ---------------------------------------------------------------------------


class TestStartExperiment:
    def test_basic_start(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        result = t.start_experiment(exp.id)
        assert result is not None
        assert result.status == ExperimentStatus.RUNNING

    def test_sets_running(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.start_experiment(exp.id)
        assert exp.status == ExperimentStatus.RUNNING
        assert exp.started_at is not None

    def test_start_not_found(self):
        t = _tracker()
        result = t.start_experiment("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# complete_experiment
# ---------------------------------------------------------------------------


class TestCompleteExperiment:
    def test_basic_complete(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.start_experiment(exp.id)
        result = t.complete_experiment(exp.id, steady_state_met=True)
        assert result is not None
        assert result.status == ExperimentStatus.COMPLETED
        assert result.steady_state_met is True
        assert result.completed_at is not None

    def test_complete_with_findings(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.FAULT_INJECTION, "api")
        t.start_experiment(exp.id)
        result = t.complete_experiment(
            exp.id,
            steady_state_met=False,
            findings=["p99 latency exceeded SLO", "error rate spiked 5x"],
        )
        assert result is not None
        assert result.steady_state_met is False
        assert len(result.findings) == 2
        assert "p99 latency exceeded SLO" in result.findings

    def test_complete_not_found(self):
        t = _tracker()
        result = t.complete_experiment("nonexistent", steady_state_met=True)
        assert result is None


# ---------------------------------------------------------------------------
# abort_experiment
# ---------------------------------------------------------------------------


class TestAbortExperiment:
    def test_basic_abort(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.RESOURCE_STRESS, "db")
        t.start_experiment(exp.id)
        result = t.abort_experiment(exp.id)
        assert result is not None
        assert result.status == ExperimentStatus.ABORTED
        assert result.rollback_triggered is True
        assert result.completed_at is not None

    def test_abort_adds_reason(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.RESOURCE_STRESS, "db")
        t.start_experiment(exp.id)
        result = t.abort_experiment(exp.id, reason="Critical alert triggered")
        assert result is not None
        assert "Critical alert triggered" in result.findings

    def test_abort_not_found(self):
        t = _tracker()
        result = t.abort_experiment("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# record_result
# ---------------------------------------------------------------------------


class TestRecordResult:
    def test_within_tolerance(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        r = t.record_result(
            exp.id, "latency_p99", baseline_value=100.0, observed_value=105.0, tolerance_pct=10.0
        )
        assert r.within_tolerance is True
        assert r.impact_pct == pytest.approx(5.0, abs=0.01)

    def test_outside_tolerance(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        r = t.record_result(
            exp.id, "latency_p99", baseline_value=100.0, observed_value=150.0, tolerance_pct=10.0
        )
        assert r.within_tolerance is False
        assert r.impact_pct == pytest.approx(50.0, abs=0.01)

    def test_record_not_found(self):
        t = _tracker()
        with pytest.raises(ValueError, match="Experiment not found"):
            t.record_result("nonexistent", "cpu", 50.0, 60.0)

    def test_impact_pct_calculation(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.RESOURCE_STRESS, "db")
        r = t.record_result(exp.id, "throughput", baseline_value=200.0, observed_value=150.0)
        # abs(150-200)/200 * 100 = 25%
        assert r.impact_pct == pytest.approx(25.0, abs=0.01)

    def test_impact_pct_zero_baseline(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.FAULT_INJECTION, "cache")
        r = t.record_result(exp.id, "errors", baseline_value=0.0, observed_value=10.0)
        assert r.impact_pct == 0.0
        assert r.within_tolerance is True


# ---------------------------------------------------------------------------
# list_experiments
# ---------------------------------------------------------------------------


class TestListExperiments:
    def test_list_all(self):
        t = _tracker()
        t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        assert len(t.list_experiments()) == 2

    def test_list_by_status(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        t.start_experiment(exp.id)
        results = t.list_experiments(status=ExperimentStatus.RUNNING)
        assert len(results) == 1
        assert results[0].id == exp.id

    def test_list_by_service(self):
        t = _tracker()
        t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        results = t.list_experiments(target_service="api")
        assert len(results) == 1
        assert results[0].target_service == "api"

    def test_list_empty(self):
        t = _tracker()
        assert t.list_experiments() == []


# ---------------------------------------------------------------------------
# get_results
# ---------------------------------------------------------------------------


class TestGetResults:
    def test_returns_results_for_experiment(self):
        t = _tracker()
        e1 = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        e2 = t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        t.record_result(e1.id, "latency", 100.0, 110.0)
        t.record_result(e1.id, "errors", 0.0, 5.0)
        t.record_result(e2.id, "throughput", 1000.0, 800.0)
        results = t.get_results(e1.id)
        assert len(results) == 2
        assert all(r.experiment_id == e1.id for r in results)
        assert len(t.get_results(e2.id)) == 1


# ---------------------------------------------------------------------------
# delete_experiment
# ---------------------------------------------------------------------------


class TestDeleteExperiment:
    def test_delete_existing(self):
        t = _tracker()
        exp = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        assert t.delete_experiment(exp.id) is True
        assert t.get_experiment(exp.id) is None

    def test_delete_nonexistent(self):
        t = _tracker()
        assert t.delete_experiment("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        t = _tracker()
        stats = t.get_stats()
        assert stats["total_experiments"] == 0
        assert stats["by_status"] == {}
        assert stats["steady_state_success_rate"] == 0.0
        assert stats["total_results"] == 0
        assert stats["avg_impact_pct"] == 0.0

    def test_stats_populated(self):
        t = _tracker()
        e1 = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        t.start_experiment(e1.id)
        t.complete_experiment(e1.id, steady_state_met=True)
        t.record_result(e1.id, "latency", 100.0, 110.0)
        stats = t.get_stats()
        assert stats["total_experiments"] == 2
        assert stats["total_results"] == 1
        assert ExperimentStatus.COMPLETED in stats["by_status"]
        assert ExperimentStatus.PLANNED in stats["by_status"]

    def test_steady_state_rate(self):
        t = _tracker()
        e1 = t.create_experiment("e1", ExperimentType.LATENCY_INJECTION, "web")
        e2 = t.create_experiment("e2", ExperimentType.FAULT_INJECTION, "api")
        t.start_experiment(e1.id)
        t.complete_experiment(e1.id, steady_state_met=True)
        t.start_experiment(e2.id)
        t.complete_experiment(e2.id, steady_state_met=False)
        stats = t.get_stats()
        assert stats["steady_state_success_rate"] == pytest.approx(50.0, abs=0.1)
