"""Observability Cost Optimizer V2 — advanced cost optimization for observability pipelines."""

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
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    STORAGE = "storage"
    COMPUTE = "compute"
    EGRESS = "egress"


class OptimizationType(StrEnum):
    DOWNSAMPLING = "downsampling"
    TIER_MIGRATION = "tier_migration"
    RETENTION_REDUCTION = "retention_reduction"
    DEDUPLICATION = "deduplication"
    COMPRESSION = "compression"
    SAMPLING = "sampling"


class CostTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    SPIKE = "spike"


# --- Models ---


class CostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: CostCategory = CostCategory.METRICS
    service: str = ""
    cost_usd: float = 0.0
    volume_units: int = 0
    unit_label: str = "events"
    period: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    opt_type: OptimizationType = OptimizationType.DOWNSAMPLING
    category: CostCategory = CostCategory.METRICS
    service: str = ""
    estimated_savings_usd: float = 0.0
    savings_pct: float = 0.0
    effort: str = "low"
    applied: bool = False
    created_at: float = Field(default_factory=time.time)


class CostReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_cost_usd: float = 0.0
    total_records: int = 0
    total_recommendations: int = 0
    potential_savings_usd: float = 0.0
    by_category: dict[str, float] = Field(default_factory=dict)
    cost_trend: CostTrend = CostTrend.STABLE
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityCostOptimizerV2:
    """Advanced cost optimization for observability pipelines."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._costs: list[CostRecord] = []
        self._recommendations: list[OptimizationRecommendation] = []
        logger.info(
            "observability_cost_optimizer_v2.initialized",
            max_records=max_records,
        )

    def add_cost(
        self,
        category: CostCategory,
        service: str,
        cost_usd: float,
        volume_units: int = 0,
        period: str = "",
    ) -> CostRecord:
        """Record a cost entry."""
        record = CostRecord(
            category=category,
            service=service,
            cost_usd=cost_usd,
            volume_units=volume_units,
            period=period,
        )
        self._costs.append(record)
        if len(self._costs) > self._max_records:
            self._costs = self._costs[-self._max_records :]
        logger.info(
            "observability_cost_optimizer_v2.cost_added",
            category=category.value,
            cost_usd=cost_usd,
        )
        return record

    def analyze_costs(self, service: str | None = None) -> dict[str, Any]:
        """Analyze cost distribution."""
        targets = self._costs
        if service:
            targets = [c for c in targets if c.service == service]
        by_cat: dict[str, float] = {}
        for c in targets:
            by_cat[c.category.value] = by_cat.get(c.category.value, 0) + c.cost_usd
        total = sum(by_cat.values())
        return {
            "total_cost_usd": round(total, 2),
            "by_category": {k: round(v, 2) for k, v in by_cat.items()},
            "record_count": len(targets),
            "top_category": max(by_cat, key=lambda k: by_cat[k]) if by_cat else "none",
        }

    def recommend_optimizations(
        self,
        service: str | None = None,
    ) -> list[OptimizationRecommendation]:
        """Generate cost optimization recommendations."""
        targets = self._costs
        if service:
            targets = [c for c in targets if c.service == service]
        cat_costs: dict[str, float] = {}
        for c in targets:
            cat_costs[c.category.value] = cat_costs.get(c.category.value, 0) + c.cost_usd
        new_recs: list[OptimizationRecommendation] = []
        for cat, cost in cat_costs.items():
            if cost > 100:
                savings = round(cost * 0.2, 2)
                rec = OptimizationRecommendation(
                    opt_type=OptimizationType.DOWNSAMPLING,
                    category=CostCategory(cat),
                    service=service or "all",
                    estimated_savings_usd=savings,
                    savings_pct=20.0,
                    effort="medium",
                )
                new_recs.append(rec)
                self._recommendations.append(rec)
            if cost > 500:
                savings = round(cost * 0.15, 2)
                rec = OptimizationRecommendation(
                    opt_type=OptimizationType.TIER_MIGRATION,
                    category=CostCategory(cat),
                    service=service or "all",
                    estimated_savings_usd=savings,
                    savings_pct=15.0,
                    effort="high",
                )
                new_recs.append(rec)
                self._recommendations.append(rec)
        if not new_recs:
            rec = OptimizationRecommendation(
                opt_type=OptimizationType.COMPRESSION,
                service=service or "all",
                estimated_savings_usd=0,
                savings_pct=0,
                effort="low",
            )
            new_recs.append(rec)
            self._recommendations.append(rec)
        return new_recs

    def estimate_savings(self) -> dict[str, Any]:
        """Estimate total potential savings."""
        unapplied = [r for r in self._recommendations if not r.applied]
        total_savings = sum(r.estimated_savings_usd for r in unapplied)
        total_cost = sum(c.cost_usd for c in self._costs)
        pct = round(total_savings / total_cost * 100, 1) if total_cost else 0
        return {
            "total_potential_savings_usd": round(total_savings, 2),
            "total_current_cost_usd": round(total_cost, 2),
            "savings_pct": pct,
            "unapplied_recommendations": len(unapplied),
        }

    def apply_optimization(self, recommendation_id: str) -> dict[str, Any]:
        """Mark an optimization as applied."""
        for r in self._recommendations:
            if r.id == recommendation_id:
                r.applied = True
                logger.info(
                    "observability_cost_optimizer_v2.optimization_applied",
                    id=recommendation_id,
                )
                return {
                    "id": recommendation_id,
                    "status": "applied",
                    "savings_usd": r.estimated_savings_usd,
                }
        return {"id": recommendation_id, "status": "not_found"}

    def get_cost_breakdown(
        self,
        group_by: str = "category",
    ) -> dict[str, Any]:
        """Get cost breakdown by category or service."""
        groups: dict[str, float] = {}
        for c in self._costs:
            key = c.category.value if group_by == "category" else c.service
            groups[key] = groups.get(key, 0) + c.cost_usd
        return {
            "group_by": group_by,
            "breakdown": {k: round(v, 2) for k, v in groups.items()},
            "total_usd": round(sum(groups.values()), 2),
        }

    def generate_report(self) -> CostReport:
        """Generate cost optimization report."""
        by_cat: dict[str, float] = {}
        for c in self._costs:
            by_cat[c.category.value] = by_cat.get(c.category.value, 0) + c.cost_usd
        total = sum(by_cat.values())
        potential = sum(r.estimated_savings_usd for r in self._recommendations if not r.applied)
        # Determine trend
        if len(self._costs) >= 4:
            mid = len(self._costs) // 2
            first = sum(c.cost_usd for c in self._costs[:mid]) / mid
            second = sum(c.cost_usd for c in self._costs[mid:]) / (len(self._costs) - mid)
            if second > first * 1.2:
                trend = CostTrend.INCREASING
            elif second < first * 0.8:
                trend = CostTrend.DECREASING
            else:
                trend = CostTrend.STABLE
        else:
            trend = CostTrend.STABLE
        recs: list[str] = []
        if potential > 0:
            recs.append(
                f"${round(potential, 2)} in potential savings from "
                f"{sum(1 for r in self._recommendations if not r.applied)} recommendation(s)"
            )
        if trend == CostTrend.INCREASING:
            recs.append("Costs trending upward — review usage")
        if not recs:
            recs.append("Observability costs are optimized")
        return CostReport(
            total_cost_usd=round(total, 2),
            total_records=len(self._costs),
            total_recommendations=len(self._recommendations),
            potential_savings_usd=round(potential, 2),
            by_category={k: round(v, 2) for k, v in by_cat.items()},
            cost_trend=trend,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all costs and recommendations."""
        self._costs.clear()
        self._recommendations.clear()
        logger.info("observability_cost_optimizer_v2.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_costs": len(self._costs),
            "total_recommendations": len(self._recommendations),
            "unique_services": len({c.service for c in self._costs}),
            "applied_count": sum(1 for r in self._recommendations if r.applied),
        }
