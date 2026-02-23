"""Health check aggregation with weighted scoring and trend detection.

Registers components with weights, computes an aggregate health score
(0-100), and tracks history for trend analysis.
"""

from __future__ import annotations

import enum
import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class HealthStatus(enum.StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthTrend(enum.StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ── Status numerical values for scoring ──────────────────────────────

_STATUS_VALUE: dict[HealthStatus, float] = {
    HealthStatus.HEALTHY: 1.0,
    HealthStatus.DEGRADED: 0.5,
    HealthStatus.UNHEALTHY: 0.1,
    HealthStatus.CRITICAL: 0.0,
    HealthStatus.UNKNOWN: 0.0,
}


# ── Models ───────────────────────────────────────────────────────────


class ComponentHealth(BaseModel):
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    consecutive_failures: int = 0
    weight: float = 1.0
    is_critical: bool = False
    last_checked: float = Field(default_factory=time.time)
    message: str = ""


class HealthSnapshot(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    health_score: float = 0.0
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    component_count: int = 0


class AggregateHealth(BaseModel):
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    health_score: float = 0.0
    components: list[ComponentHealth] = Field(default_factory=list)
    trend: HealthTrend = HealthTrend.STABLE
    checked_at: float = Field(default_factory=time.time)


# ── Aggregator ───────────────────────────────────────────────────────


class HealthAggregator:
    """Register components, compute aggregate health score, track trends.

    Parameters
    ----------
    history_size:
        Max number of snapshots to retain for trend detection.
    degraded_threshold:
        Score below which overall status becomes "degraded" (default 70).
    unhealthy_threshold:
        Score below which overall status becomes "unhealthy" (default 40).
    """

    def __init__(
        self,
        history_size: int = 100,
        degraded_threshold: float = 70.0,
        unhealthy_threshold: float = 40.0,
    ) -> None:
        self._components: dict[str, ComponentHealth] = {}
        self._history: list[HealthSnapshot] = []
        self._history_size = history_size
        self._degraded_threshold = degraded_threshold
        self._unhealthy_threshold = unhealthy_threshold

    # ── Registration ─────────────────────────────────────────────

    def register(
        self,
        name: str,
        weight: float = 1.0,
        is_critical: bool = False,
    ) -> ComponentHealth:
        comp = ComponentHealth(name=name, weight=weight, is_critical=is_critical)
        self._components[name] = comp
        logger.info("health_component_registered", name=name, weight=weight)
        return comp

    def unregister(self, name: str) -> bool:
        return self._components.pop(name, None) is not None

    def get_component(self, name: str) -> ComponentHealth | None:
        return self._components.get(name)

    def list_components(self) -> list[ComponentHealth]:
        return list(self._components.values())

    # ── Update ───────────────────────────────────────────────────

    def update_component(
        self,
        name: str,
        status: HealthStatus,
        latency_ms: float = 0.0,
        message: str = "",
    ) -> ComponentHealth | None:
        comp = self._components.get(name)
        if comp is None:
            return None
        if status in (HealthStatus.UNHEALTHY, HealthStatus.CRITICAL):
            comp.consecutive_failures += 1
        else:
            comp.consecutive_failures = 0
        comp.status = status
        comp.latency_ms = latency_ms
        comp.message = message
        comp.last_checked = time.time()
        return comp

    # ── Scoring ──────────────────────────────────────────────────

    def compute(self) -> AggregateHealth:
        """Compute aggregate health score and overall status."""
        if not self._components:
            return AggregateHealth()

        components = list(self._components.values())

        # Critical component override
        for comp in components:
            if comp.is_critical and comp.status == HealthStatus.CRITICAL:
                agg = AggregateHealth(
                    overall_status=HealthStatus.CRITICAL,
                    health_score=0.0,
                    components=components,
                    trend=self._detect_trend(0.0),
                    checked_at=time.time(),
                )
                self._record_snapshot(agg)
                return agg

        # Weighted average
        total_weight = sum(c.weight for c in components)
        if total_weight == 0:
            total_weight = 1.0
        score = (
            sum(c.weight * _STATUS_VALUE.get(c.status, 0.0) for c in components)
            / total_weight
            * 100
        )
        score = round(score, 2)

        # Map score to status
        if score >= self._degraded_threshold:
            overall = HealthStatus.HEALTHY
        elif score >= self._unhealthy_threshold:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.UNHEALTHY

        # Check if any critical component is unhealthy (force degraded at minimum)
        for comp in components:
            if comp.is_critical and comp.status in (
                HealthStatus.UNHEALTHY,
                HealthStatus.CRITICAL,
            ):
                if overall == HealthStatus.HEALTHY:
                    overall = HealthStatus.DEGRADED
                break

        trend = self._detect_trend(score)
        agg = AggregateHealth(
            overall_status=overall,
            health_score=score,
            components=components,
            trend=trend,
            checked_at=time.time(),
        )
        self._record_snapshot(agg)
        return agg

    def _record_snapshot(self, agg: AggregateHealth) -> None:
        snap = HealthSnapshot(
            health_score=agg.health_score,
            overall_status=agg.overall_status,
            component_count=len(agg.components),
        )
        self._history.append(snap)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size :]

    def _detect_trend(self, current_score: float) -> HealthTrend:
        if len(self._history) < 3:
            return HealthTrend.STABLE
        recent = [s.health_score for s in self._history[-5:]]
        avg_recent = sum(recent) / len(recent)
        if current_score > avg_recent + 5:
            return HealthTrend.IMPROVING
        if current_score < avg_recent - 5:
            return HealthTrend.DECLINING
        return HealthTrend.STABLE

    # ── History ──────────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[HealthSnapshot]:
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for comp in self._components.values():
            by_status[comp.status.value] = by_status.get(comp.status.value, 0) + 1
        return {
            "total_components": len(self._components),
            "by_status": by_status,
            "history_size": len(self._history),
        }
