"""Model Inference Cost Tracker — track and optimize ML model inference costs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InferenceType(StrEnum):
    BATCH = "batch"
    REALTIME = "realtime"
    STREAMING = "streaming"
    EDGE = "edge"
    SERVERLESS = "serverless"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"
    API_CALLS = "api_calls"


class OptimizationStatus(StrEnum):
    OPTIMIZED = "optimized"
    NEEDS_OPTIMIZATION = "needs_optimization"
    IN_PROGRESS = "in_progress"
    REVIEWED = "reviewed"
    SKIPPED = "skipped"


# --- Models ---


class InferenceCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    inference_type: InferenceType = InferenceType.REALTIME
    cost_category: CostCategory = CostCategory.COMPUTE
    optimization_status: OptimizationStatus = OptimizationStatus.NEEDS_OPTIMIZATION
    cost_usd: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    inference_type: InferenceType = InferenceType.REALTIME
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InferenceCostReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    overspend_count: int = 0
    avg_cost_usd: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_costly: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelInferenceCostTracker:
    """Track and optimize ML model inference costs."""

    def __init__(
        self,
        max_records: int = 200000,
        cost_threshold_usd: float = 100.0,
    ) -> None:
        self._max_records = max_records
        self._cost_threshold_usd = cost_threshold_usd
        self._records: list[InferenceCostRecord] = []
        self._analyses: list[CostAnalysis] = []
        logger.info(
            "model_inference_cost_tracker.initialized",
            max_records=max_records,
            cost_threshold_usd=cost_threshold_usd,
        )

    # -- record / get / list ------------------------------------------------

    def record_cost(
        self,
        model_id: str,
        inference_type: InferenceType = InferenceType.REALTIME,
        cost_category: CostCategory = CostCategory.COMPUTE,
        optimization_status: OptimizationStatus = OptimizationStatus.NEEDS_OPTIMIZATION,
        cost_usd: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> InferenceCostRecord:
        record = InferenceCostRecord(
            model_id=model_id,
            inference_type=inference_type,
            cost_category=cost_category,
            optimization_status=optimization_status,
            cost_usd=cost_usd,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_inference_cost_tracker.cost_recorded",
            record_id=record.id,
            model_id=model_id,
            inference_type=inference_type.value,
            cost_usd=cost_usd,
        )
        return record

    def get_cost(self, record_id: str) -> InferenceCostRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_costs(
        self,
        inference_type: InferenceType | None = None,
        optimization_status: OptimizationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InferenceCostRecord]:
        results = list(self._records)
        if inference_type is not None:
            results = [r for r in results if r.inference_type == inference_type]
        if optimization_status is not None:
            results = [r for r in results if r.optimization_status == optimization_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        inference_type: InferenceType = InferenceType.REALTIME,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CostAnalysis:
        analysis = CostAnalysis(
            model_id=model_id,
            inference_type=inference_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_inference_cost_tracker.analysis_added",
            model_id=model_id,
            inference_type=inference_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by inference_type; return count and avg cost_usd."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.inference_type.value
            type_data.setdefault(key, []).append(r.cost_usd)
        result: dict[str, Any] = {}
        for itype, costs in type_data.items():
            result[itype] = {
                "count": len(costs),
                "avg_cost_usd": round(sum(costs) / len(costs), 4),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where cost_usd > cost_threshold_usd."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cost_usd > self._cost_threshold_usd:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "inference_type": r.inference_type.value,
                        "cost_usd": r.cost_usd,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cost_usd"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg cost_usd, sort descending."""
        model_costs: dict[str, list[float]] = {}
        for r in self._records:
            model_costs.setdefault(r.model_id, []).append(r.cost_usd)
        results: list[dict[str, Any]] = []
        for model_id, costs in model_costs.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_cost_usd": round(sum(costs) / len(costs), 4),
                }
            )
        results.sort(key=lambda x: x["avg_cost_usd"], reverse=True)
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> InferenceCostReport:
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.inference_type.value] = by_type.get(r.inference_type.value, 0) + 1
            by_category[r.cost_category.value] = by_category.get(r.cost_category.value, 0) + 1
            by_status[r.optimization_status.value] = (
                by_status.get(r.optimization_status.value, 0) + 1
            )
        overspend_count = sum(1 for r in self._records if r.cost_usd > self._cost_threshold_usd)
        costs = [r.cost_usd for r in self._records]
        avg_cost_usd = round(sum(costs) / len(costs), 4) if costs else 0.0
        costly_list = self.identify_severe_drifts()
        top_costly = [o["model_id"] for o in costly_list[:5]]
        recs: list[str] = []
        if self._records and overspend_count > 0:
            recs.append(
                f"{overspend_count} model(s) exceeding cost threshold (${self._cost_threshold_usd})"
            )
        if self._records and avg_cost_usd > self._cost_threshold_usd:
            recs.append(
                f"Avg inference cost ${avg_cost_usd} exceeds threshold "
                f"(${self._cost_threshold_usd})"
            )
        if not recs:
            recs.append("Inference costs are within acceptable bounds")
        return InferenceCostReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            overspend_count=overspend_count,
            avg_cost_usd=avg_cost_usd,
            by_type=by_type,
            by_category=by_category,
            by_status=by_status,
            top_costly=top_costly,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_inference_cost_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.inference_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cost_threshold_usd": self._cost_threshold_usd,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
