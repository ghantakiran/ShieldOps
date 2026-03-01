"""Deploy Canary Health Monitor — monitor canary deployment health in real-time."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CanaryMetricType(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"
    AVAILABILITY = "availability"


class CanaryHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CanaryDecision(StrEnum):
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    EXTEND = "extend"
    PAUSE = "pause"
    MANUAL_REVIEW = "manual_review"


# --- Models ---


class CanaryHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE
    canary_health: CanaryHealth = CanaryHealth.HEALTHY
    canary_decision: CanaryDecision = CanaryDecision.PROMOTE
    health_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CanaryComparison(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE
    comparison_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployCanaryHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_comparisons: int = 0
    unhealthy_canaries: int = 0
    avg_health_score: float = 0.0
    by_metric_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    top_unhealthy: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployCanaryHealthMonitor:
    """Monitor canary deployment health in real-time, compare canary vs baseline."""

    def __init__(
        self,
        max_records: int = 200000,
        max_unhealthy_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_unhealthy_pct = max_unhealthy_pct
        self._records: list[CanaryHealthRecord] = []
        self._comparisons: list[CanaryComparison] = []
        logger.info(
            "deploy_canary_health.initialized",
            max_records=max_records,
            max_unhealthy_pct=max_unhealthy_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_canary(
        self,
        deployment_id: str,
        canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE,
        canary_health: CanaryHealth = CanaryHealth.HEALTHY,
        canary_decision: CanaryDecision = CanaryDecision.PROMOTE,
        health_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CanaryHealthRecord:
        record = CanaryHealthRecord(
            deployment_id=deployment_id,
            canary_metric_type=canary_metric_type,
            canary_health=canary_health,
            canary_decision=canary_decision,
            health_score=health_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_canary_health.canary_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            canary_metric_type=canary_metric_type.value,
            canary_health=canary_health.value,
        )
        return record

    def get_canary(self, record_id: str) -> CanaryHealthRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_canaries(
        self,
        metric_type: CanaryMetricType | None = None,
        health: CanaryHealth | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CanaryHealthRecord]:
        results = list(self._records)
        if metric_type is not None:
            results = [r for r in results if r.canary_metric_type == metric_type]
        if health is not None:
            results = [r for r in results if r.canary_health == health]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_comparison(
        self,
        deployment_id: str,
        canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE,
        comparison_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CanaryComparison:
        comparison = CanaryComparison(
            deployment_id=deployment_id,
            canary_metric_type=canary_metric_type,
            comparison_score=comparison_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_records:
            self._comparisons = self._comparisons[-self._max_records :]
        logger.info(
            "deploy_canary_health.comparison_added",
            deployment_id=deployment_id,
            canary_metric_type=canary_metric_type.value,
            comparison_score=comparison_score,
        )
        return comparison

    # -- domain operations --------------------------------------------------

    def analyze_canary_health(self) -> dict[str, Any]:
        """Group by metric type; return count and avg health score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.canary_metric_type.value
            type_data.setdefault(key, []).append(r.health_score)
        result: dict[str, Any] = {}
        for metric_type, scores in type_data.items():
            result[metric_type] = {
                "count": len(scores),
                "avg_health_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_unhealthy_canaries(self) -> list[dict[str, Any]]:
        """Return records where canary_health is CRITICAL or DEGRADED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.canary_health in (
                CanaryHealth.CRITICAL,
                CanaryHealth.DEGRADED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "deployment_id": r.deployment_id,
                        "canary_metric_type": r.canary_metric_type.value,
                        "canary_health": r.canary_health.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"], reverse=True)
        return results

    def detect_health_trends(self) -> dict[str, Any]:
        """Split-half on comparison_score; delta threshold 5.0."""
        if len(self._comparisons) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [c.comparison_score for c in self._comparisons]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
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

    def generate_report(self) -> DeployCanaryHealthReport:
        by_metric_type: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        for r in self._records:
            by_metric_type[r.canary_metric_type.value] = (
                by_metric_type.get(r.canary_metric_type.value, 0) + 1
            )
            by_health[r.canary_health.value] = by_health.get(r.canary_health.value, 0) + 1
            by_decision[r.canary_decision.value] = by_decision.get(r.canary_decision.value, 0) + 1
        unhealthy_count = sum(
            1
            for r in self._records
            if r.canary_health in (CanaryHealth.CRITICAL, CanaryHealth.DEGRADED)
        )
        scores = [r.health_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_health_score()
        top_unhealthy = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        unhealthy_rate = (
            round(unhealthy_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if unhealthy_rate > self._max_unhealthy_pct:
            recs.append(
                f"Unhealthy canary rate {unhealthy_rate}% exceeds threshold"
                f" ({self._max_unhealthy_pct}%)"
            )
        if unhealthy_count > 0:
            recs.append(f"{unhealthy_count} unhealthy canary(ies) detected — review deployments")
        if not recs:
            recs.append("Canary deployment health is acceptable")
        return DeployCanaryHealthReport(
            total_records=len(self._records),
            total_comparisons=len(self._comparisons),
            unhealthy_canaries=unhealthy_count,
            avg_health_score=avg_score,
            by_metric_type=by_metric_type,
            by_health=by_health,
            by_decision=by_decision,
            top_unhealthy=top_unhealthy,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._comparisons.clear()
        logger.info("deploy_canary_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.canary_metric_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_comparisons": len(self._comparisons),
            "max_unhealthy_pct": self._max_unhealthy_pct,
            "metric_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_deployments": len({r.deployment_id for r in self._records}),
        }
