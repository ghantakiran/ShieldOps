"""Tests for shieldops.topology.dependency_update_planner — DependencyUpdatePlanner."""

from __future__ import annotations

from shieldops.topology.dependency_update_planner import (
    DependencyUpdate,
    DependencyUpdatePlanner,
    UpdatePlan,
    UpdatePlannerReport,
    UpdateRisk,
    UpdateStatus,
    UpdateStrategy,
)


def _engine(**kw) -> DependencyUpdatePlanner:
    return DependencyUpdatePlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # UpdateRisk (5)
    def test_risk_trivial(self):
        assert UpdateRisk.TRIVIAL == "trivial"

    def test_risk_low(self):
        assert UpdateRisk.LOW == "low"

    def test_risk_moderate(self):
        assert UpdateRisk.MODERATE == "moderate"

    def test_risk_high(self):
        assert UpdateRisk.HIGH == "high"

    def test_risk_breaking(self):
        assert UpdateRisk.BREAKING == "breaking"

    # UpdateStrategy (5)
    def test_strategy_immediate(self):
        assert UpdateStrategy.IMMEDIATE == "immediate"

    def test_strategy_staged(self):
        assert UpdateStrategy.STAGED == "staged"

    def test_strategy_canary(self):
        assert UpdateStrategy.CANARY == "canary"

    def test_strategy_blue_green(self):
        assert UpdateStrategy.BLUE_GREEN == "blue_green"

    def test_strategy_manual_review(self):
        assert UpdateStrategy.MANUAL_REVIEW == "manual_review"

    # UpdateStatus (5)
    def test_status_planned(self):
        assert UpdateStatus.PLANNED == "planned"

    def test_status_in_progress(self):
        assert UpdateStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert UpdateStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert UpdateStatus.FAILED == "failed"

    def test_status_skipped(self):
        assert UpdateStatus.SKIPPED == "skipped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_update_defaults(self):
        u = DependencyUpdate()
        assert u.id
        assert u.package_name == ""
        assert u.current_version == ""
        assert u.target_version == ""
        assert u.risk == UpdateRisk.LOW
        assert u.strategy == UpdateStrategy.IMMEDIATE
        assert u.status == UpdateStatus.PLANNED
        assert u.dependents == []
        assert u.test_coverage_pct == 0.0
        assert u.breaking_changes == []
        assert u.created_at > 0

    def test_update_plan_defaults(self):
        p = UpdatePlan()
        assert p.id
        assert p.name == ""
        assert p.updates == []
        assert p.total_risk_score == 0.0
        assert p.estimated_duration_hours == 0.0
        assert p.execution_order == []
        assert p.created_at > 0

    def test_update_planner_report_defaults(self):
        r = UpdatePlannerReport()
        assert r.total_updates == 0
        assert r.total_plans == 0
        assert r.avg_risk_score == 0.0
        assert r.by_risk == {}
        assert r.by_strategy == {}
        assert r.by_status == {}
        assert r.high_risk_updates == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_update
# ---------------------------------------------------------------------------


class TestRegisterUpdate:
    def test_basic_register(self):
        eng = _engine()
        upd = eng.register_update(
            package_name="requests",
            current_version="2.28.0",
            target_version="2.31.0",
            risk=UpdateRisk.MODERATE,
            strategy=UpdateStrategy.STAGED,
            dependents=["api-service", "auth-service"],
            test_coverage_pct=85.0,
            breaking_changes=["Dropped Python 3.7"],
        )
        assert upd.package_name == "requests"
        assert upd.current_version == "2.28.0"
        assert upd.target_version == "2.31.0"
        assert upd.risk == UpdateRisk.MODERATE
        assert upd.strategy == UpdateStrategy.STAGED
        assert upd.dependents == ["api-service", "auth-service"]
        assert upd.test_coverage_pct == 85.0
        assert upd.breaking_changes == ["Dropped Python 3.7"]

    def test_eviction_at_max(self):
        eng = _engine(max_updates=3)
        for i in range(5):
            eng.register_update(package_name=f"pkg-{i}")
        assert len(eng._items) == 3

    def test_defaults(self):
        eng = _engine()
        upd = eng.register_update(package_name="flask")
        assert upd.risk == UpdateRisk.LOW
        assert upd.strategy == UpdateStrategy.IMMEDIATE
        assert upd.dependents == []


# ---------------------------------------------------------------------------
# get_update
# ---------------------------------------------------------------------------


class TestGetUpdate:
    def test_found(self):
        eng = _engine()
        upd = eng.register_update(package_name="numpy")
        assert eng.get_update(upd.id) is not None
        assert eng.get_update(upd.id).package_name == "numpy"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_update("nonexistent") is None


# ---------------------------------------------------------------------------
# list_updates
# ---------------------------------------------------------------------------


class TestListUpdates:
    def test_list_all(self):
        eng = _engine()
        eng.register_update(package_name="a")
        eng.register_update(package_name="b")
        assert len(eng.list_updates()) == 2

    def test_filter_by_risk(self):
        eng = _engine()
        eng.register_update(package_name="a", risk=UpdateRisk.HIGH)
        eng.register_update(package_name="b", risk=UpdateRisk.LOW)
        results = eng.list_updates(risk=UpdateRisk.HIGH)
        assert len(results) == 1
        assert results[0].package_name == "a"

    def test_filter_by_status(self):
        eng = _engine()
        u1 = eng.register_update(package_name="a")
        eng.register_update(package_name="b")
        u1.status = UpdateStatus.COMPLETED
        results = eng.list_updates(status=UpdateStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].package_name == "a"

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_update(package_name=f"pkg-{i}")
        assert len(eng.list_updates(limit=3)) == 3


# ---------------------------------------------------------------------------
# create_plan
# ---------------------------------------------------------------------------


class TestCreatePlan:
    def test_basic_plan(self):
        eng = _engine()
        u1 = eng.register_update(
            package_name="a",
            risk=UpdateRisk.LOW,
            strategy=UpdateStrategy.IMMEDIATE,
        )
        u2 = eng.register_update(
            package_name="b",
            risk=UpdateRisk.HIGH,
            strategy=UpdateStrategy.CANARY,
        )
        plan = eng.create_plan("Q1 Updates", [u1.id, u2.id])
        assert plan.name == "Q1 Updates"
        assert len(plan.updates) == 2
        assert plan.total_risk_score > 0
        assert plan.estimated_duration_hours > 0

    def test_invalid_ids_skipped(self):
        eng = _engine()
        u1 = eng.register_update(package_name="a")
        plan = eng.create_plan("test", [u1.id, "bogus"])
        assert len(plan.updates) == 1

    def test_empty_plan(self):
        eng = _engine()
        plan = eng.create_plan("empty", [])
        assert len(plan.updates) == 0
        assert plan.total_risk_score == 0.0


# ---------------------------------------------------------------------------
# calculate_execution_order
# ---------------------------------------------------------------------------


class TestCalculateExecutionOrder:
    def test_order_by_risk(self):
        eng = _engine()
        u_high = eng.register_update(
            package_name="high",
            risk=UpdateRisk.HIGH,
        )
        u_low = eng.register_update(
            package_name="low",
            risk=UpdateRisk.TRIVIAL,
        )
        plan = eng.create_plan("test", [u_high.id, u_low.id])
        order = eng.calculate_execution_order(plan.id)
        assert len(order) == 2
        # Low risk should come first
        assert order[0] == u_low.id
        assert order[1] == u_high.id

    def test_nonexistent_plan(self):
        eng = _engine()
        assert eng.calculate_execution_order("bogus") == []


# ---------------------------------------------------------------------------
# assess_update_risk
# ---------------------------------------------------------------------------


class TestAssessUpdateRisk:
    def test_low_risk(self):
        eng = _engine()
        upd = eng.register_update(
            package_name="simple",
            risk=UpdateRisk.LOW,
            test_coverage_pct=90.0,
        )
        result = eng.assess_update_risk(upd.id)
        assert result["package_name"] == "simple"
        assert result["risk_score"] >= 1.0

    def test_high_risk_with_breaking(self):
        eng = _engine()
        upd = eng.register_update(
            package_name="risky",
            risk=UpdateRisk.HIGH,
            test_coverage_pct=20.0,
            breaking_changes=["API removed", "Signature changed"],
            dependents=["a", "b", "c", "d", "e", "f"],
        )
        result = eng.assess_update_risk(upd.id)
        assert result["risk_score"] >= 4.0
        assert len(result["factors"]) >= 2

    def test_nonexistent_update(self):
        eng = _engine()
        result = eng.assess_update_risk("bogus")
        assert result["risk_score"] == 0.0
        assert result["risk_level"] == "trivial"


# ---------------------------------------------------------------------------
# detect_breaking_chains
# ---------------------------------------------------------------------------


class TestDetectBreakingChains:
    def test_chain_detected(self):
        eng = _engine()
        eng.register_update(
            package_name="core-lib",
            breaking_changes=["Removed v1 API"],
        )
        eng.register_update(
            package_name="service-a",
            dependents=["core-lib"],
        )
        eng.register_update(
            package_name="service-b",
            dependents=["core-lib"],
        )
        chains = eng.detect_breaking_chains()
        assert len(chains) >= 1
        assert chains[0]["package_name"] == "core-lib"
        assert len(chains[0]["affected_packages"]) == 2

    def test_no_chains(self):
        eng = _engine()
        eng.register_update(package_name="safe-lib")
        chains = eng.detect_breaking_chains()
        assert len(chains) == 0


# ---------------------------------------------------------------------------
# estimate_plan_duration
# ---------------------------------------------------------------------------


class TestEstimatePlanDuration:
    def test_basic_duration(self):
        eng = _engine()
        u1 = eng.register_update(
            package_name="a",
            strategy=UpdateStrategy.IMMEDIATE,
        )
        u2 = eng.register_update(
            package_name="b",
            strategy=UpdateStrategy.CANARY,
        )
        plan = eng.create_plan("test", [u1.id, u2.id])
        hours = eng.estimate_plan_duration(plan.id)
        assert hours == 4.5  # 0.5 + 4.0

    def test_nonexistent_plan(self):
        eng = _engine()
        assert eng.estimate_plan_duration("bogus") == 0.0


# ---------------------------------------------------------------------------
# generate_planner_report
# ---------------------------------------------------------------------------


class TestGeneratePlannerReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_update(
            package_name="a",
            risk=UpdateRisk.HIGH,
            strategy=UpdateStrategy.CANARY,
        )
        eng.register_update(
            package_name="b",
            risk=UpdateRisk.LOW,
            strategy=UpdateStrategy.IMMEDIATE,
        )
        report = eng.generate_planner_report()
        assert isinstance(report, UpdatePlannerReport)
        assert report.total_updates == 2
        assert report.avg_risk_score > 0
        assert report.by_risk["high"] == 1
        assert report.by_risk["low"] == 1
        assert report.by_strategy["canary"] == 1
        assert report.by_status["planned"] == 2
        assert "a" in report.high_risk_updates

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_planner_report()
        assert report.total_updates == 0
        assert len(report.recommendations) >= 1

    def test_report_with_low_coverage(self):
        eng = _engine()
        eng.register_update(
            package_name="untested",
            test_coverage_pct=10.0,
        )
        report = eng.generate_planner_report()
        assert any("coverage" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        u1 = eng.register_update(package_name="a")
        eng.create_plan("p", [u1.id])
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._plans) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_updates"] == 0
        assert stats["total_plans"] == 0
        assert stats["unique_packages"] == 0
        assert stats["risk_levels"] == []
        assert stats["statuses"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_update(
            package_name="requests",
            risk=UpdateRisk.HIGH,
        )
        eng.register_update(
            package_name="flask",
            risk=UpdateRisk.LOW,
        )
        stats = eng.get_stats()
        assert stats["total_updates"] == 2
        assert stats["unique_packages"] == 2
        assert "high" in stats["risk_levels"]
        assert "low" in stats["risk_levels"]
        assert "planned" in stats["statuses"]
