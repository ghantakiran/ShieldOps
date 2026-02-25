"""Tests for shieldops.changes.rollback_advisor — DeploymentRollbackAdvisor."""

from __future__ import annotations

from shieldops.changes.rollback_advisor import (
    DeploymentRollbackAdvisor,
    HealthSignal,
    RollbackAction,
    RollbackAssessment,
    RollbackDecision,
    RollbackReport,
    RollbackStrategy,
)


def _engine(**kw) -> DeploymentRollbackAdvisor:
    return DeploymentRollbackAdvisor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RollbackDecision (5)
    def test_decision_proceed(self):
        assert RollbackDecision.PROCEED == "proceed"

    def test_decision_monitor(self):
        assert RollbackDecision.MONITOR == "monitor"

    def test_decision_prepare_rollback(self):
        assert RollbackDecision.PREPARE_ROLLBACK == "prepare_rollback"

    def test_decision_rollback_now(self):
        assert RollbackDecision.ROLLBACK_NOW == "rollback_now"

    def test_decision_emergency_rollback(self):
        assert RollbackDecision.EMERGENCY_ROLLBACK == "emergency_rollback"

    # HealthSignal (5)
    def test_signal_error_rate_spike(self):
        assert HealthSignal.ERROR_RATE_SPIKE == "error_rate_spike"

    def test_signal_latency_increase(self):
        assert HealthSignal.LATENCY_INCREASE == "latency_increase"

    def test_signal_crash_loop(self):
        assert HealthSignal.CRASH_LOOP == "crash_loop"

    def test_signal_resource_exhaustion(self):
        assert HealthSignal.RESOURCE_EXHAUSTION == "resource_exhaustion"

    def test_signal_dependency_failure(self):
        assert HealthSignal.DEPENDENCY_FAILURE == "dependency_failure"

    # RollbackStrategy (5)
    def test_strategy_full_rollback(self):
        assert RollbackStrategy.FULL_ROLLBACK == "full_rollback"

    def test_strategy_partial_rollback(self):
        assert RollbackStrategy.PARTIAL_ROLLBACK == "partial_rollback"

    def test_strategy_feature_flag_disable(self):
        assert RollbackStrategy.FEATURE_FLAG_DISABLE == "feature_flag_disable"

    def test_strategy_traffic_shift(self):
        assert RollbackStrategy.TRAFFIC_SHIFT == "traffic_shift"

    def test_strategy_manual_intervention(self):
        assert RollbackStrategy.MANUAL_INTERVENTION == "manual_intervention"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rollback_assessment_defaults(self):
        a = RollbackAssessment()
        assert a.id
        assert a.deployment_id == ""
        assert a.service_name == ""
        assert a.decision == RollbackDecision.PROCEED
        assert a.confidence == 0.0
        assert a.signals == []
        assert a.strategy == RollbackStrategy.FULL_ROLLBACK
        assert a.blast_radius_pct == 0.0
        assert a.assessed_at > 0
        assert a.created_at > 0

    def test_rollback_action_defaults(self):
        a = RollbackAction()
        assert a.id
        assert a.assessment_id == ""
        assert a.strategy == RollbackStrategy.FULL_ROLLBACK
        assert a.executed_by == ""
        assert a.success is False
        assert a.duration_seconds == 0
        assert a.executed_at > 0
        assert a.created_at > 0

    def test_rollback_report_defaults(self):
        r = RollbackReport()
        assert r.total_assessments == 0
        assert r.total_rollbacks == 0
        assert r.rollback_rate_pct == 0.0
        assert r.avg_confidence == 0.0
        assert r.by_decision == {}
        assert r.by_signal == {}
        assert r.by_strategy == {}
        assert r.slow_rollbacks == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# create_assessment
# ---------------------------------------------------------------------------


class TestCreateAssessment:
    def test_basic_create(self):
        eng = _engine()
        a = eng.create_assessment(
            deployment_id="deploy-1",
            service_name="api-gateway",
            signals=[HealthSignal.ERROR_RATE_SPIKE],
            blast_radius_pct=25.0,
        )
        assert a.deployment_id == "deploy-1"
        assert a.service_name == "api-gateway"
        assert len(a.signals) == 1
        assert a.blast_radius_pct == 25.0

    def test_eviction_at_max(self):
        eng = _engine(max_assessments=3)
        for i in range(5):
            eng.create_assessment(
                deployment_id=f"d-{i}",
                service_name=f"svc-{i}",
            )
        assert len(eng._items) == 3

    def test_no_signals(self):
        eng = _engine()
        a = eng.create_assessment(
            deployment_id="d-1",
            service_name="svc-1",
        )
        assert a.signals == []


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        a = eng.create_assessment(
            deployment_id="d-1",
            service_name="svc-1",
        )
        result = eng.get_assessment(a.id)
        assert result is not None
        assert result.deployment_id == "d-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.create_assessment("d-1", "svc-a")
        eng.create_assessment("d-2", "svc-b")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_assessment("d-1", "svc-a")
        eng.create_assessment("d-2", "svc-b")
        results = eng.list_assessments(
            service_name="svc-a",
        )
        assert len(results) == 1

    def test_filter_by_decision(self):
        eng = _engine()
        a1 = eng.create_assessment(
            "d-1",
            "svc-a",
            signals=[
                HealthSignal.CRASH_LOOP,
                HealthSignal.ERROR_RATE_SPIKE,
                HealthSignal.LATENCY_INCREASE,
            ],
        )
        eng.create_assessment("d-2", "svc-b")
        eng.evaluate_rollback_need(a1.id)
        results = eng.list_assessments(
            decision=RollbackDecision.EMERGENCY_ROLLBACK,
        )
        assert len(results) == 1


# ---------------------------------------------------------------------------
# evaluate_rollback_need
# ---------------------------------------------------------------------------


class TestEvaluateRollbackNeed:
    def test_emergency_with_crash_loop(self):
        eng = _engine()
        a = eng.create_assessment(
            "d-1",
            "svc-1",
            signals=[HealthSignal.CRASH_LOOP],
        )
        result = eng.evaluate_rollback_need(a.id)
        assert result is not None
        assert result.decision == (RollbackDecision.EMERGENCY_ROLLBACK)
        assert result.confidence > 0.7

    def test_rollback_now_two_signals(self):
        eng = _engine()
        a = eng.create_assessment(
            "d-1",
            "svc-1",
            signals=[
                HealthSignal.ERROR_RATE_SPIKE,
                HealthSignal.LATENCY_INCREASE,
            ],
        )
        result = eng.evaluate_rollback_need(a.id)
        assert result is not None
        assert result.decision == (RollbackDecision.ROLLBACK_NOW)

    def test_monitor_one_signal(self):
        eng = _engine()
        a = eng.create_assessment(
            "d-1",
            "svc-1",
            signals=[HealthSignal.LATENCY_INCREASE],
        )
        result = eng.evaluate_rollback_need(a.id)
        assert result is not None
        assert result.decision == RollbackDecision.MONITOR

    def test_proceed_no_signals(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        result = eng.evaluate_rollback_need(a.id)
        assert result is not None
        assert result.decision == RollbackDecision.PROCEED
        assert result.confidence == 0.95

    def test_not_found(self):
        eng = _engine()
        assert eng.evaluate_rollback_need("bad") is None


# ---------------------------------------------------------------------------
# execute_rollback
# ---------------------------------------------------------------------------


class TestExecuteRollback:
    def test_successful_execution(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        action = eng.execute_rollback(
            a.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        assert action is not None
        assert action.assessment_id == a.id
        assert action.strategy == (RollbackStrategy.FULL_ROLLBACK)
        assert action.executed_by == "alice"
        assert action.success is True
        assert action.duration_seconds == 120

    def test_feature_flag_fast(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        action = eng.execute_rollback(
            a.id,
            RollbackStrategy.FEATURE_FLAG_DISABLE,
            "bob",
        )
        assert action is not None
        assert action.duration_seconds == 10

    def test_not_found(self):
        eng = _engine()
        assert (
            eng.execute_rollback(
                "bad",
                RollbackStrategy.FULL_ROLLBACK,
                "alice",
            )
            is None
        )


# ---------------------------------------------------------------------------
# calculate_rollback_success_rate
# ---------------------------------------------------------------------------


class TestCalculateRollbackSuccessRate:
    def test_no_actions(self):
        eng = _engine()
        assert eng.calculate_rollback_success_rate() == 0.0

    def test_all_successful(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        eng.execute_rollback(
            a.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        assert eng.calculate_rollback_success_rate() == 100.0


# ---------------------------------------------------------------------------
# identify_rollback_patterns
# ---------------------------------------------------------------------------


class TestIdentifyRollbackPatterns:
    def test_detects_recurring_service(self):
        eng = _engine()
        for i in range(3):
            a = eng.create_assessment(
                f"d-{i}",
                "flaky-svc",
                signals=[HealthSignal.CRASH_LOOP],
            )
            eng.evaluate_rollback_need(a.id)
        patterns = eng.identify_rollback_patterns()
        assert len(patterns) == 1
        assert patterns[0]["service_name"] == "flaky-svc"
        assert patterns[0]["rollback_count"] == 3

    def test_empty_patterns(self):
        eng = _engine()
        assert eng.identify_rollback_patterns() == []


# ---------------------------------------------------------------------------
# estimate_rollback_time
# ---------------------------------------------------------------------------


class TestEstimateRollbackTime:
    def test_with_history(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "api")
        eng.execute_rollback(
            a.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        est = eng.estimate_rollback_time("api")
        assert est["service_name"] == "api"
        assert est["avg_duration_seconds"] > 0
        assert est["sample_count"] == 1

    def test_no_history(self):
        eng = _engine()
        est = eng.estimate_rollback_time("unknown")
        assert est["avg_duration_seconds"] == 0
        assert est["sample_count"] == 0


# ---------------------------------------------------------------------------
# generate_rollback_report
# ---------------------------------------------------------------------------


class TestGenerateRollbackReport:
    def test_basic_report(self):
        eng = _engine()
        a1 = eng.create_assessment(
            "d-1",
            "svc-1",
            signals=[
                HealthSignal.CRASH_LOOP,
                HealthSignal.ERROR_RATE_SPIKE,
                HealthSignal.LATENCY_INCREASE,
            ],
        )
        a2 = eng.create_assessment("d-2", "svc-2")
        eng.evaluate_rollback_need(a1.id)
        eng.evaluate_rollback_need(a2.id)
        eng.execute_rollback(
            a1.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        report = eng.generate_rollback_report()
        assert report.total_assessments == 2
        assert report.total_rollbacks == 1
        assert report.avg_confidence > 0
        assert len(report.by_decision) > 0
        assert len(report.by_signal) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_rollback_report()
        assert report.total_assessments == 0
        assert report.total_rollbacks == 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        eng.execute_rollback(
            a.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        assert len(eng._items) == 1
        assert len(eng._actions) == 1
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._actions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_actions"] == 0
        assert stats["decision_distribution"] == {}
        assert stats["service_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        a = eng.create_assessment("d-1", "svc-1")
        eng.execute_rollback(
            a.id,
            RollbackStrategy.FULL_ROLLBACK,
            "alice",
        )
        stats = eng.get_stats()
        assert stats["total_assessments"] == 1
        assert stats["total_actions"] == 1
        assert stats["max_assessments"] == 100000
        assert stats["auto_rollback_confidence"] == 0.9
