"""Tests for shieldops.operations.self_healing — SelfHealingOrchestrator."""

from __future__ import annotations

from shieldops.operations.self_healing import (
    HealingAction,
    HealingOutcome,
    HealingPolicy,
    HealingRecord,
    HealingTrigger,
    SelfHealingOrchestrator,
    SelfHealingReport,
)


def _engine(**kw) -> SelfHealingOrchestrator:
    return SelfHealingOrchestrator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # HealingAction (5)
    def test_action_restart(self):
        assert HealingAction.RESTART_SERVICE == "restart_service"

    def test_action_scale_out(self):
        assert HealingAction.SCALE_OUT == "scale_out"

    def test_action_clear_cache(self):
        assert HealingAction.CLEAR_CACHE == "clear_cache"

    def test_action_rotate_creds(self):
        assert HealingAction.ROTATE_CREDENTIALS == "rotate_credentials"

    def test_action_failover(self):
        assert HealingAction.FAILOVER == "failover"

    # HealingOutcome (5)
    def test_outcome_success(self):
        assert HealingOutcome.SUCCESS == "success"

    def test_outcome_partial(self):
        assert HealingOutcome.PARTIAL == "partial"

    def test_outcome_failed(self):
        assert HealingOutcome.FAILED == "failed"

    def test_outcome_rollback(self):
        assert HealingOutcome.ROLLBACK == "rollback"

    def test_outcome_timeout(self):
        assert HealingOutcome.TIMEOUT == "timeout"

    # HealingTrigger (5)
    def test_trigger_alert(self):
        assert HealingTrigger.ALERT == "alert"

    def test_trigger_threshold(self):
        assert HealingTrigger.THRESHOLD == "threshold"

    def test_trigger_anomaly(self):
        assert HealingTrigger.ANOMALY == "anomaly"

    def test_trigger_schedule(self):
        assert HealingTrigger.SCHEDULE == "schedule"

    def test_trigger_manual(self):
        assert HealingTrigger.MANUAL == "manual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_healing_record_defaults(self):
        r = HealingRecord()
        assert r.id
        assert r.service_name == ""
        assert r.action == HealingAction.RESTART_SERVICE
        assert r.outcome == HealingOutcome.SUCCESS
        assert r.trigger == HealingTrigger.ALERT
        assert r.duration_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_healing_policy_defaults(self):
        r = HealingPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.action == HealingAction.RESTART_SERVICE
        assert r.trigger == HealingTrigger.ALERT
        assert r.max_retries == 3
        assert r.cooldown_seconds == 300.0
        assert r.created_at > 0

    def test_self_healing_report_defaults(self):
        r = SelfHealingReport()
        assert r.total_healings == 0
        assert r.total_policies == 0
        assert r.success_rate_pct == 0.0
        assert r.by_action == {}
        assert r.by_outcome == {}
        assert r.repeat_failure_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_healing
# -------------------------------------------------------------------


class TestRecordHealing:
    def test_basic(self):
        eng = _engine()
        r = eng.record_healing(
            "svc-a",
            action=HealingAction.RESTART_SERVICE,
            outcome=HealingOutcome.SUCCESS,
        )
        assert r.service_name == "svc-a"
        assert r.action == HealingAction.RESTART_SERVICE

    def test_with_trigger(self):
        eng = _engine()
        r = eng.record_healing("svc-b", trigger=HealingTrigger.ANOMALY)
        assert r.trigger == HealingTrigger.ANOMALY

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_healing(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_healing
# -------------------------------------------------------------------


class TestGetHealing:
    def test_found(self):
        eng = _engine()
        r = eng.record_healing("svc-a")
        assert eng.get_healing(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_healing("nonexistent") is None


# -------------------------------------------------------------------
# list_healings
# -------------------------------------------------------------------


class TestListHealings:
    def test_list_all(self):
        eng = _engine()
        eng.record_healing("svc-a")
        eng.record_healing("svc-b")
        assert len(eng.list_healings()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_healing("svc-a")
        eng.record_healing("svc-b")
        results = eng.list_healings(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_healing("svc-a", action=HealingAction.FAILOVER)
        eng.record_healing("svc-b", action=HealingAction.SCALE_OUT)
        results = eng.list_healings(action=HealingAction.FAILOVER)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "restart-on-alert",
            action=HealingAction.RESTART_SERVICE,
            trigger=HealingTrigger.ALERT,
            max_retries=5,
            cooldown_seconds=600.0,
        )
        assert p.policy_name == "restart-on-alert"
        assert p.max_retries == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_healing_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeHealingEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_healing("svc-a", outcome=HealingOutcome.SUCCESS)
        eng.record_healing("svc-a", outcome=HealingOutcome.FAILED)
        result = eng.analyze_healing_effectiveness("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_healings"] == 2
        assert result["success_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_healing_effectiveness("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_repeat_failures
# -------------------------------------------------------------------


class TestIdentifyRepeatFailures:
    def test_with_failures(self):
        eng = _engine()
        eng.record_healing("svc-a", outcome=HealingOutcome.FAILED)
        eng.record_healing("svc-a", outcome=HealingOutcome.FAILED)
        eng.record_healing("svc-b", outcome=HealingOutcome.SUCCESS)
        results = eng.identify_repeat_failures()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_repeat_failures() == []


# -------------------------------------------------------------------
# rank_by_healing_frequency
# -------------------------------------------------------------------


class TestRankByHealingFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.record_healing("svc-a")
        eng.record_healing("svc-a")
        eng.record_healing("svc-b")
        results = eng.rank_by_healing_frequency()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["healing_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_healing_frequency() == []


# -------------------------------------------------------------------
# detect_healing_loops
# -------------------------------------------------------------------


class TestDetectHealingLoops:
    def test_with_loops(self):
        eng = _engine()
        for _ in range(5):
            eng.record_healing("svc-a", outcome=HealingOutcome.FAILED)
        eng.record_healing("svc-b", outcome=HealingOutcome.SUCCESS)
        results = eng.detect_healing_loops()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["loop_detected"] is True

    def test_no_loops(self):
        eng = _engine()
        eng.record_healing("svc-a", outcome=HealingOutcome.FAILED)
        assert eng.detect_healing_loops() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_healing("svc-a", outcome=HealingOutcome.SUCCESS)
        eng.record_healing("svc-b", outcome=HealingOutcome.FAILED)
        eng.record_healing("svc-b", outcome=HealingOutcome.FAILED)
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_healings == 3
        assert report.total_policies == 1
        assert report.by_action != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_healings == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_healing("svc-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_healings"] == 0
        assert stats["total_policies"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_healing("svc-a", action=HealingAction.RESTART_SERVICE)
        eng.record_healing("svc-b", action=HealingAction.FAILOVER)
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_healings"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
