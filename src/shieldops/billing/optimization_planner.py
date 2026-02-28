"""Cost Optimization Planner — plan and analyze cost optimization opportunities."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OptimizationType(StrEnum):
    RIGHT_SIZING = "right_sizing"
    RESERVED_INSTANCE = "reserved_instance"
    SPOT_INSTANCE = "spot_instance"
    STORAGE_TIERING = "storage_tiering"
    LICENSE_OPTIMIZATION = "license_optimization"


class OptimizationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class ImplementationEffort(StrEnum):
    TRIVIAL = "trivial"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    COMPLEX = "complex"


# --- Models ---


class OptimizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    priority: OptimizationPriority = OptimizationPriority.MEDIUM
    effort: ImplementationEffort = ImplementationEffort.MODERATE
    savings_pct: float = 0.0
    estimated_savings_usd: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationAction(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    action_description: str = ""
    effort: ImplementationEffort = ImplementationEffort.LOW
    estimated_savings_usd: float = 0.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationPlannerReport(BaseModel):
    total_optimizations: int = 0
    total_actions: int = 0
    avg_savings_pct: float = 0.0
    total_estimated_savings_usd: float = 0.0
    by_optimization_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    quick_wins_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostOptimizationPlanner:
    """Plan and analyze cost optimization opportunities across infrastructure."""

    def __init__(
        self,
        max_records: int = 200000,
        min_savings_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._min_savings_pct = min_savings_pct
        self._records: list[OptimizationRecord] = []
        self._actions: list[OptimizationAction] = []
        logger.info(
            "optimization_planner.initialized",
            max_records=max_records,
            min_savings_pct=min_savings_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_optimization(
        self,
        resource_id: str = "",
        optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING,
        priority: OptimizationPriority = OptimizationPriority.MEDIUM,
        effort: ImplementationEffort = ImplementationEffort.MODERATE,
        savings_pct: float = 0.0,
        estimated_savings_usd: float = 0.0,
        details: str = "",
    ) -> OptimizationRecord:
        record = OptimizationRecord(
            resource_id=resource_id,
            optimization_type=optimization_type,
            priority=priority,
            effort=effort,
            savings_pct=savings_pct,
            estimated_savings_usd=estimated_savings_usd,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "optimization_planner.optimization_recorded",
            record_id=record.id,
            resource_id=resource_id,
            optimization_type=optimization_type.value,
        )
        return record

    def get_optimization(self, record_id: str) -> OptimizationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_optimizations(
        self,
        optimization_type: OptimizationType | None = None,
        priority: OptimizationPriority | None = None,
        limit: int = 50,
    ) -> list[OptimizationRecord]:
        results = list(self._records)
        if optimization_type is not None:
            results = [r for r in results if r.optimization_type == optimization_type]
        if priority is not None:
            results = [r for r in results if r.priority == priority]
        return results[-limit:]

    def add_action(
        self,
        resource_id: str = "",
        optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING,
        action_description: str = "",
        effort: ImplementationEffort = ImplementationEffort.LOW,
        estimated_savings_usd: float = 0.0,
        notes: str = "",
    ) -> OptimizationAction:
        action = OptimizationAction(
            resource_id=resource_id,
            optimization_type=optimization_type,
            action_description=action_description,
            effort=effort,
            estimated_savings_usd=estimated_savings_usd,
            notes=notes,
        )
        self._actions.append(action)
        if len(self._actions) > self._max_records:
            self._actions = self._actions[-self._max_records :]
        logger.info(
            "optimization_planner.action_added",
            resource_id=resource_id,
            optimization_type=optimization_type.value,
        )
        return action

    # -- domain operations -----------------------------------------------

    def analyze_optimization_by_type(self, optimization_type: OptimizationType) -> dict[str, Any]:
        """Analyze optimizations for a specific type."""
        records = [r for r in self._records if r.optimization_type == optimization_type]
        if not records:
            return {"optimization_type": optimization_type.value, "status": "no_data"}
        avg_savings = round(sum(r.savings_pct for r in records) / len(records), 2)
        total_usd = round(sum(r.estimated_savings_usd for r in records), 2)
        return {
            "optimization_type": optimization_type.value,
            "total": len(records),
            "avg_savings_pct": avg_savings,
            "total_estimated_savings_usd": total_usd,
            "meets_threshold": avg_savings >= self._min_savings_pct,
        }

    def identify_quick_wins(self) -> list[dict[str, Any]]:
        """Find optimizations with high savings and low/trivial effort."""
        easy_efforts = {ImplementationEffort.TRIVIAL, ImplementationEffort.LOW}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effort in easy_efforts and r.savings_pct >= self._min_savings_pct:
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "optimization_type": r.optimization_type.value,
                        "savings_pct": r.savings_pct,
                        "estimated_savings_usd": r.estimated_savings_usd,
                        "effort": r.effort.value,
                    }
                )
        results.sort(key=lambda x: x["savings_pct"], reverse=True)
        return results

    def rank_by_savings_potential(self) -> list[dict[str, Any]]:
        """Rank optimizations by estimated savings USD descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "resource_id": r.resource_id,
                    "optimization_type": r.optimization_type.value,
                    "estimated_savings_usd": r.estimated_savings_usd,
                    "savings_pct": r.savings_pct,
                    "priority": r.priority.value,
                }
            )
        results.sort(key=lambda x: x["estimated_savings_usd"], reverse=True)
        return results

    def detect_optimization_trends(self) -> list[dict[str, Any]]:
        """Detect savings trends per resource using sufficient historical data."""
        resource_records: dict[str, list[OptimizationRecord]] = {}
        for r in self._records:
            resource_records.setdefault(r.resource_id, []).append(r)
        results: list[dict[str, Any]] = []
        for rid, recs in resource_records.items():
            if len(recs) > 3:
                savings = [r.savings_pct for r in recs]
                trend = "improving" if savings[-1] > savings[0] else "declining"
                results.append(
                    {
                        "resource_id": rid,
                        "record_count": len(recs),
                        "savings_trend": trend,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> OptimizationPlannerReport:
        by_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_type[r.optimization_type.value] = by_type.get(r.optimization_type.value, 0) + 1
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
        avg_savings = (
            round(sum(r.savings_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        total_usd = round(sum(r.estimated_savings_usd for r in self._records), 2)
        easy_efforts = {ImplementationEffort.TRIVIAL, ImplementationEffort.LOW}
        quick_wins_count = sum(
            1
            for r in self._records
            if r.effort in easy_efforts and r.savings_pct >= self._min_savings_pct
        )
        recs: list[str] = []
        if quick_wins_count > 0:
            recs.append(f"{quick_wins_count} quick win optimization(s) available")
        if total_usd > 0:
            recs.append(f"Total estimated savings: ${total_usd:,.2f}")
        if avg_savings < self._min_savings_pct and self._records:
            recs.append(
                f"Average savings {avg_savings}% below minimum threshold of"
                f" {self._min_savings_pct}%"
            )
        if not recs:
            recs.append("Cost optimization opportunities within expected range")
        return OptimizationPlannerReport(
            total_optimizations=len(self._records),
            total_actions=len(self._actions),
            avg_savings_pct=avg_savings,
            total_estimated_savings_usd=total_usd,
            by_optimization_type=by_type,
            by_priority=by_priority,
            quick_wins_count=quick_wins_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._actions.clear()
        logger.info("optimization_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.optimization_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_optimizations": len(self._records),
            "total_actions": len(self._actions),
            "min_savings_pct": self._min_savings_pct,
            "type_distribution": type_dist,
            "unique_resources": len({r.resource_id for r in self._records}),
        }
