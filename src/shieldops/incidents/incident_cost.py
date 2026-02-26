"""Incident Cost Calculator — track and analyze incident-related costs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostComponent(StrEnum):
    DOWNTIME_REVENUE = "downtime_revenue"
    ENGINEERING_HOURS = "engineering_hours"
    CUSTOMER_IMPACT = "customer_impact"
    SLA_PENALTY = "sla_penalty"
    REMEDIATION = "remediation"


class CostSeverity(StrEnum):
    CATASTROPHIC = "catastrophic"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class CostTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class IncidentCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    component: CostComponent = CostComponent.DOWNTIME_REVENUE
    severity: CostSeverity = CostSeverity.MODERATE
    total_cost: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CostBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    breakdown_name: str = ""
    component: CostComponent = CostComponent.DOWNTIME_REVENUE
    severity: CostSeverity = CostSeverity.MODERATE
    amount: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentCostReport(BaseModel):
    total_costs: int = 0
    total_breakdowns: int = 0
    avg_cost: float = 0.0
    by_component: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_cost_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentCostCalculator:
    """Track incident costs, breakdowns, cost pattern analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        high_threshold: float = 10000.0,
    ) -> None:
        self._max_records = max_records
        self._high_threshold = high_threshold
        self._records: list[IncidentCostRecord] = []
        self._breakdowns: list[CostBreakdown] = []
        logger.info(
            "incident_cost.initialized",
            max_records=max_records,
            high_threshold=high_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_cost(
        self,
        service_name: str,
        component: CostComponent = CostComponent.DOWNTIME_REVENUE,
        severity: CostSeverity = CostSeverity.MODERATE,
        total_cost: float = 0.0,
        details: str = "",
    ) -> IncidentCostRecord:
        record = IncidentCostRecord(
            service_name=service_name,
            component=component,
            severity=severity,
            total_cost=total_cost,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_cost.recorded",
            record_id=record.id,
            service_name=service_name,
            component=component.value,
            severity=severity.value,
        )
        return record

    def get_cost(self, record_id: str) -> IncidentCostRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_costs(
        self,
        service_name: str | None = None,
        component: CostComponent | None = None,
        limit: int = 50,
    ) -> list[IncidentCostRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if component is not None:
            results = [r for r in results if r.component == component]
        return results[-limit:]

    def add_breakdown(
        self,
        breakdown_name: str,
        component: CostComponent = CostComponent.DOWNTIME_REVENUE,
        severity: CostSeverity = CostSeverity.MODERATE,
        amount: float = 0.0,
        description: str = "",
    ) -> CostBreakdown:
        breakdown = CostBreakdown(
            breakdown_name=breakdown_name,
            component=component,
            severity=severity,
            amount=amount,
            description=description,
        )
        self._breakdowns.append(breakdown)
        if len(self._breakdowns) > self._max_records:
            self._breakdowns = self._breakdowns[-self._max_records :]
        logger.info(
            "incident_cost.breakdown_added",
            breakdown_name=breakdown_name,
            component=component.value,
            severity=severity.value,
        )
        return breakdown

    # -- domain operations -----------------------------------------------

    def analyze_cost_by_service(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_cost = round(sum(r.total_cost for r in records) / len(records), 2)
        high_cost = sum(1 for r in records if r.total_cost >= self._high_threshold)
        return {
            "service_name": service_name,
            "total_records": len(records),
            "avg_cost": avg_cost,
            "high_cost_count": high_cost,
            "exceeds_threshold": avg_cost >= self._high_threshold,
        }

    def identify_costly_incidents(self) -> list[dict[str, Any]]:
        cost_counts: dict[str, int] = {}
        for r in self._records:
            if r.total_cost >= self._high_threshold:
                cost_counts[r.service_name] = cost_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in cost_counts.items():
            if count > 1:
                results.append({"service_name": svc, "high_cost_count": count})
        results.sort(key=lambda x: x["high_cost_count"], reverse=True)
        return results

    def rank_by_total_cost(self) -> list[dict[str, Any]]:
        svc_costs: dict[str, list[float]] = {}
        for r in self._records:
            svc_costs.setdefault(r.service_name, []).append(r.total_cost)
        results: list[dict[str, Any]] = []
        for svc, costs in svc_costs.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_total_cost": round(sum(costs) / len(costs), 2),
                    "record_count": len(costs),
                }
            )
        results.sort(key=lambda x: x["avg_total_cost"], reverse=True)
        return results

    def detect_cost_trends(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "cost_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["cost_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> IncidentCostReport:
        by_component: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_component[r.component.value] = by_component.get(r.component.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        avg_cost = (
            round(sum(r.total_cost for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_cost = sum(1 for r in self._records if r.total_cost >= self._high_threshold)
        recs: list[str] = []
        if avg_cost >= self._high_threshold:
            recs.append(f"Average cost ${avg_cost} exceeds ${self._high_threshold} threshold")
        trends = len(self.detect_cost_trends())
        if trends > 0:
            recs.append(f"{trends} service(s) with recurring cost trends")
        if not recs:
            recs.append("Incident cost analysis within acceptable range")
        return IncidentCostReport(
            total_costs=len(self._records),
            total_breakdowns=len(self._breakdowns),
            avg_cost=avg_cost,
            by_component=by_component,
            by_severity=by_severity,
            high_cost_count=high_cost,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._breakdowns.clear()
        logger.info("incident_cost.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        comp_dist: dict[str, int] = {}
        for r in self._records:
            key = r.component.value
            comp_dist[key] = comp_dist.get(key, 0) + 1
        return {
            "total_costs": len(self._records),
            "total_breakdowns": len(self._breakdowns),
            "high_threshold": self._high_threshold,
            "component_distribution": comp_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
