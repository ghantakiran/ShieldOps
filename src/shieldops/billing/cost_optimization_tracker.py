"""Cost Optimization Tracker — track cost optimization opportunities and savings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OptimizationType(StrEnum):
    RIGHT_SIZING = "right_sizing"
    RESERVED_INSTANCES = "reserved_instances"
    SPOT_USAGE = "spot_usage"
    STORAGE_TIERING = "storage_tiering"
    LICENSE_CONSOLIDATION = "license_consolidation"


class OptimizationStatus(StrEnum):
    IDENTIFIED = "identified"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    EXPIRED = "expired"


class SavingsCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    LICENSING = "licensing"


# --- Models ---


class OptimizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    optimization_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    optimization_status: OptimizationStatus = OptimizationStatus.IDENTIFIED
    savings_category: SavingsCategory = SavingsCategory.COMPUTE
    savings_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    optimization_id: str = ""
    optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostOptimizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    pending_count: int = 0
    avg_savings_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostOptimizationTracker:
    """Track cost optimization opportunities, savings realized, effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        min_savings_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._min_savings_pct = min_savings_pct
        self._records: list[OptimizationRecord] = []
        self._metrics: list[OptimizationMetric] = []
        logger.info(
            "cost_optimization_tracker.initialized",
            max_records=max_records,
            min_savings_pct=min_savings_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_optimization(
        self,
        optimization_id: str,
        optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING,
        optimization_status: OptimizationStatus = OptimizationStatus.IDENTIFIED,
        savings_category: SavingsCategory = SavingsCategory.COMPUTE,
        savings_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> OptimizationRecord:
        record = OptimizationRecord(
            optimization_id=optimization_id,
            optimization_type=optimization_type,
            optimization_status=optimization_status,
            savings_category=savings_category,
            savings_pct=savings_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_optimization_tracker.optimization_recorded",
            record_id=record.id,
            optimization_id=optimization_id,
            optimization_type=optimization_type.value,
            optimization_status=optimization_status.value,
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
        optimization_status: OptimizationStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[OptimizationRecord]:
        results = list(self._records)
        if optimization_type is not None:
            results = [r for r in results if r.optimization_type == optimization_type]
        if optimization_status is not None:
            results = [r for r in results if r.optimization_status == optimization_status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        optimization_id: str,
        optimization_type: OptimizationType = OptimizationType.RIGHT_SIZING,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> OptimizationMetric:
        metric = OptimizationMetric(
            optimization_id=optimization_id,
            optimization_type=optimization_type,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "cost_optimization_tracker.metric_added",
            optimization_id=optimization_id,
            optimization_type=optimization_type.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_optimization_distribution(self) -> dict[str, Any]:
        """Group by optimization_type; return count and avg savings_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.optimization_type.value
            type_data.setdefault(key, []).append(r.savings_pct)
        result: dict[str, Any] = {}
        for otype, scores in type_data.items():
            result[otype] = {
                "count": len(scores),
                "avg_savings_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_pending_optimizations(self) -> list[dict[str, Any]]:
        """Return records where status is IDENTIFIED or IN_PROGRESS."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.optimization_status in (
                OptimizationStatus.IDENTIFIED,
                OptimizationStatus.IN_PROGRESS,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "optimization_id": r.optimization_id,
                        "optimization_status": r.optimization_status.value,
                        "savings_pct": r.savings_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_savings(self) -> list[dict[str, Any]]:
        """Group by service, avg savings_pct, sort descending."""
        svc_savings: dict[str, list[float]] = {}
        for r in self._records:
            svc_savings.setdefault(r.service, []).append(r.savings_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_savings.items():
            results.append(
                {
                    "service": svc,
                    "avg_savings_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_savings_pct"], reverse=True)
        return results

    def detect_optimization_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CostOptimizationReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_type[r.optimization_type.value] = by_type.get(r.optimization_type.value, 0) + 1
            by_status[r.optimization_status.value] = (
                by_status.get(r.optimization_status.value, 0) + 1
            )
            by_category[r.savings_category.value] = by_category.get(r.savings_category.value, 0) + 1
        pending_count = sum(
            1
            for r in self._records
            if r.optimization_status
            in (
                OptimizationStatus.IDENTIFIED,
                OptimizationStatus.IN_PROGRESS,
            )
        )
        savings = [r.savings_pct for r in self._records]
        avg_savings_pct = round(sum(savings) / len(savings), 2) if savings else 0.0
        pending_list = self.identify_pending_optimizations()
        top_opportunities = [o["optimization_id"] for o in pending_list[:5]]
        recs: list[str] = []
        if self._records and avg_savings_pct < self._min_savings_pct:
            recs.append(
                f"Avg savings {avg_savings_pct}% below threshold ({self._min_savings_pct}%)"
            )
        if pending_count > 0:
            recs.append(f"{pending_count} pending optimization(s) — prioritize implementation")
        if not recs:
            recs.append("Cost optimization levels are healthy")
        return CostOptimizationReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            pending_count=pending_count,
            avg_savings_pct=avg_savings_pct,
            by_type=by_type,
            by_status=by_status,
            by_category=by_category,
            top_opportunities=top_opportunities,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("cost_optimization_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.optimization_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_savings_pct": self._min_savings_pct,
            "optimization_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
