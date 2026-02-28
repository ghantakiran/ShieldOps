"""Capacity Utilization Scorer — score and analyze resource utilization across environments."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

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


class UtilizationGrade(StrEnum):
    OPTIMAL = "optimal"
    GOOD = "good"
    UNDERUTILIZED = "underutilized"
    OVER_PROVISIONED = "over_provisioned"
    CRITICAL = "critical"


class UtilizationTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class UtilizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    utilization_pct: float = 0.0
    grade: UtilizationGrade = UtilizationGrade.GOOD
    trend: UtilizationTrend = UtilizationTrend.INSUFFICIENT_DATA
    environment: str = ""
    created_at: float = Field(default_factory=time.time)


class UtilizationMetric(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    metric_name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    threshold_pct: float = 0.0
    sample_window_minutes: int = 60
    environment: str = ""
    created_at: float = Field(default_factory=time.time)


class UtilizationScorerReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_metrics: int = 0
    avg_utilization_pct: float = 0.0
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    over_provisioned_count: int = 0
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityUtilizationScorer:
    """Score and analyze resource utilization across environments."""

    def __init__(
        self,
        max_records: int = 200000,
        optimal_utilization_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._optimal_utilization_pct = optimal_utilization_pct
        self._records: list[UtilizationRecord] = []
        self._metrics: list[UtilizationMetric] = []
        logger.info(
            "utilization_scorer.initialized",
            max_records=max_records,
            optimal_utilization_pct=optimal_utilization_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_utilization(
        self,
        resource_name: str,
        resource_type: ResourceType = ResourceType.CPU,
        utilization_pct: float = 0.0,
        grade: UtilizationGrade = UtilizationGrade.GOOD,
        trend: UtilizationTrend = UtilizationTrend.INSUFFICIENT_DATA,
        environment: str = "",
    ) -> UtilizationRecord:
        record = UtilizationRecord(
            resource_name=resource_name,
            resource_type=resource_type,
            utilization_pct=utilization_pct,
            grade=grade,
            trend=trend,
            environment=environment,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "utilization_scorer.utilization_recorded",
            record_id=record.id,
            resource_name=resource_name,
            resource_type=resource_type.value,
            utilization_pct=utilization_pct,
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
        grade: UtilizationGrade | None = None,
        limit: int = 50,
    ) -> list[UtilizationRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if grade is not None:
            results = [r for r in results if r.grade == grade]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        resource_type: ResourceType = ResourceType.CPU,
        threshold_pct: float = 0.0,
        sample_window_minutes: int = 60,
        environment: str = "",
    ) -> UtilizationMetric:
        metric = UtilizationMetric(
            metric_name=metric_name,
            resource_type=resource_type,
            threshold_pct=threshold_pct,
            sample_window_minutes=sample_window_minutes,
            environment=environment,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "utilization_scorer.metric_added",
            metric_name=metric_name,
            resource_type=resource_type.value,
            threshold_pct=threshold_pct,
        )
        return metric

    # -- domain operations -----------------------------------------------

    def analyze_utilization_by_resource(self, resource_type: ResourceType) -> dict[str, Any]:
        """Analyze utilization stats for a specific resource type."""
        records = [r for r in self._records if r.resource_type == resource_type]
        if not records:
            return {"resource_type": resource_type.value, "status": "no_data"}
        avg_util = round(sum(r.utilization_pct for r in records) / len(records), 2)
        return {
            "resource_type": resource_type.value,
            "record_count": len(records),
            "avg_utilization_pct": avg_util,
            "near_optimal": abs(avg_util - self._optimal_utilization_pct) <= 10.0,
        }

    def identify_over_provisioned(self) -> list[dict[str, Any]]:
        """Find resources with OVER_PROVISIONED or UNDERUTILIZED grade."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.grade in (UtilizationGrade.OVER_PROVISIONED, UtilizationGrade.UNDERUTILIZED):
                results.append(
                    {
                        "record_id": r.id,
                        "resource_name": r.resource_name,
                        "resource_type": r.resource_type.value,
                        "utilization_pct": r.utilization_pct,
                        "grade": r.grade.value,
                        "environment": r.environment,
                    }
                )
        results.sort(key=lambda x: x["utilization_pct"])
        return results

    def rank_by_utilization_score(self) -> list[dict[str, Any]]:
        """Rank resources by utilization percentage descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "resource_name": r.resource_name,
                    "resource_type": r.resource_type.value,
                    "utilization_pct": r.utilization_pct,
                    "grade": r.grade.value,
                }
            )
        results.sort(key=lambda x: x["utilization_pct"], reverse=True)
        return results

    def detect_utilization_trends(self) -> list[dict[str, Any]]:
        """Detect resource types with VOLATILE or INCREASING trends."""
        resource_trends: dict[str, dict[str, int]] = {}
        for r in self._records:
            rt = r.resource_type.value
            resource_trends.setdefault(rt, {})
            resource_trends[rt][r.trend.value] = resource_trends[rt].get(r.trend.value, 0) + 1
        results: list[dict[str, Any]] = []
        for rt, trend_counts in resource_trends.items():
            volatile = trend_counts.get(UtilizationTrend.VOLATILE.value, 0)
            increasing = trend_counts.get(UtilizationTrend.INCREASING.value, 0)
            if volatile > 0 or increasing > 1:
                results.append(
                    {
                        "resource_type": rt,
                        "volatile_count": volatile,
                        "increasing_count": increasing,
                        "attention_required": True,
                    }
                )
        results.sort(key=lambda x: x["volatile_count"] + x["increasing_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> UtilizationScorerReport:
        by_resource_type: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        total_util = 0.0
        for r in self._records:
            by_resource_type[r.resource_type.value] = (
                by_resource_type.get(r.resource_type.value, 0) + 1
            )
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
            total_util += r.utilization_pct
        avg_util = round(total_util / len(self._records), 2) if self._records else 0.0
        over_provisioned_count = sum(
            1
            for r in self._records
            if r.grade in (UtilizationGrade.OVER_PROVISIONED, UtilizationGrade.UNDERUTILIZED)
        )
        critical_count = sum(1 for r in self._records if r.grade == UtilizationGrade.CRITICAL)
        recs: list[str] = []
        if over_provisioned_count > 0:
            recs.append(
                f"{over_provisioned_count} resource(s) are over-provisioned or underutilized"
            )
        if critical_count > 0:
            recs.append(f"{critical_count} resource(s) have critical utilization levels")
        if self._records and abs(avg_util - self._optimal_utilization_pct) > 20.0:
            recs.append(
                f"Average utilization {avg_util}% deviates significantly"
                f" from optimal {self._optimal_utilization_pct}%"
            )
        if not recs:
            recs.append("Capacity utilization meets targets")
        return UtilizationScorerReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            avg_utilization_pct=avg_util,
            by_resource_type=by_resource_type,
            by_grade=by_grade,
            over_provisioned_count=over_provisioned_count,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("utilization_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        resource_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            resource_dist[key] = resource_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "optimal_utilization_pct": self._optimal_utilization_pct,
            "resource_type_distribution": resource_dist,
            "unique_resources": len({r.resource_name for r in self._records}),
        }
