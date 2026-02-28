"""Infra Capacity Planner — plan infrastructure capacity needs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"


class PlanningHorizon(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class CapacityAction(StrEnum):
    PROVISION = "provision"
    DECOMMISSION = "decommission"
    RESIZE = "resize"
    MIGRATE = "migrate"
    MAINTAIN = "maintain"


# --- Models ---


class CapacityPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    resource: ResourceType = ResourceType.COMPUTE
    horizon: PlanningHorizon = PlanningHorizon.MONTHLY
    action: CapacityAction = CapacityAction.MAINTAIN
    utilization_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PlanningRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    resource: ResourceType = ResourceType.COMPUTE
    horizon: PlanningHorizon = PlanningHorizon.MONTHLY
    target_utilization_pct: float = 70.0
    headroom_pct: float = 20.0
    created_at: float = Field(default_factory=time.time)


class CapacityPlannerReport(BaseModel):
    total_plans: int = 0
    total_rules: int = 0
    optimal_rate_pct: float = 0.0
    by_resource: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    over_provisioned_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfraCapacityPlanner:
    """Plan infrastructure capacity needs."""

    def __init__(
        self,
        max_records: int = 200000,
        target_utilization_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._target_utilization_pct = target_utilization_pct
        self._records: list[CapacityPlan] = []
        self._rules: list[PlanningRule] = []
        logger.info(
            "infra_capacity_planner.initialized",
            max_records=max_records,
            target_utilization_pct=(target_utilization_pct),
        )

    # -- record / get / list -----------------------------------------

    def record_plan(
        self,
        service_name: str,
        resource: ResourceType = ResourceType.COMPUTE,
        horizon: PlanningHorizon = (PlanningHorizon.MONTHLY),
        action: CapacityAction = (CapacityAction.MAINTAIN),
        utilization_pct: float = 0.0,
        details: str = "",
    ) -> CapacityPlan:
        record = CapacityPlan(
            service_name=service_name,
            resource=resource,
            horizon=horizon,
            action=action,
            utilization_pct=utilization_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "infra_capacity_planner.plan_recorded",
            record_id=record.id,
            service_name=service_name,
            resource=resource.value,
            action=action.value,
        )
        return record

    def get_plan(self, record_id: str) -> CapacityPlan | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_plans(
        self,
        service_name: str | None = None,
        resource: ResourceType | None = None,
        limit: int = 50,
    ) -> list[CapacityPlan]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if resource is not None:
            results = [r for r in results if r.resource == resource]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        resource: ResourceType = ResourceType.COMPUTE,
        horizon: PlanningHorizon = (PlanningHorizon.MONTHLY),
        target_utilization_pct: float = 70.0,
        headroom_pct: float = 20.0,
    ) -> PlanningRule:
        rule = PlanningRule(
            rule_name=rule_name,
            resource=resource,
            horizon=horizon,
            target_utilization_pct=(target_utilization_pct),
            headroom_pct=headroom_pct,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "infra_capacity_planner.rule_added",
            rule_name=rule_name,
            resource=resource.value,
            horizon=horizon.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_capacity_efficiency(self, service_name: str) -> dict[str, Any]:
        """Analyze capacity efficiency for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        optimal = sum(1 for r in records if r.action == CapacityAction.MAINTAIN)
        optimal_rate = round(optimal / len(records) * 100, 2)
        avg_util = round(
            sum(r.utilization_pct for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "plan_count": len(records),
            "optimal_count": optimal,
            "optimal_rate": optimal_rate,
            "avg_utilization": avg_util,
            "meets_threshold": (avg_util <= self._target_utilization_pct),
        }

    def identify_over_provisioned(
        self,
    ) -> list[dict[str, Any]]:
        """Find over-provisioned services."""
        counts: dict[str, int] = {}
        for r in self._records:
            if r.action in (
                CapacityAction.DECOMMISSION,
                CapacityAction.RESIZE,
            ):
                counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "over_provisioned_count": (count),
                    }
                )
        results.sort(
            key=lambda x: x["over_provisioned_count"],
            reverse=True,
        )
        return results

    def rank_by_utilization(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg utilization desc."""
        svc_vals: dict[str, list[float]] = {}
        for r in self._records:
            svc_vals.setdefault(r.service_name, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for svc, vals in svc_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_utilization": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
            reverse=True,
        )
        return results

    def detect_capacity_risks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect capacity risks (>3 non-MAINTAIN)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.action != CapacityAction.MAINTAIN:
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "risk_count": count,
                        "risk_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["risk_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> CapacityPlannerReport:
        by_resource: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_resource[r.resource.value] = by_resource.get(r.resource.value, 0) + 1
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
        optimal_count = sum(1 for r in self._records if r.action == CapacityAction.MAINTAIN)
        optimal_rate = (
            round(
                optimal_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        over_prov = len(self.identify_over_provisioned())
        recs: list[str] = []
        if over_prov > 0:
            recs.append(f"{over_prov} service(s) over-provisioned")
        risks = len(self.detect_capacity_risks())
        if risks > 0:
            recs.append(f"{risks} service(s) with capacity risks")
        if optimal_rate < 50.0 and self._records:
            recs.append(f"Optimal rate {optimal_rate}% is below 50% target")
        if not recs:
            recs.append("Infrastructure capacity is optimal")
        return CapacityPlannerReport(
            total_plans=len(self._records),
            total_rules=len(self._rules),
            optimal_rate_pct=optimal_rate,
            by_resource=by_resource,
            by_action=by_action,
            over_provisioned_count=over_prov,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("infra_capacity_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        resource_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource.value
            resource_dist[key] = resource_dist.get(key, 0) + 1
        return {
            "total_plans": len(self._records),
            "total_rules": len(self._rules),
            "target_utilization_pct": (self._target_utilization_pct),
            "resource_distribution": resource_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
