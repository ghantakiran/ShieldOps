"""Performance Capacity Correlation Engine
compute capacity-performance correlation, detect capacity
driven degradation, rank resources by performance sensitivity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class CapacityMetric(StrEnum):
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_PRESSURE = "memory_pressure"
    DISK_IO = "disk_io"
    NETWORK_BANDWIDTH = "network_bandwidth"


class PerformanceMetric(StrEnum):
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"


# --- Models ---


class PerformanceCapacityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    correlation_strength: CorrelationStrength = CorrelationStrength.WEAK
    capacity_metric: CapacityMetric = CapacityMetric.CPU_UTILIZATION
    performance_metric: PerformanceMetric = PerformanceMetric.LATENCY
    capacity_value: float = 0.0
    performance_value: float = 0.0
    correlation_coefficient: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceCapacityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    computed_correlation: float = 0.0
    correlation_strength: CorrelationStrength = CorrelationStrength.WEAK
    capacity_driven: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceCapacityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_correlation: float = 0.0
    by_correlation_strength: dict[str, int] = Field(default_factory=dict)
    by_capacity_metric: dict[str, int] = Field(default_factory=dict)
    by_performance_metric: dict[str, int] = Field(default_factory=dict)
    strongly_correlated: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PerformanceCapacityCorrelationEngine:
    """Compute capacity-performance correlation, detect
    capacity driven degradation, rank by sensitivity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PerformanceCapacityRecord] = []
        self._analyses: dict[str, PerformanceCapacityAnalysis] = {}
        logger.info(
            "performance_capacity_correlation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        resource_id: str = "",
        correlation_strength: CorrelationStrength = CorrelationStrength.WEAK,
        capacity_metric: CapacityMetric = CapacityMetric.CPU_UTILIZATION,
        performance_metric: PerformanceMetric = PerformanceMetric.LATENCY,
        capacity_value: float = 0.0,
        performance_value: float = 0.0,
        correlation_coefficient: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> PerformanceCapacityRecord:
        record = PerformanceCapacityRecord(
            resource_id=resource_id,
            correlation_strength=correlation_strength,
            capacity_metric=capacity_metric,
            performance_metric=performance_metric,
            capacity_value=capacity_value,
            performance_value=performance_value,
            correlation_coefficient=correlation_coefficient,
            service=service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "performance_capacity_correlation_engine.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> PerformanceCapacityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.resource_id == rec.resource_id)
        capacity_driven = rec.correlation_strength in (
            CorrelationStrength.STRONG,
            CorrelationStrength.MODERATE,
        )
        analysis = PerformanceCapacityAnalysis(
            resource_id=rec.resource_id,
            computed_correlation=round(rec.correlation_coefficient, 2),
            correlation_strength=rec.correlation_strength,
            capacity_driven=capacity_driven,
            data_points=points,
            description=f"Resource {rec.resource_id} correlation {rec.correlation_coefficient}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PerformanceCapacityReport:
        by_cs: dict[str, int] = {}
        by_cm: dict[str, int] = {}
        by_pm: dict[str, int] = {}
        corrs: list[float] = []
        for r in self._records:
            k = r.correlation_strength.value
            by_cs[k] = by_cs.get(k, 0) + 1
            k2 = r.capacity_metric.value
            by_cm[k2] = by_cm.get(k2, 0) + 1
            k3 = r.performance_metric.value
            by_pm[k3] = by_pm.get(k3, 0) + 1
            corrs.append(r.correlation_coefficient)
        avg = round(sum(corrs) / len(corrs), 2) if corrs else 0.0
        strong = list(
            {
                r.resource_id
                for r in self._records
                if r.correlation_strength == CorrelationStrength.STRONG
            }
        )[:10]
        recs: list[str] = []
        if strong:
            recs.append(f"{len(strong)} resources with strong capacity-performance correlation")
        if not recs:
            recs.append("No strong capacity-performance correlations detected")
        return PerformanceCapacityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_correlation=avg,
            by_correlation_strength=by_cs,
            by_capacity_metric=by_cm,
            by_performance_metric=by_pm,
            strongly_correlated=strong,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.correlation_strength.value
            cs_dist[k] = cs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "correlation_strength_distribution": cs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("performance_capacity_correlation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_capacity_performance_correlation(
        self,
    ) -> list[dict[str, Any]]:
        """Compute capacity-performance correlation per resource."""
        res_data: dict[str, list[float]] = {}
        res_metrics: dict[str, str] = {}
        for r in self._records:
            res_data.setdefault(r.resource_id, []).append(r.correlation_coefficient)
            res_metrics[r.resource_id] = r.capacity_metric.value
        results: list[dict[str, Any]] = []
        for rid, corrs in res_data.items():
            avg = round(sum(corrs) / len(corrs), 2)
            results.append(
                {
                    "resource_id": rid,
                    "capacity_metric": res_metrics[rid],
                    "avg_correlation": avg,
                    "data_points": len(corrs),
                }
            )
        results.sort(key=lambda x: abs(x["avg_correlation"]), reverse=True)
        return results

    def detect_capacity_driven_degradation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect resources with capacity-driven degradation."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.correlation_strength in (CorrelationStrength.STRONG, CorrelationStrength.MODERATE)
                and r.resource_id not in seen
            ):
                seen.add(r.resource_id)
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "capacity_metric": r.capacity_metric.value,
                        "performance_metric": r.performance_metric.value,
                        "correlation_coefficient": r.correlation_coefficient,
                        "strength": r.correlation_strength.value,
                    }
                )
        results.sort(key=lambda x: abs(x["correlation_coefficient"]), reverse=True)
        return results

    def rank_resources_by_performance_sensitivity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all resources by performance sensitivity."""
        res_data: dict[str, list[float]] = {}
        res_metrics: dict[str, str] = {}
        for r in self._records:
            res_data.setdefault(r.resource_id, []).append(abs(r.correlation_coefficient))
            res_metrics[r.resource_id] = r.capacity_metric.value
        results: list[dict[str, Any]] = []
        for rid, corrs in res_data.items():
            avg = round(sum(corrs) / len(corrs), 2)
            results.append(
                {
                    "resource_id": rid,
                    "capacity_metric": res_metrics[rid],
                    "avg_sensitivity": avg,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_sensitivity"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
