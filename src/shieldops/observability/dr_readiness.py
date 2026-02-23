"""Disaster Recovery Readiness Tracker — RTO/RPO tracking, drill scheduling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecoveryObjectiveType(StrEnum):
    RTO = "rto"
    RPO = "rpo"
    MTTR = "mttr"
    WRT = "wrt"


class DrillStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReadinessTier(StrEnum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    UNRATED = "unrated"


# --- Models ---


class RecoveryPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    rto_minutes: int = 60
    rpo_minutes: int = 30
    mttr_minutes: int = 45
    wrt_minutes: int = 15
    owner: str = ""
    tier: ReadinessTier = ReadinessTier.UNRATED
    last_drill_at: float | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class DrDrill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    status: DrillStatus = DrillStatus.SCHEDULED
    scheduled_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    actual_rto_minutes: float | None = None
    actual_rpo_minutes: float | None = None
    notes: str = ""


class ReadinessReport(BaseModel):
    service: str
    plan_id: str
    tier: ReadinessTier = ReadinessTier.UNRATED
    drill_count: int = 0
    passed_drills: int = 0
    last_drill_at: float | None = None
    rto_met: bool = False
    rpo_met: bool = False
    score: float = 0.0


# --- Engine ---


class DisasterRecoveryReadinessTracker:
    """Tracks RTO/RPO objectives, schedules failover drills, scores readiness."""

    def __init__(
        self,
        max_plans: int = 2000,
        drill_max_age_days: int = 90,
    ) -> None:
        self._max_plans = max_plans
        self._drill_max_age_days = drill_max_age_days
        self._plans: dict[str, RecoveryPlan] = {}
        self._drills: dict[str, DrDrill] = {}
        logger.info(
            "dr_readiness.initialized",
            max_plans=max_plans,
            drill_max_age_days=drill_max_age_days,
        )

    def register_plan(
        self,
        service: str,
        rto_minutes: int = 60,
        rpo_minutes: int = 30,
        **kw: Any,
    ) -> RecoveryPlan:
        plan = RecoveryPlan(
            service=service,
            rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes,
            **kw,
        )
        self._plans[plan.id] = plan
        if len(self._plans) > self._max_plans:
            oldest = next(iter(self._plans))
            del self._plans[oldest]
        logger.info("dr_readiness.plan_registered", plan_id=plan.id, service=service)
        return plan

    def get_plan(self, plan_id: str) -> RecoveryPlan | None:
        return self._plans.get(plan_id)

    def list_plans(self, service: str | None = None) -> list[RecoveryPlan]:
        results = list(self._plans.values())
        if service is not None:
            results = [p for p in results if p.service == service]
        return results

    def update_plan(
        self,
        plan_id: str,
        **kw: Any,
    ) -> RecoveryPlan | None:
        plan = self._plans.get(plan_id)
        if plan is None:
            return None
        for key, value in kw.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        plan.updated_at = time.time()
        logger.info("dr_readiness.plan_updated", plan_id=plan_id)
        return plan

    def schedule_drill(
        self,
        plan_id: str,
        **kw: Any,
    ) -> DrDrill | None:
        if plan_id not in self._plans:
            return None
        drill = DrDrill(plan_id=plan_id, **kw)
        self._drills[drill.id] = drill
        logger.info("dr_readiness.drill_scheduled", drill_id=drill.id, plan_id=plan_id)
        return drill

    def complete_drill(
        self,
        drill_id: str,
        passed: bool = True,
        actual_rto_minutes: float | None = None,
        actual_rpo_minutes: float | None = None,
        notes: str = "",
    ) -> DrDrill | None:
        drill = self._drills.get(drill_id)
        if drill is None:
            return None
        drill.status = DrillStatus.PASSED if passed else DrillStatus.FAILED
        drill.completed_at = time.time()
        drill.actual_rto_minutes = actual_rto_minutes
        drill.actual_rpo_minutes = actual_rpo_minutes
        if notes:
            drill.notes = notes
        plan = self._plans.get(drill.plan_id)
        if plan is not None:
            plan.last_drill_at = drill.completed_at
        logger.info("dr_readiness.drill_completed", drill_id=drill_id, passed=passed)
        return drill

    def assess_readiness(self, service: str) -> ReadinessReport:
        plans = [p for p in self._plans.values() if p.service == service]
        if not plans:
            return ReadinessReport(service=service, plan_id="")
        plan = plans[0]
        drills = [d for d in self._drills.values() if d.plan_id == plan.id]
        passed = [d for d in drills if d.status == DrillStatus.PASSED]
        drill_times = [d.completed_at for d in drills if d.completed_at is not None]
        last_drill = max(drill_times) if drill_times else None
        rto_met = any(
            d.actual_rto_minutes is not None and d.actual_rto_minutes <= plan.rto_minutes
            for d in passed
        )
        rpo_met = any(
            d.actual_rpo_minutes is not None and d.actual_rpo_minutes <= plan.rpo_minutes
            for d in passed
        )
        total = len(drills)
        pass_count = len(passed)
        score = 0.0 if total == 0 else round((pass_count / total) * 100, 1)
        if score >= 90 and rto_met and rpo_met:
            tier = ReadinessTier.PLATINUM
        elif score >= 75 and (rto_met or rpo_met):
            tier = ReadinessTier.GOLD
        elif score >= 50:
            tier = ReadinessTier.SILVER
        elif total > 0:
            tier = ReadinessTier.BRONZE
        else:
            tier = ReadinessTier.UNRATED
        plan.tier = tier
        return ReadinessReport(
            service=service,
            plan_id=plan.id,
            tier=tier,
            drill_count=total,
            passed_drills=pass_count,
            last_drill_at=last_drill,
            rto_met=rto_met,
            rpo_met=rpo_met,
            score=score,
        )

    def list_drills(
        self,
        plan_id: str | None = None,
        status: DrillStatus | None = None,
    ) -> list[DrDrill]:
        results = list(self._drills.values())
        if plan_id is not None:
            results = [d for d in results if d.plan_id == plan_id]
        if status is not None:
            results = [d for d in results if d.status == status]
        return results

    def get_overdue_drills(self) -> list[RecoveryPlan]:
        cutoff = time.time() - (self._drill_max_age_days * 86400)
        overdue: list[RecoveryPlan] = []
        for plan in self._plans.values():
            if plan.last_drill_at is None or plan.last_drill_at < cutoff:
                overdue.append(plan)
        return overdue

    def get_stats(self) -> dict[str, Any]:
        tier_counts: dict[str, int] = {}
        for p in self._plans.values():
            tier_counts[p.tier] = tier_counts.get(p.tier, 0) + 1
        status_counts: dict[str, int] = {}
        for d in self._drills.values():
            status_counts[d.status] = status_counts.get(d.status, 0) + 1
        return {
            "total_plans": len(self._plans),
            "total_drills": len(self._drills),
            "tier_distribution": tier_counts,
            "drill_status_distribution": status_counts,
        }
