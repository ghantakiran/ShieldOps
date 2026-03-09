"""InfrastructureCostIntelligence

Infrastructure cost attribution, resource waste detection,
optimization recommendations, trend analysis.
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


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    OBSERVABILITY = "observability"
    SECURITY = "security"


class WasteType(StrEnum):
    IDLE_RESOURCE = "idle_resource"
    OVER_PROVISIONED = "over_provisioned"
    UNATTACHED_VOLUME = "unattached_volume"
    UNUSED_LICENSE = "unused_license"
    STALE_SNAPSHOT = "stale_snapshot"
    ORPHANED_RESOURCE = "orphaned_resource"


class OptimizationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class InfrastructureCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cost_category: CostCategory = CostCategory.COMPUTE
    waste_type: WasteType = WasteType.IDLE_RESOURCE
    optimization_priority: OptimizationPriority = OptimizationPriority.MEDIUM
    monthly_cost: float = 0.0
    projected_monthly_cost: float = 0.0
    potential_savings: float = 0.0
    utilization_pct: float = 0.0
    resource_count: int = 0
    cloud_provider: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class InfrastructureCostAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cost_category: CostCategory = CostCategory.COMPUTE
    analysis_score: float = 0.0
    cost_efficiency_pct: float = 0.0
    month_over_month_delta: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InfrastructureCostReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_monthly_cost: float = 0.0
    total_potential_savings: float = 0.0
    waste_ratio_pct: float = 0.0
    avg_utilization: float = 0.0
    by_category: dict[str, float] = Field(default_factory=dict)
    by_waste_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_cost_drivers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureCostIntelligence:
    """Infrastructure cost attribution with waste detection and optimization recommendations."""

    def __init__(
        self,
        max_records: int = 200000,
        waste_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._waste_threshold = waste_threshold
        self._records: list[InfrastructureCostRecord] = []
        self._analyses: list[InfrastructureCostAnalysis] = []
        logger.info(
            "infrastructure.cost.intelligence.initialized",
            max_records=max_records,
            waste_threshold=waste_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        cost_category: CostCategory = CostCategory.COMPUTE,
        waste_type: WasteType = WasteType.IDLE_RESOURCE,
        optimization_priority: OptimizationPriority = OptimizationPriority.MEDIUM,
        monthly_cost: float = 0.0,
        projected_monthly_cost: float = 0.0,
        potential_savings: float = 0.0,
        utilization_pct: float = 0.0,
        resource_count: int = 0,
        cloud_provider: str = "",
        service: str = "",
        team: str = "",
    ) -> InfrastructureCostRecord:
        record = InfrastructureCostRecord(
            name=name,
            cost_category=cost_category,
            waste_type=waste_type,
            optimization_priority=optimization_priority,
            monthly_cost=monthly_cost,
            projected_monthly_cost=projected_monthly_cost,
            potential_savings=potential_savings,
            utilization_pct=utilization_pct,
            resource_count=resource_count,
            cloud_provider=cloud_provider,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "infrastructure.cost.intelligence.item_recorded",
            record_id=record.id,
            name=name,
            cost_category=cost_category.value,
            monthly_cost=monthly_cost,
        )
        return record

    def get_record(self, record_id: str) -> InfrastructureCostRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        cost_category: CostCategory | None = None,
        waste_type: WasteType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InfrastructureCostRecord]:
        results = list(self._records)
        if cost_category is not None:
            results = [r for r in results if r.cost_category == cost_category]
        if waste_type is not None:
            results = [r for r in results if r.waste_type == waste_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        cost_category: CostCategory = CostCategory.COMPUTE,
        analysis_score: float = 0.0,
        cost_efficiency_pct: float = 0.0,
        month_over_month_delta: float = 0.0,
        description: str = "",
    ) -> InfrastructureCostAnalysis:
        analysis = InfrastructureCostAnalysis(
            name=name,
            cost_category=cost_category,
            analysis_score=analysis_score,
            cost_efficiency_pct=cost_efficiency_pct,
            month_over_month_delta=month_over_month_delta,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "infrastructure.cost.intelligence.analysis_added",
            name=name,
            cost_category=cost_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def attribute_costs(self) -> dict[str, Any]:
        team_costs: dict[str, float] = {}
        provider_costs: dict[str, float] = {}
        for r in self._records:
            team_costs[r.team] = team_costs.get(r.team, 0.0) + r.monthly_cost
            provider_costs[r.cloud_provider] = (
                provider_costs.get(r.cloud_provider, 0.0) + r.monthly_cost
            )
        return {
            "by_team": {k: round(v, 2) for k, v in team_costs.items()},
            "by_provider": {k: round(v, 2) for k, v in provider_costs.items()},
            "total_monthly": round(sum(r.monthly_cost for r in self._records), 2),
        }

    def detect_waste(self) -> list[dict[str, Any]]:
        wasteful: list[dict[str, Any]] = []
        for r in self._records:
            if r.potential_savings > 0 and r.utilization_pct < self._waste_threshold:
                waste_score = round((1 - r.utilization_pct / 100) * r.monthly_cost, 2)
                wasteful.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "waste_type": r.waste_type.value,
                        "monthly_cost": r.monthly_cost,
                        "utilization_pct": r.utilization_pct,
                        "potential_savings": r.potential_savings,
                        "waste_score": waste_score,
                        "cloud_provider": r.cloud_provider,
                    }
                )
        return sorted(wasteful, key=lambda x: x["waste_score"], reverse=True)

    def forecast_cost_trend(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        deltas = [a.month_over_month_delta for a in self._analyses]
        avg_delta = round(sum(deltas) / len(deltas), 2)
        total_current = sum(r.monthly_cost for r in self._records)
        projected = round(total_current * (1 + avg_delta / 100), 2)
        return {
            "current_monthly": round(total_current, 2),
            "projected_next_month": projected,
            "avg_mom_delta_pct": avg_delta,
            "trend": "increasing"
            if avg_delta > 2
            else ("decreasing" if avg_delta < -2 else "stable"),
        }

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

    def generate_report(self) -> InfrastructureCostReport:
        by_cat: dict[str, float] = {}
        by_waste: dict[str, int] = {}
        by_prio: dict[str, int] = {}
        for r in self._records:
            by_cat[r.cost_category.value] = by_cat.get(r.cost_category.value, 0.0) + r.monthly_cost
            by_waste[r.waste_type.value] = by_waste.get(r.waste_type.value, 0) + 1
            by_prio[r.optimization_priority.value] = (
                by_prio.get(r.optimization_priority.value, 0) + 1
            )
        by_cat = {k: round(v, 2) for k, v in by_cat.items()}
        total_cost = round(sum(r.monthly_cost for r in self._records), 2)
        total_savings = round(sum(r.potential_savings for r in self._records), 2)
        waste_ratio = round(total_savings / total_cost * 100, 2) if total_cost > 0 else 0.0
        utils = [r.utilization_pct for r in self._records]
        avg_util = round(sum(utils) / len(utils), 2) if utils else 0.0
        svc_costs: dict[str, float] = {}
        for r in self._records:
            svc_costs[r.service] = svc_costs.get(r.service, 0.0) + r.monthly_cost
        top_drivers = sorted(svc_costs, key=svc_costs.get, reverse=True)[:5]  # type: ignore[arg-type]
        recs: list[str] = []
        if waste_ratio > 20:
            recs.append(
                f"Waste ratio {waste_ratio}% — ${total_savings:.2f}/mo in savings available"
            )
        if avg_util < 30 and self._records:
            recs.append(f"Avg utilization {avg_util}% — consolidation opportunities exist")
        critical = by_prio.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical optimization(s) require immediate action")
        if not recs:
            recs.append("Infrastructure cost is well-optimized — minimal waste detected")
        return InfrastructureCostReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_monthly_cost=total_cost,
            total_potential_savings=total_savings,
            waste_ratio_pct=waste_ratio,
            avg_utilization=avg_util,
            by_category=by_cat,
            by_waste_type=by_waste,
            by_priority=by_prio,
            top_cost_drivers=top_drivers,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("infrastructure.cost.intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            cat_dist[r.cost_category.value] = cat_dist.get(r.cost_category.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "waste_threshold": self._waste_threshold,
            "category_distribution": cat_dist,
            "unique_providers": len({r.cloud_provider for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
