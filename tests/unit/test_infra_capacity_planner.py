"""Tests for shieldops.analytics.infra_capacity_planner — InfraCapacityPlanner."""

from __future__ import annotations

from shieldops.analytics.infra_capacity_planner import (
    CapacityAction,
    CapacityPlan,
    CapacityPlannerReport,
    InfraCapacityPlanner,
    PlanningHorizon,
    PlanningRule,
    ResourceType,
)


def _engine(**kw) -> InfraCapacityPlanner:
    return InfraCapacityPlanner(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResourceType (5)
    def test_resource_compute(self):
        assert ResourceType.COMPUTE == "compute"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_gpu(self):
        assert ResourceType.GPU == "gpu"

    # PlanningHorizon (5)
    def test_horizon_weekly(self):
        assert PlanningHorizon.WEEKLY == "weekly"

    def test_horizon_monthly(self):
        assert PlanningHorizon.MONTHLY == "monthly"

    def test_horizon_quarterly(self):
        assert PlanningHorizon.QUARTERLY == "quarterly"

    def test_horizon_semi_annual(self):
        assert PlanningHorizon.SEMI_ANNUAL == "semi_annual"

    def test_horizon_annual(self):
        assert PlanningHorizon.ANNUAL == "annual"

    # CapacityAction (5)
    def test_action_provision(self):
        assert CapacityAction.PROVISION == "provision"

    def test_action_decommission(self):
        assert CapacityAction.DECOMMISSION == "decommission"

    def test_action_resize(self):
        assert CapacityAction.RESIZE == "resize"

    def test_action_migrate(self):
        assert CapacityAction.MIGRATE == "migrate"

    def test_action_maintain(self):
        assert CapacityAction.MAINTAIN == "maintain"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_capacity_plan_defaults(self):
        r = CapacityPlan()
        assert r.id
        assert r.service_name == ""
        assert r.resource == ResourceType.COMPUTE
        assert r.horizon == PlanningHorizon.MONTHLY
        assert r.action == CapacityAction.MAINTAIN
        assert r.utilization_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_planning_rule_defaults(self):
        r = PlanningRule()
        assert r.id
        assert r.rule_name == ""
        assert r.resource == ResourceType.COMPUTE
        assert r.horizon == PlanningHorizon.MONTHLY
        assert r.target_utilization_pct == 70.0
        assert r.headroom_pct == 20.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CapacityPlannerReport()
        assert r.total_plans == 0
        assert r.total_rules == 0
        assert r.optimal_rate_pct == 0.0
        assert r.by_resource == {}
        assert r.by_action == {}
        assert r.over_provisioned_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_plan
# -------------------------------------------------------------------


class TestRecordPlan:
    def test_basic(self):
        eng = _engine()
        r = eng.record_plan(
            "svc-a",
            resource=ResourceType.GPU,
            action=CapacityAction.PROVISION,
        )
        assert r.service_name == "svc-a"
        assert r.resource == ResourceType.GPU

    def test_with_utilization(self):
        eng = _engine()
        r = eng.record_plan("svc-b", utilization_pct=85.0)
        assert r.utilization_pct == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_plan(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_plan
# -------------------------------------------------------------------


class TestGetPlan:
    def test_found(self):
        eng = _engine()
        r = eng.record_plan("svc-a")
        assert eng.get_plan(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_plan("nonexistent") is None


# -------------------------------------------------------------------
# list_plans
# -------------------------------------------------------------------


class TestListPlans:
    def test_list_all(self):
        eng = _engine()
        eng.record_plan("svc-a")
        eng.record_plan("svc-b")
        assert len(eng.list_plans()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_plan("svc-a")
        eng.record_plan("svc-b")
        results = eng.list_plans(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_resource(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            resource=ResourceType.GPU,
        )
        eng.record_plan(
            "svc-b",
            resource=ResourceType.COMPUTE,
        )
        results = eng.list_plans(resource=ResourceType.GPU)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            "gpu-utilization",
            resource=ResourceType.GPU,
            horizon=PlanningHorizon.QUARTERLY,
            target_utilization_pct=60.0,
            headroom_pct=30.0,
        )
        assert r.rule_name == "gpu-utilization"
        assert r.target_utilization_pct == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_capacity_efficiency
# -------------------------------------------------------------------


class TestAnalyzeCapacityEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            action=CapacityAction.MAINTAIN,
            utilization_pct=60.0,
        )
        eng.record_plan(
            "svc-a",
            action=CapacityAction.PROVISION,
            utilization_pct=80.0,
        )
        result = eng.analyze_capacity_efficiency("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["plan_count"] == 2
        assert result["optimal_count"] == 1
        assert result["optimal_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_capacity_efficiency("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_over_provisioned
# -------------------------------------------------------------------


class TestIdentifyOverProvisioned:
    def test_with_over_provisioned(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            action=CapacityAction.DECOMMISSION,
        )
        eng.record_plan(
            "svc-a",
            action=CapacityAction.RESIZE,
        )
        eng.record_plan(
            "svc-b",
            action=CapacityAction.MAINTAIN,
        )
        results = eng.identify_over_provisioned()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_over_provisioned() == []


# -------------------------------------------------------------------
# rank_by_utilization
# -------------------------------------------------------------------


class TestRankByUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_plan("svc-a", utilization_pct=90.0)
        eng.record_plan("svc-a", utilization_pct=70.0)
        eng.record_plan("svc-b", utilization_pct=30.0)
        results = eng.rank_by_utilization()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_utilization"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# -------------------------------------------------------------------
# detect_capacity_risks
# -------------------------------------------------------------------


class TestDetectCapacityRisks:
    def test_with_risks(self):
        eng = _engine()
        for _ in range(5):
            eng.record_plan(
                "svc-a",
                action=CapacityAction.PROVISION,
            )
        eng.record_plan(
            "svc-b",
            action=CapacityAction.MAINTAIN,
        )
        results = eng.detect_capacity_risks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["risk_detected"] is True

    def test_no_risks(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            action=CapacityAction.PROVISION,
        )
        assert eng.detect_capacity_risks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            action=CapacityAction.MAINTAIN,
        )
        eng.record_plan(
            "svc-b",
            action=CapacityAction.DECOMMISSION,
        )
        eng.record_plan(
            "svc-b",
            action=CapacityAction.RESIZE,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_plans == 3
        assert report.total_rules == 1
        assert report.by_resource != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_plans == 0
        assert "optimal" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_plan("svc-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_plans"] == 0
        assert stats["total_rules"] == 0
        assert stats["resource_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_plan(
            "svc-a",
            resource=ResourceType.GPU,
        )
        eng.record_plan(
            "svc-b",
            resource=ResourceType.COMPUTE,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_plans"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
