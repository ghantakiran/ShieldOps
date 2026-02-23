"""Tests for shieldops.observability.dr_readiness — DisasterRecoveryReadinessTracker."""

from __future__ import annotations

import time

from shieldops.observability.dr_readiness import (
    DisasterRecoveryReadinessTracker,
    DrDrill,
    DrillStatus,
    ReadinessReport,
    ReadinessTier,
    RecoveryObjectiveType,
    RecoveryPlan,
)


def _engine(**kw) -> DisasterRecoveryReadinessTracker:
    return DisasterRecoveryReadinessTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_recovery_objective_rto(self):
        assert RecoveryObjectiveType.RTO == "rto"

    def test_recovery_objective_rpo(self):
        assert RecoveryObjectiveType.RPO == "rpo"

    def test_recovery_objective_mttr(self):
        assert RecoveryObjectiveType.MTTR == "mttr"

    def test_recovery_objective_wrt(self):
        assert RecoveryObjectiveType.WRT == "wrt"

    def test_drill_status_scheduled(self):
        assert DrillStatus.SCHEDULED == "scheduled"

    def test_drill_status_in_progress(self):
        assert DrillStatus.IN_PROGRESS == "in_progress"

    def test_drill_status_passed(self):
        assert DrillStatus.PASSED == "passed"

    def test_drill_status_failed(self):
        assert DrillStatus.FAILED == "failed"

    def test_drill_status_cancelled(self):
        assert DrillStatus.CANCELLED == "cancelled"

    def test_readiness_tier_platinum(self):
        assert ReadinessTier.PLATINUM == "platinum"

    def test_readiness_tier_gold(self):
        assert ReadinessTier.GOLD == "gold"

    def test_readiness_tier_silver(self):
        assert ReadinessTier.SILVER == "silver"

    def test_readiness_tier_bronze(self):
        assert ReadinessTier.BRONZE == "bronze"

    def test_readiness_tier_unrated(self):
        assert ReadinessTier.UNRATED == "unrated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_recovery_plan_defaults(self):
        plan = RecoveryPlan(service="db-primary")
        assert plan.id
        assert plan.service == "db-primary"
        assert plan.rto_minutes == 60
        assert plan.rpo_minutes == 30
        assert plan.tier == ReadinessTier.UNRATED
        assert plan.last_drill_at is None
        assert plan.created_at > 0

    def test_dr_drill_defaults(self):
        drill = DrDrill(plan_id="p-1")
        assert drill.id
        assert drill.plan_id == "p-1"
        assert drill.status == DrillStatus.SCHEDULED
        assert drill.completed_at is None
        assert drill.actual_rto_minutes is None

    def test_readiness_report_defaults(self):
        report = ReadinessReport(service="svc-a", plan_id="p-1")
        assert report.service == "svc-a"
        assert report.tier == ReadinessTier.UNRATED
        assert report.drill_count == 0
        assert report.score == 0.0


# ---------------------------------------------------------------------------
# register_plan
# ---------------------------------------------------------------------------


class TestRegisterPlan:
    def test_basic_register(self):
        eng = _engine()
        plan = eng.register_plan("db-primary")
        assert plan.service == "db-primary"
        assert plan.rto_minutes == 60
        assert eng.get_plan(plan.id) is not None

    def test_register_unique_ids(self):
        eng = _engine()
        p1 = eng.register_plan("svc-a")
        p2 = eng.register_plan("svc-b")
        assert p1.id != p2.id

    def test_register_with_custom_values(self):
        eng = _engine()
        plan = eng.register_plan("db", rto_minutes=15, rpo_minutes=5, owner="team-a")
        assert plan.rto_minutes == 15
        assert plan.rpo_minutes == 5
        assert plan.owner == "team-a"

    def test_evicts_at_max(self):
        eng = _engine(max_plans=2)
        p1 = eng.register_plan("svc-1")
        eng.register_plan("svc-2")
        eng.register_plan("svc-3")
        assert eng.get_plan(p1.id) is None
        assert len(eng.list_plans()) == 2


# ---------------------------------------------------------------------------
# get_plan / list_plans
# ---------------------------------------------------------------------------


class TestGetPlan:
    def test_found(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        assert eng.get_plan(plan.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_plan("nonexistent") is None


class TestListPlans:
    def test_list_all(self):
        eng = _engine()
        eng.register_plan("svc-a")
        eng.register_plan("svc-b")
        assert len(eng.list_plans()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_plan("svc-a")
        eng.register_plan("svc-b")
        eng.register_plan("svc-a")
        results = eng.list_plans(service="svc-a")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# update_plan
# ---------------------------------------------------------------------------


class TestUpdatePlan:
    def test_basic_update(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        updated = eng.update_plan(plan.id, rto_minutes=10)
        assert updated is not None
        assert updated.rto_minutes == 10

    def test_update_not_found(self):
        eng = _engine()
        assert eng.update_plan("nonexistent", rto_minutes=10) is None


# ---------------------------------------------------------------------------
# schedule_drill / complete_drill
# ---------------------------------------------------------------------------


class TestScheduleDrill:
    def test_basic_schedule(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        drill = eng.schedule_drill(plan.id)
        assert drill is not None
        assert drill.plan_id == plan.id
        assert drill.status == DrillStatus.SCHEDULED

    def test_schedule_invalid_plan(self):
        eng = _engine()
        assert eng.schedule_drill("nonexistent") is None


class TestCompleteDrill:
    def test_complete_passed(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        drill = eng.schedule_drill(plan.id)
        result = eng.complete_drill(drill.id, passed=True, actual_rto_minutes=10.0)
        assert result is not None
        assert result.status == DrillStatus.PASSED
        assert result.actual_rto_minutes == 10.0
        assert result.completed_at is not None

    def test_complete_failed(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        drill = eng.schedule_drill(plan.id)
        result = eng.complete_drill(drill.id, passed=False)
        assert result.status == DrillStatus.FAILED

    def test_complete_not_found(self):
        eng = _engine()
        assert eng.complete_drill("nonexistent") is None

    def test_complete_updates_plan(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        drill = eng.schedule_drill(plan.id)
        eng.complete_drill(drill.id, passed=True)
        updated_plan = eng.get_plan(plan.id)
        assert updated_plan.last_drill_at is not None


# ---------------------------------------------------------------------------
# assess_readiness
# ---------------------------------------------------------------------------


class TestAssessReadiness:
    def test_no_plans(self):
        eng = _engine()
        report = eng.assess_readiness("no-service")
        assert report.tier == ReadinessTier.UNRATED
        assert report.score == 0.0

    def test_platinum(self):
        eng = _engine()
        plan = eng.register_plan("svc-a", rto_minutes=30, rpo_minutes=15)
        for _ in range(10):
            drill = eng.schedule_drill(plan.id)
            eng.complete_drill(
                drill.id, passed=True, actual_rto_minutes=10.0, actual_rpo_minutes=5.0
            )
        report = eng.assess_readiness("svc-a")
        assert report.tier == ReadinessTier.PLATINUM
        assert report.score >= 90

    def test_bronze(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        drill = eng.schedule_drill(plan.id)
        eng.complete_drill(drill.id, passed=False)
        report = eng.assess_readiness("svc-a")
        assert report.tier == ReadinessTier.BRONZE


# ---------------------------------------------------------------------------
# list_drills
# ---------------------------------------------------------------------------


class TestListDrills:
    def test_list_all(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        eng.schedule_drill(plan.id)
        eng.schedule_drill(plan.id)
        assert len(eng.list_drills()) == 2

    def test_filter_by_plan(self):
        eng = _engine()
        p1 = eng.register_plan("svc-a")
        p2 = eng.register_plan("svc-b")
        eng.schedule_drill(p1.id)
        eng.schedule_drill(p2.id)
        results = eng.list_drills(plan_id=p1.id)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# get_overdue_drills
# ---------------------------------------------------------------------------


class TestGetOverdueDrills:
    def test_overdue(self):
        eng = _engine(drill_max_age_days=0)
        plan = eng.register_plan("svc-a")
        plan.last_drill_at = time.time() - 86400
        overdue = eng.get_overdue_drills()
        assert len(overdue) == 1

    def test_none_overdue(self):
        eng = _engine(drill_max_age_days=9999)
        plan = eng.register_plan("svc-a")
        plan.last_drill_at = time.time()
        overdue = eng.get_overdue_drills()
        assert len(overdue) == 0

    def test_no_drill_is_overdue(self):
        eng = _engine(drill_max_age_days=0)
        eng.register_plan("svc-a")
        overdue = eng.get_overdue_drills()
        assert len(overdue) == 1


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_plans"] == 0
        assert stats["total_drills"] == 0

    def test_populated_stats(self):
        eng = _engine()
        plan = eng.register_plan("svc-a")
        eng.schedule_drill(plan.id)
        stats = eng.get_stats()
        assert stats["total_plans"] == 1
        assert stats["total_drills"] == 1
