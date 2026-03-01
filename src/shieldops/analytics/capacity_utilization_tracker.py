"""Capacity Utilization Tracker — track resource utilization efficiency, detect waste."""

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
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"


class UtilizationLevel(StrEnum):
    OVER_UTILIZED = "over_utilized"
    OPTIMAL = "optimal"
    UNDER_UTILIZED = "under_utilized"
    IDLE = "idle"
    UNKNOWN = "unknown"


class AllocationStrategy(StrEnum):
    RESERVED = "reserved"
    ON_DEMAND = "on_demand"
    SPOT = "spot"
    BURSTABLE = "burstable"
    DEDICATED = "dedicated"


# --- Models ---


class UtilizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.CPU
    utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN
    allocation_strategy: AllocationStrategy = AllocationStrategy.ON_DEMAND
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UtilizationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.CPU
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityUtilizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    waste_count: int = 0
    avg_utilization_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_wasteful: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityUtilizationTracker:
    """Track resource utilization efficiency, detect waste."""

    def __init__(
        self,
        max_records: int = 200000,
        min_utilization_pct: float = 40.0,
    ) -> None:
        self._max_records = max_records
        self._min_utilization_pct = min_utilization_pct
        self._records: list[UtilizationRecord] = []
        self._metrics: list[UtilizationMetric] = []
        logger.info(
            "capacity_utilization_tracker.initialized",
            max_records=max_records,
            min_utilization_pct=min_utilization_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_utilization(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.CPU,
        utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN,
        allocation_strategy: AllocationStrategy = AllocationStrategy.ON_DEMAND,
        utilization_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> UtilizationRecord:
        record = UtilizationRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            utilization_level=utilization_level,
            allocation_strategy=allocation_strategy,
            utilization_pct=utilization_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_utilization_tracker.utilization_recorded",
            record_id=record.id,
            resource_id=resource_id,
            resource_type=resource_type.value,
            utilization_level=utilization_level.value,
        )
        return record

    def get_utilization(self, record_id: str) -> UtilizationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_utilizations(
        self,
        resource_type: ResourceType | None = None,
        level: UtilizationLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[UtilizationRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if level is not None:
            results = [r for r in results if r.utilization_level == level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.CPU,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> UtilizationMetric:
        metric = UtilizationMetric(
            resource_id=resource_id,
            resource_type=resource_type,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "capacity_utilization_tracker.metric_added",
            resource_id=resource_id,
            resource_type=resource_type.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_utilization_distribution(self) -> dict[str, Any]:
        """Group by resource_type; return count and avg utilization_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.resource_type.value
            type_data.setdefault(key, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_utilization_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_wasteful_resources(self) -> list[dict[str, Any]]:
        """Return records where utilization_level is IDLE or UNDER_UTILIZED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_level in (
                UtilizationLevel.IDLE,
                UtilizationLevel.UNDER_UTILIZED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "resource_id": r.resource_id,
                        "utilization_level": r.utilization_level.value,
                        "utilization_pct": r.utilization_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, avg utilization_pct, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_utilization_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"])
        return results

    def detect_utilization_trends(self) -> dict[str, Any]:
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
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CapacityUtilizationReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_type[r.resource_type.value] = by_type.get(r.resource_type.value, 0) + 1
            by_level[r.utilization_level.value] = by_level.get(r.utilization_level.value, 0) + 1
            by_strategy[r.allocation_strategy.value] = (
                by_strategy.get(r.allocation_strategy.value, 0) + 1
            )
        waste_count = sum(
            1
            for r in self._records
            if r.utilization_level in (UtilizationLevel.IDLE, UtilizationLevel.UNDER_UTILIZED)
        )
        scores = [r.utilization_pct for r in self._records]
        avg_utilization_pct = round(sum(scores) / len(scores), 2) if scores else 0.0
        wasteful_list = self.identify_wasteful_resources()
        top_wasteful = [w["resource_id"] for w in wasteful_list[:5]]
        recs: list[str] = []
        if self._records and avg_utilization_pct < self._min_utilization_pct:
            recs.append(
                f"Avg utilization {avg_utilization_pct}% below threshold "
                f"({self._min_utilization_pct}%)"
            )
        if waste_count > 0:
            recs.append(f"{waste_count} wasteful resource(s) — optimize allocation")
        if not recs:
            recs.append("Capacity utilization levels are healthy")
        return CapacityUtilizationReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            waste_count=waste_count,
            avg_utilization_pct=avg_utilization_pct,
            by_type=by_type,
            by_level=by_level,
            by_strategy=by_strategy,
            top_wasteful=top_wasteful,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("capacity_utilization_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_utilization_pct": self._min_utilization_pct,
            "resource_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
