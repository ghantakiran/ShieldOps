"""Tests for shieldops.operations.burst_manager — CapacityBurstManager."""

from __future__ import annotations

from shieldops.operations.burst_manager import (
    BurstAction,
    BurstManagerReport,
    BurstPolicy,
    BurstRecord,
    BurstStatus,
    BurstType,
    CapacityBurstManager,
)


def _engine(**kw) -> CapacityBurstManager:
    return CapacityBurstManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BurstType (5)
    def test_type_traffic_spike(self):
        assert BurstType.TRAFFIC_SPIKE == "traffic_spike"

    def test_type_seasonal_peak(self):
        assert BurstType.SEASONAL_PEAK == "seasonal_peak"

    def test_type_event_driven(self):
        assert BurstType.EVENT_DRIVEN == "event_driven"

    def test_type_failure_recovery(self):
        assert BurstType.FAILURE_RECOVERY == "failure_recovery"

    def test_type_scheduled_batch(self):
        assert BurstType.SCHEDULED_BATCH == "scheduled_batch"

    # BurstAction (5)
    def test_action_auto_scale(self):
        assert BurstAction.AUTO_SCALE == "auto_scale"

    def test_action_pre_provision(self):
        assert BurstAction.PRE_PROVISION == "pre_provision"

    def test_action_queue_traffic(self):
        assert BurstAction.QUEUE_TRAFFIC == "queue_traffic"

    def test_action_shed_load(self):
        assert BurstAction.SHED_LOAD == "shed_load"

    def test_action_failover(self):
        assert BurstAction.FAILOVER == "failover"

    # BurstStatus (5)
    def test_status_detected(self):
        assert BurstStatus.DETECTED == "detected"

    def test_status_mitigating(self):
        assert BurstStatus.MITIGATING == "mitigating"

    def test_status_resolved(self):
        assert BurstStatus.RESOLVED == "resolved"

    def test_status_escalated(self):
        assert BurstStatus.ESCALATED == "escalated"

    def test_status_budget_exceeded(self):
        assert BurstStatus.BUDGET_EXCEEDED == "budget_exceeded"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_burst_record_defaults(self):
        r = BurstRecord()
        assert r.id
        assert r.service_name == ""
        assert r.burst_type == BurstType.TRAFFIC_SPIKE
        assert r.action == BurstAction.AUTO_SCALE
        assert r.status == BurstStatus.DETECTED
        assert r.cost_impact == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_burst_policy_defaults(self):
        r = BurstPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.burst_type == BurstType.TRAFFIC_SPIKE
        assert r.action == BurstAction.AUTO_SCALE
        assert r.max_scale_factor == 3
        assert r.budget_limit == 1000.0
        assert r.created_at > 0

    def test_burst_manager_report_defaults(self):
        r = BurstManagerReport()
        assert r.total_bursts == 0
        assert r.total_policies == 0
        assert r.resolution_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.budget_exceeded_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_burst
# -------------------------------------------------------------------


class TestRecordBurst:
    def test_basic(self):
        eng = _engine()
        r = eng.record_burst(
            "svc-a",
            burst_type=BurstType.TRAFFIC_SPIKE,
            action=BurstAction.AUTO_SCALE,
        )
        assert r.service_name == "svc-a"
        assert r.burst_type == BurstType.TRAFFIC_SPIKE

    def test_with_status(self):
        eng = _engine()
        r = eng.record_burst(
            "svc-b",
            status=BurstStatus.RESOLVED,
        )
        assert r.status == BurstStatus.RESOLVED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_burst(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_burst
# -------------------------------------------------------------------


class TestGetBurst:
    def test_found(self):
        eng = _engine()
        r = eng.record_burst("svc-a")
        assert eng.get_burst(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_burst("nonexistent") is None


# -------------------------------------------------------------------
# list_bursts
# -------------------------------------------------------------------


class TestListBursts:
    def test_list_all(self):
        eng = _engine()
        eng.record_burst("svc-a")
        eng.record_burst("svc-b")
        assert len(eng.list_bursts()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_burst("svc-a")
        eng.record_burst("svc-b")
        results = eng.list_bursts(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            burst_type=BurstType.SEASONAL_PEAK,
        )
        eng.record_burst(
            "svc-b",
            burst_type=BurstType.EVENT_DRIVEN,
        )
        results = eng.list_bursts(
            burst_type=BurstType.SEASONAL_PEAK,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "scale-on-spike",
            burst_type=BurstType.TRAFFIC_SPIKE,
            action=BurstAction.AUTO_SCALE,
            max_scale_factor=5,
            budget_limit=2000.0,
        )
        assert p.policy_name == "scale-on-spike"
        assert p.max_scale_factor == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_burst_patterns
# -------------------------------------------------------------------


class TestAnalyzeBurstPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            status=BurstStatus.RESOLVED,
            cost_impact=100.0,
        )
        eng.record_burst(
            "svc-a",
            status=BurstStatus.DETECTED,
            cost_impact=200.0,
        )
        result = eng.analyze_burst_patterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["burst_count"] == 2
        assert result["resolution_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_burst_patterns("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_budget_overruns
# -------------------------------------------------------------------


class TestIdentifyBudgetOverruns:
    def test_with_overruns(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            status=BurstStatus.BUDGET_EXCEEDED,
        )
        eng.record_burst(
            "svc-a",
            status=BurstStatus.BUDGET_EXCEEDED,
        )
        eng.record_burst(
            "svc-b",
            status=BurstStatus.RESOLVED,
        )
        results = eng.identify_budget_overruns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_budget_overruns() == []


# -------------------------------------------------------------------
# rank_by_cost_impact
# -------------------------------------------------------------------


class TestRankByCostImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_burst("svc-a", cost_impact=500.0)
        eng.record_burst("svc-a", cost_impact=300.0)
        eng.record_burst("svc-b", cost_impact=100.0)
        results = eng.rank_by_cost_impact()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_cost_impact"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_impact() == []


# -------------------------------------------------------------------
# detect_recurring_bursts
# -------------------------------------------------------------------


class TestDetectRecurringBursts:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_burst(
                "svc-a",
                status=BurstStatus.DETECTED,
            )
        eng.record_burst(
            "svc-b",
            status=BurstStatus.RESOLVED,
        )
        results = eng.detect_recurring_bursts()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recurring_detected"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            status=BurstStatus.DETECTED,
        )
        assert eng.detect_recurring_bursts() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            status=BurstStatus.RESOLVED,
        )
        eng.record_burst(
            "svc-b",
            status=BurstStatus.BUDGET_EXCEEDED,
        )
        eng.record_burst(
            "svc-b",
            status=BurstStatus.BUDGET_EXCEEDED,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_bursts == 3
        assert report.total_policies == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_bursts == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_burst("svc-a")
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
        assert stats["total_bursts"] == 0
        assert stats["total_policies"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_burst(
            "svc-a",
            burst_type=BurstType.TRAFFIC_SPIKE,
        )
        eng.record_burst(
            "svc-b",
            burst_type=BurstType.SEASONAL_PEAK,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_bursts"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
