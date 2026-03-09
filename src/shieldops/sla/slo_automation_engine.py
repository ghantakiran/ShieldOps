"""SLO Automation Engine — automated SLO lifecycle management."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SLOType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class SLOStatus(StrEnum):
    ACTIVE = "active"
    PROPOSED = "proposed"
    BREACHED = "breached"
    DEPRECATED = "deprecated"
    DRAFT = "draft"


class BudgetPolicy(StrEnum):
    STRICT = "strict"
    RELAXED = "relaxed"
    ADAPTIVE = "adaptive"
    FREEZE = "freeze"


# --- Models ---


class SLORecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    service: str = ""
    slo_type: SLOType = SLOType.AVAILABILITY
    target_pct: float = 99.9
    current_pct: float = 100.0
    error_budget_remaining_pct: float = 100.0
    status: SLOStatus = SLOStatus.DRAFT
    window_days: int = 30
    created_at: float = Field(default_factory=time.time)


class ErrorBudgetPolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_name: str = ""
    policy: BudgetPolicy = BudgetPolicy.STRICT
    threshold_pct: float = 25.0
    action: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_slos: int = 0
    active_count: int = 0
    breached_count: int = 0
    avg_budget_remaining: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOAutomationEngine:
    """Automated SLO lifecycle management."""

    def __init__(self, max_slos: int = 50000) -> None:
        self._max_slos = max_slos
        self._slos: list[SLORecord] = []
        self._policies: list[ErrorBudgetPolicyRecord] = []
        logger.info("slo_automation_engine.initialized", max_slos=max_slos)

    def add_slo(
        self,
        name: str,
        service: str,
        slo_type: SLOType = SLOType.AVAILABILITY,
        target_pct: float = 99.9,
        window_days: int = 30,
    ) -> SLORecord:
        """Register an SLO."""
        record = SLORecord(
            name=name,
            service=service,
            slo_type=slo_type,
            target_pct=target_pct,
            window_days=window_days,
            status=SLOStatus.DRAFT,
        )
        self._slos.append(record)
        if len(self._slos) > self._max_slos:
            self._slos = self._slos[-self._max_slos :]
        logger.info("slo_automation_engine.slo_added", name=name, service=service)
        return record

    def propose_slo(
        self,
        service: str,
        slo_type: SLOType = SLOType.AVAILABILITY,
    ) -> SLORecord:
        """Propose an SLO based on current performance."""
        existing = [s for s in self._slos if s.service == service and s.slo_type == slo_type]
        if existing:
            avg_current = sum(s.current_pct for s in existing) / len(existing)
            target = round(max(99.0, avg_current - 0.5), 2)
        else:
            target = 99.5
        record = SLORecord(
            name=f"proposed-{service}-{slo_type.value}",
            service=service,
            slo_type=slo_type,
            target_pct=target,
            status=SLOStatus.PROPOSED,
        )
        self._slos.append(record)
        logger.info(
            "slo_automation_engine.slo_proposed",
            service=service,
            target=target,
        )
        return record

    def validate_slo(self, name: str) -> dict[str, Any]:
        """Validate an SLO configuration."""
        slos = [s for s in self._slos if s.name == name]
        if not slos:
            return {"name": name, "valid": False, "errors": ["SLO not found"]}
        slo = slos[-1]
        errors: list[str] = []
        if slo.target_pct < 90.0:
            errors.append("target below 90% — too loose")
        if slo.target_pct > 99.999:
            errors.append("target above 99.999% — likely unachievable")
        if slo.window_days < 1:
            errors.append("window must be at least 1 day")
        return {
            "name": name,
            "valid": len(errors) == 0,
            "errors": errors,
            "target_pct": slo.target_pct,
        }

    def auto_adjust_targets(
        self,
        service: str,
        adjustment_pct: float = 0.1,
    ) -> list[dict[str, Any]]:
        """Auto-adjust SLO targets based on performance."""
        slos = [s for s in self._slos if s.service == service]
        adjustments: list[dict[str, Any]] = []
        for slo in slos:
            if slo.status in (SLOStatus.DEPRECATED, SLOStatus.DRAFT):
                continue
            if slo.error_budget_remaining_pct < 10:
                new_target = round(slo.target_pct - adjustment_pct, 3)
                old_target = slo.target_pct
                slo.target_pct = new_target
                adjustments.append(
                    {
                        "slo": slo.name,
                        "old_target": old_target,
                        "new_target": new_target,
                        "reason": "error budget nearly exhausted",
                    }
                )
            elif slo.error_budget_remaining_pct > 90:
                new_target = round(slo.target_pct + adjustment_pct, 3)
                old_target = slo.target_pct
                slo.target_pct = min(99.999, new_target)
                adjustments.append(
                    {
                        "slo": slo.name,
                        "old_target": old_target,
                        "new_target": slo.target_pct,
                        "reason": "excess error budget — tightening target",
                    }
                )
        return adjustments

    def generate_error_budget_policy(
        self,
        slo_name: str,
        policy: BudgetPolicy = BudgetPolicy.STRICT,
        threshold_pct: float = 25.0,
    ) -> ErrorBudgetPolicyRecord:
        """Generate an error budget policy for an SLO."""
        actions = {
            BudgetPolicy.STRICT: "freeze deployments when budget < threshold",
            BudgetPolicy.RELAXED: "alert team when budget < threshold",
            BudgetPolicy.ADAPTIVE: "reduce deployment velocity proportionally",
            BudgetPolicy.FREEZE: "halt all changes immediately",
        }
        record = ErrorBudgetPolicyRecord(
            slo_name=slo_name,
            policy=policy,
            threshold_pct=threshold_pct,
            action=actions.get(policy, "alert"),
        )
        self._policies.append(record)
        logger.info(
            "slo_automation_engine.policy_generated",
            slo=slo_name,
            policy=policy.value,
        )
        return record

    def get_slo_recommendations(self, service: str) -> list[dict[str, Any]]:
        """Get SLO recommendations for a service."""
        slos = [s for s in self._slos if s.service == service]
        recs: list[dict[str, Any]] = []
        covered_types = {s.slo_type for s in slos}
        for slo_type in SLOType:
            if slo_type not in covered_types:
                recs.append(
                    {
                        "type": "missing_slo",
                        "slo_type": slo_type.value,
                        "message": f"No {slo_type.value} SLO — consider adding one",
                    }
                )
        for slo in slos:
            if slo.error_budget_remaining_pct < 20:
                recs.append(
                    {
                        "type": "budget_low",
                        "slo": slo.name,
                        "remaining_pct": slo.error_budget_remaining_pct,
                        "message": "Error budget running low",
                    }
                )
        if not recs:
            recs.append(
                {
                    "type": "healthy",
                    "message": f"SLOs for {service} are healthy",
                }
            )
        return recs

    def generate_report(self) -> SLOReport:
        """Generate SLO automation report."""
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for s in self._slos:
            by_type[s.slo_type.value] = by_type.get(s.slo_type.value, 0) + 1
            by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
        active = sum(1 for s in self._slos if s.status == SLOStatus.ACTIVE)
        breached = sum(1 for s in self._slos if s.status == SLOStatus.BREACHED)
        budgets = [s.error_budget_remaining_pct for s in self._slos]
        avg_budget = round(sum(budgets) / len(budgets), 2) if budgets else 0.0
        recs: list[str] = []
        if breached > 0:
            recs.append(f"{breached} SLO(s) breached — review immediately")
        if not recs:
            recs.append("All SLOs within targets")
        return SLOReport(
            total_slos=len(self._slos),
            active_count=active,
            breached_count=breached,
            avg_budget_remaining=avg_budget,
            by_type=by_type,
            by_status=by_status,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all SLOs and policies."""
        self._slos.clear()
        self._policies.clear()
        logger.info("slo_automation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_slos": len(self._slos),
            "total_policies": len(self._policies),
            "unique_services": len({s.service for s in self._slos}),
        }
