"""Infrastructure Cost Estimator
estimate plan cost impact, detect cost surprises,
rank changes by cost delta."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostImpact(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class EstimationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class PricingModel(StrEnum):
    ON_DEMAND = "on_demand"
    RESERVED = "reserved"
    SPOT = "spot"
    COMMITTED = "committed"


# --- Models ---


class CostEstimationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    resource_name: str = ""
    cost_impact: CostImpact = CostImpact.NEUTRAL
    estimation_confidence: EstimationConfidence = EstimationConfidence.MEDIUM
    pricing_model: PricingModel = PricingModel.ON_DEMAND
    estimated_monthly_cost: float = 0.0
    cost_delta: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostEstimationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    computed_cost: float = 0.0
    cost_impact: CostImpact = CostImpact.NEUTRAL
    is_surprise: bool = False
    confidence: EstimationConfidence = EstimationConfidence.MEDIUM
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostEstimationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_cost_delta: float = 0.0
    by_cost_impact: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_pricing_model: dict[str, int] = Field(default_factory=dict)
    costly_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureCostEstimator:
    """Estimate plan cost impact, detect cost
    surprises, rank changes by cost delta."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CostEstimationRecord] = []
        self._analyses: dict[str, CostEstimationAnalysis] = {}
        logger.info(
            "infrastructure_cost_estimator.init",
            max_records=max_records,
        )

    def add_record(
        self,
        change_id: str = "",
        resource_name: str = "",
        cost_impact: CostImpact = CostImpact.NEUTRAL,
        estimation_confidence: EstimationConfidence = (EstimationConfidence.MEDIUM),
        pricing_model: PricingModel = (PricingModel.ON_DEMAND),
        estimated_monthly_cost: float = 0.0,
        cost_delta: float = 0.0,
        description: str = "",
    ) -> CostEstimationRecord:
        record = CostEstimationRecord(
            change_id=change_id,
            resource_name=resource_name,
            cost_impact=cost_impact,
            estimation_confidence=estimation_confidence,
            pricing_model=pricing_model,
            estimated_monthly_cost=(estimated_monthly_cost),
            cost_delta=cost_delta,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_estimation.record_added",
            record_id=record.id,
            change_id=change_id,
        )
        return record

    def process(self, key: str) -> CostEstimationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_surprise = abs(rec.cost_delta) > 100.0
        analysis = CostEstimationAnalysis(
            change_id=rec.change_id,
            computed_cost=round(rec.estimated_monthly_cost, 2),
            cost_impact=rec.cost_impact,
            is_surprise=is_surprise,
            confidence=rec.estimation_confidence,
            description=(f"Change {rec.change_id} delta {rec.cost_delta}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> CostEstimationReport:
        by_ci: dict[str, int] = {}
        by_co: dict[str, int] = {}
        by_pm: dict[str, int] = {}
        deltas: list[float] = []
        for r in self._records:
            k = r.cost_impact.value
            by_ci[k] = by_ci.get(k, 0) + 1
            k2 = r.estimation_confidence.value
            by_co[k2] = by_co.get(k2, 0) + 1
            k3 = r.pricing_model.value
            by_pm[k3] = by_pm.get(k3, 0) + 1
            deltas.append(r.cost_delta)
        avg = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
        costly = list(
            {
                r.change_id
                for r in self._records
                if r.cost_impact == CostImpact.INCREASE and r.cost_delta > 100
            }
        )[:10]
        recs: list[str] = []
        if costly:
            recs.append(f"{len(costly)} costly changes detected")
        if not recs:
            recs.append("No significant cost impacts")
        return CostEstimationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_cost_delta=avg,
            by_cost_impact=by_ci,
            by_confidence=by_co,
            by_pricing_model=by_pm,
            costly_changes=costly,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ci_dist: dict[str, int] = {}
        for r in self._records:
            k = r.cost_impact.value
            ci_dist[k] = ci_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cost_impact_distribution": ci_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("infrastructure_cost_estimator.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def estimate_plan_cost_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Estimate cost impact per change."""
        change_costs: dict[str, list[float]] = {}
        change_deltas: dict[str, list[float]] = {}
        for r in self._records:
            change_costs.setdefault(r.change_id, []).append(r.estimated_monthly_cost)
            change_deltas.setdefault(r.change_id, []).append(r.cost_delta)
        results: list[dict[str, Any]] = []
        for cid, costs in change_costs.items():
            total_cost = round(sum(costs), 2)
            total_delta = round(sum(change_deltas[cid]), 2)
            results.append(
                {
                    "change_id": cid,
                    "total_monthly_cost": total_cost,
                    "total_delta": total_delta,
                    "resource_count": len(costs),
                }
            )
        results.sort(
            key=lambda x: x["total_delta"],
            reverse=True,
        )
        return results

    def detect_cost_surprises(
        self,
    ) -> list[dict[str, Any]]:
        """Detect unexpected cost changes."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if abs(r.cost_delta) > 100.0:
                results.append(
                    {
                        "change_id": r.change_id,
                        "resource_name": (r.resource_name),
                        "cost_delta": r.cost_delta,
                        "impact": (r.cost_impact.value),
                        "confidence": (r.estimation_confidence.value),
                    }
                )
        results.sort(
            key=lambda x: abs(x["cost_delta"]),
            reverse=True,
        )
        return results

    def rank_changes_by_cost_delta(
        self,
    ) -> list[dict[str, Any]]:
        """Rank changes by aggregate cost delta."""
        change_data: dict[str, float] = {}
        for r in self._records:
            change_data[r.change_id] = change_data.get(r.change_id, 0.0) + r.cost_delta
        results: list[dict[str, Any]] = []
        for cid, total in change_data.items():
            results.append(
                {
                    "change_id": cid,
                    "aggregate_delta": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: abs(x["aggregate_delta"]),
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
