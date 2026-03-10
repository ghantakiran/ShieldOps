"""ObservabilityRoiOptimizer — ROI optimization engine."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalValue(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CostCategory(StrEnum):
    INGESTION = "ingestion"
    STORAGE = "storage"
    QUERY = "query"
    EXPORT = "export"


class OptimizationAction(StrEnum):
    DOWNSAMPLE = "downsample"
    AGGREGATE = "aggregate"
    ARCHIVE = "archive"
    DROP = "drop"


# --- Models ---


class RoiRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_value: SignalValue = SignalValue.MEDIUM
    cost_category: CostCategory = CostCategory.INGESTION
    optimization_action: OptimizationAction = OptimizationAction.DOWNSAMPLE
    score: float = 0.0
    monthly_cost_usd: float = 0.0
    usage_frequency: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RoiAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_value: SignalValue = SignalValue.MEDIUM
    analysis_score: float = 0.0
    roi_ratio: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RoiReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    total_monthly_cost: float = 0.0
    by_signal_value: dict[str, int] = Field(default_factory=dict)
    by_cost_category: dict[str, int] = Field(default_factory=dict)
    by_optimization_action: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityRoiOptimizer:
    """Observability ROI Optimizer.

    Analyzes the return on investment for
    observability signals and recommends
    cost-effective optimizations.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RoiRecord] = []
        self._analyses: list[RoiAnalysis] = []
        logger.info(
            "observability_roi_optimizer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        signal_value: SignalValue = SignalValue.MEDIUM,
        cost_category: CostCategory = (CostCategory.INGESTION),
        optimization_action: OptimizationAction = (OptimizationAction.DOWNSAMPLE),
        score: float = 0.0,
        monthly_cost_usd: float = 0.0,
        usage_frequency: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RoiRecord:
        record = RoiRecord(
            name=name,
            signal_value=signal_value,
            cost_category=cost_category,
            optimization_action=optimization_action,
            score=score,
            monthly_cost_usd=monthly_cost_usd,
            usage_frequency=usage_frequency,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "observability_roi_optimizer.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        costs = [r.monthly_cost_usd for r in matching]
        total_cost = round(sum(costs), 2)
        roi = round(avg / total_cost, 2) if total_cost > 0 else 0.0
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "total_cost_usd": total_cost,
            "roi_ratio": roi,
        }

    def generate_report(self) -> RoiReport:
        by_sv: dict[str, int] = {}
        by_cc: dict[str, int] = {}
        by_oa: dict[str, int] = {}
        for r in self._records:
            v1 = r.signal_value.value
            by_sv[v1] = by_sv.get(v1, 0) + 1
            v2 = r.cost_category.value
            by_cc[v2] = by_cc.get(v2, 0) + 1
            v3 = r.optimization_action.value
            by_oa[v3] = by_oa.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        total_cost = round(
            sum(r.monthly_cost_usd for r in self._records),
            2,
        )
        recs: list[str] = []
        low_roi = sum(
            1
            for r in self._records
            if r.signal_value == SignalValue.LOW and r.monthly_cost_usd > 100
        )
        if low_roi > 0:
            recs.append(f"{low_roi} low-value signal(s) with high cost")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg ROI score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Observability ROI is healthy")
        return RoiReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            total_monthly_cost=total_cost,
            by_signal_value=by_sv,
            by_cost_category=by_cc,
            by_optimization_action=by_oa,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sv_dist: dict[str, int] = {}
        for r in self._records:
            k = r.signal_value.value
            sv_dist[k] = sv_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "signal_value_distribution": sv_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("observability_roi_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def compute_signal_roi(self) -> dict[str, Any]:
        """Compute ROI for each signal."""
        if not self._records:
            return {"status": "no_data"}
        svc_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.service not in svc_data:
                svc_data[r.service] = {
                    "total_score": 0.0,
                    "total_cost": 0.0,
                    "count": 0,
                }
            svc_data[r.service]["total_score"] += r.score
            svc_data[r.service]["total_cost"] += r.monthly_cost_usd
            svc_data[r.service]["count"] += 1
        results: dict[str, Any] = {}
        for svc, data in svc_data.items():
            cost = data["total_cost"]
            avg_score = round(data["total_score"] / data["count"], 2)
            roi = round(avg_score / cost, 4) if cost > 0 else 0.0
            results[svc] = {
                "avg_score": avg_score,
                "total_cost": round(cost, 2),
                "roi_ratio": roi,
                "record_count": int(data["count"]),
            }
        return results

    def identify_wasteful_signals(
        self,
    ) -> list[dict[str, Any]]:
        """Identify signals with low value, high cost."""
        wasteful: list[dict[str, Any]] = []
        for r in self._records:
            value_score = {
                SignalValue.CRITICAL: 4,
                SignalValue.HIGH: 3,
                SignalValue.MEDIUM: 2,
                SignalValue.LOW: 1,
            }.get(r.signal_value, 1)
            cost_per_value = (
                round(r.monthly_cost_usd / value_score, 2)
                if value_score > 0
                else r.monthly_cost_usd
            )
            if cost_per_value > 50.0 or r.usage_frequency < 0.1:
                wasteful.append(
                    {
                        "name": r.name,
                        "service": r.service,
                        "signal_value": (r.signal_value.value),
                        "monthly_cost": (r.monthly_cost_usd),
                        "cost_per_value": cost_per_value,
                        "usage_frequency": (r.usage_frequency),
                        "recommended_action": (r.optimization_action.value),
                    }
                )
        wasteful.sort(
            key=lambda x: x["cost_per_value"],
            reverse=True,
        )
        return wasteful

    def recommend_budget_allocation(
        self,
    ) -> dict[str, Any]:
        """Recommend budget allocation by category."""
        if not self._records:
            return {"status": "no_data"}
        cat_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            cat = r.cost_category.value
            if cat not in cat_data:
                cat_data[cat] = {
                    "total_cost": 0.0,
                    "total_score": 0.0,
                    "count": 0,
                }
            cat_data[cat]["total_cost"] += r.monthly_cost_usd
            cat_data[cat]["total_score"] += r.score
            cat_data[cat]["count"] += 1
        total = sum(d["total_cost"] for d in cat_data.values())
        allocation: dict[str, Any] = {}
        for cat, data in cat_data.items():
            pct = round(data["total_cost"] / total * 100, 1) if total > 0 else 0.0
            avg_s = round(data["total_score"] / data["count"], 2)
            allocation[cat] = {
                "current_pct": pct,
                "current_cost": round(data["total_cost"], 2),
                "avg_score": avg_s,
            }
        return {
            "total_budget": round(total, 2),
            "allocation": allocation,
        }
