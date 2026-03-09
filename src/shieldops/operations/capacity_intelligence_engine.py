"""CapacityIntelligenceEngine

Predictive capacity planning, resource right-sizing,
scaling recommendations, cost-aware provisioning.
"""

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
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"


class SizingAction(StrEnum):
    UPSIZE = "upsize"
    DOWNSIZE = "downsize"
    MAINTAIN = "maintain"
    CONSOLIDATE = "consolidate"
    DECOMMISSION = "decommission"


class CapacityRisk(StrEnum):
    EXHAUSTION_IMMINENT = "exhaustion_imminent"
    APPROACHING_LIMIT = "approaching_limit"
    HEALTHY = "healthy"
    OVER_PROVISIONED = "over_provisioned"
    IDLE = "idle"


# --- Models ---


class CapacityIntelligenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    sizing_action: SizingAction = SizingAction.MAINTAIN
    capacity_risk: CapacityRisk = CapacityRisk.HEALTHY
    current_utilization_pct: float = 0.0
    peak_utilization_pct: float = 0.0
    allocated_units: float = 0.0
    used_units: float = 0.0
    projected_exhaustion_days: int = 0
    monthly_cost: float = 0.0
    potential_savings: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityIntelligenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    analysis_score: float = 0.0
    utilization_efficiency: float = 0.0
    cost_efficiency: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    over_provisioned_count: int = 0
    at_risk_count: int = 0
    total_potential_savings: float = 0.0
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_sizing_action: dict[str, int] = Field(default_factory=dict)
    by_capacity_risk: dict[str, int] = Field(default_factory=dict)
    top_savings_opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityIntelligenceEngine:
    """Predictive capacity planning with resource right-sizing and cost-aware provisioning."""

    def __init__(
        self,
        max_records: int = 200000,
        utilization_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._utilization_threshold = utilization_threshold
        self._records: list[CapacityIntelligenceRecord] = []
        self._analyses: list[CapacityIntelligenceAnalysis] = []
        logger.info(
            "capacity.intelligence.engine.initialized",
            max_records=max_records,
            utilization_threshold=utilization_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        resource_type: ResourceType = ResourceType.CPU,
        sizing_action: SizingAction = SizingAction.MAINTAIN,
        capacity_risk: CapacityRisk = CapacityRisk.HEALTHY,
        current_utilization_pct: float = 0.0,
        peak_utilization_pct: float = 0.0,
        allocated_units: float = 0.0,
        used_units: float = 0.0,
        projected_exhaustion_days: int = 0,
        monthly_cost: float = 0.0,
        potential_savings: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CapacityIntelligenceRecord:
        record = CapacityIntelligenceRecord(
            name=name,
            resource_type=resource_type,
            sizing_action=sizing_action,
            capacity_risk=capacity_risk,
            current_utilization_pct=current_utilization_pct,
            peak_utilization_pct=peak_utilization_pct,
            allocated_units=allocated_units,
            used_units=used_units,
            projected_exhaustion_days=projected_exhaustion_days,
            monthly_cost=monthly_cost,
            potential_savings=potential_savings,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity.intelligence.engine.item_recorded",
            record_id=record.id,
            name=name,
            resource_type=resource_type.value,
            capacity_risk=capacity_risk.value,
        )
        return record

    def get_record(self, record_id: str) -> CapacityIntelligenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        resource_type: ResourceType | None = None,
        capacity_risk: CapacityRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CapacityIntelligenceRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if capacity_risk is not None:
            results = [r for r in results if r.capacity_risk == capacity_risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        resource_type: ResourceType = ResourceType.CPU,
        analysis_score: float = 0.0,
        utilization_efficiency: float = 0.0,
        cost_efficiency: float = 0.0,
        description: str = "",
    ) -> CapacityIntelligenceAnalysis:
        analysis = CapacityIntelligenceAnalysis(
            name=name,
            resource_type=resource_type,
            analysis_score=analysis_score,
            utilization_efficiency=utilization_efficiency,
            cost_efficiency=cost_efficiency,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "capacity.intelligence.engine.analysis_added",
            name=name,
            resource_type=resource_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def recommend_right_sizing(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.allocated_units > 0:
                efficiency = round(r.used_units / r.allocated_units * 100, 2)
            else:
                efficiency = 0.0
            action = r.sizing_action.value
            if efficiency < 20:
                action = "decommission"
            elif efficiency < 40:
                action = "downsize"
            elif efficiency > 90:
                action = "upsize"
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "resource_type": r.resource_type.value,
                    "current_efficiency": efficiency,
                    "recommended_action": action,
                    "potential_savings": r.potential_savings,
                    "service": r.service,
                }
            )
        return sorted(results, key=lambda x: x["potential_savings"], reverse=True)

    def predict_exhaustion(self) -> list[dict[str, Any]]:
        at_risk: list[dict[str, Any]] = []
        for r in self._records:
            if r.capacity_risk in (
                CapacityRisk.EXHAUSTION_IMMINENT,
                CapacityRisk.APPROACHING_LIMIT,
            ):
                at_risk.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "resource_type": r.resource_type.value,
                        "current_utilization": r.current_utilization_pct,
                        "peak_utilization": r.peak_utilization_pct,
                        "projected_exhaustion_days": r.projected_exhaustion_days,
                        "service": r.service,
                    }
                )
        return sorted(at_risk, key=lambda x: x["projected_exhaustion_days"])

    def calculate_cost_efficiency(self) -> dict[str, Any]:
        type_costs: dict[str, dict[str, float]] = {}
        for r in self._records:
            key = r.resource_type.value
            type_costs.setdefault(key, {"total_cost": 0.0, "total_savings": 0.0, "count": 0})
            type_costs[key]["total_cost"] += r.monthly_cost
            type_costs[key]["total_savings"] += r.potential_savings
            type_costs[key]["count"] += 1
        result: dict[str, Any] = {}
        for rtype, data in type_costs.items():
            waste_ratio = (
                round(data["total_savings"] / data["total_cost"] * 100, 2)
                if data["total_cost"] > 0
                else 0.0
            )
            result[rtype] = {
                "total_monthly_cost": round(data["total_cost"], 2),
                "total_potential_savings": round(data["total_savings"], 2),
                "waste_ratio_pct": waste_ratio,
                "resource_count": int(data["count"]),
            }
        return result

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CapacityIntelligenceReport:
        by_type: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_type[r.resource_type.value] = by_type.get(r.resource_type.value, 0) + 1
            by_action[r.sizing_action.value] = by_action.get(r.sizing_action.value, 0) + 1
            by_risk[r.capacity_risk.value] = by_risk.get(r.capacity_risk.value, 0) + 1
        utils = [r.current_utilization_pct for r in self._records]
        avg_util = round(sum(utils) / len(utils), 2) if utils else 0.0
        over_prov = sum(
            1
            for r in self._records
            if r.capacity_risk in (CapacityRisk.OVER_PROVISIONED, CapacityRisk.IDLE)
        )
        at_risk = sum(
            1
            for r in self._records
            if r.capacity_risk in (CapacityRisk.EXHAUSTION_IMMINENT, CapacityRisk.APPROACHING_LIMIT)
        )
        total_savings = round(sum(r.potential_savings for r in self._records), 2)
        sizing = self.recommend_right_sizing()
        top_savings = [s["name"] for s in sizing[:5]]
        recs: list[str] = []
        if over_prov > 0:
            recs.append(
                f"{over_prov} resource(s) over-provisioned"
                f" — right-size to save ${total_savings:.2f}/mo"
            )
        if at_risk > 0:
            recs.append(f"{at_risk} resource(s) approaching capacity limits — plan scaling")
        if avg_util < 30.0 and self._records:
            recs.append(f"Avg utilization {avg_util}% — consolidation recommended")
        if not recs:
            recs.append("Capacity intelligence is healthy — resources optimally sized")
        return CapacityIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg_util,
            over_provisioned_count=over_prov,
            at_risk_count=at_risk,
            total_potential_savings=total_savings,
            by_resource_type=by_type,
            by_sizing_action=by_action,
            by_capacity_risk=by_risk,
            top_savings_opportunities=top_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("capacity.intelligence.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            type_dist[r.resource_type.value] = type_dist.get(r.resource_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "utilization_threshold": self._utilization_threshold,
            "resource_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
