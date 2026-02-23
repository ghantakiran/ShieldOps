"""Capacity Trend Analyzer — analyzes resource trends and predicts exhaustion."""

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
    INSTANCES = "instances"


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


# --- Models ---


class CapacitySnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    resource_type: ResourceType
    used: float
    total: float
    utilization_pct: float = 0.0
    recorded_at: float = Field(default_factory=time.time)


class TrendAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    resource_type: ResourceType
    direction: TrendDirection = TrendDirection.STABLE
    growth_rate_pct: float = 0.0
    days_to_exhaustion: float | None = None
    current_utilization: float = 0.0
    recommended_action: str = ""
    analyzed_at: float = Field(default_factory=time.time)


# --- Analyzer ---


class CapacityTrendAnalyzer:
    """Analyzes resource capacity trends and predicts exhaustion."""

    def __init__(
        self,
        max_snapshots: int = 500000,
        max_analyses: int = 10000,
        exhaustion_threshold: float = 90.0,
    ) -> None:
        self._max_snapshots = max_snapshots
        self._max_analyses = max_analyses
        self._exhaustion_threshold = exhaustion_threshold
        self._snapshots: list[CapacitySnapshot] = []
        self._analyses: dict[str, TrendAnalysis] = {}
        logger.info(
            "capacity_trend_analyzer.initialized",
            max_snapshots=max_snapshots,
            max_analyses=max_analyses,
            exhaustion_threshold=exhaustion_threshold,
        )

    def record_snapshot(
        self,
        service: str,
        resource_type: ResourceType,
        used: float,
        total: float,
    ) -> CapacitySnapshot:
        """Record a capacity snapshot with auto-calculated utilization."""
        utilization = (used / total * 100) if total > 0 else 0.0
        snap = CapacitySnapshot(
            service=service,
            resource_type=resource_type,
            used=used,
            total=total,
            utilization_pct=round(utilization, 2),
        )
        self._snapshots.append(snap)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots :]
        logger.info(
            "capacity_trend_analyzer.snapshot_recorded",
            snap_id=snap.id,
            service=service,
            resource_type=resource_type,
            utilization_pct=snap.utilization_pct,
        )
        return snap

    def _get_snapshots(
        self,
        service: str,
        resource_type: ResourceType,
    ) -> list[CapacitySnapshot]:
        """Return matching snapshots sorted by time."""
        return sorted(
            [
                s
                for s in self._snapshots
                if s.service == service and s.resource_type == resource_type
            ],
            key=lambda s: s.recorded_at,
        )

    def _compute_growth_rate(
        self,
        snapshots: list[CapacitySnapshot],
    ) -> float:
        """Compute growth rate in pct/day from snapshots."""
        if len(snapshots) < 2:
            return 0.0
        first = snapshots[0]
        last = snapshots[-1]
        elapsed_days = (last.recorded_at - first.recorded_at) / 86400
        if elapsed_days <= 0:
            return 0.0
        delta_pct = last.utilization_pct - first.utilization_pct
        return round(delta_pct / elapsed_days, 4)

    def _direction_from_rate(self, rate: float) -> TrendDirection:
        """Map growth rate to a direction label."""
        if rate > 0.5:
            return TrendDirection.INCREASING
        if rate < -0.5:
            return TrendDirection.DECREASING
        return TrendDirection.STABLE

    def analyze_trend(
        self,
        service: str,
        resource_type: ResourceType,
    ) -> TrendAnalysis:
        """Analyze the capacity trend for a service + resource."""
        snaps = self._get_snapshots(service, resource_type)
        current_util = snaps[-1].utilization_pct if snaps else 0.0
        growth_rate = self._compute_growth_rate(snaps)
        direction = self._direction_from_rate(growth_rate)

        days_to_exhaust: float | None = None
        if direction == TrendDirection.INCREASING and growth_rate > 0 and current_util < 100:
            remaining = 100.0 - current_util
            days_to_exhaust = round(remaining / growth_rate, 2)

        action = ""
        if current_util >= self._exhaustion_threshold:
            action = "Capacity critical; scale up immediately."
        elif days_to_exhaust is not None and days_to_exhaust < 30:
            action = f"Exhaustion in ~{days_to_exhaust:.0f} days; plan capacity expansion."
        elif direction == TrendDirection.INCREASING:
            action = "Utilization growing; monitor closely."
        elif direction == TrendDirection.DECREASING:
            action = "Utilization declining; consider downsizing."

        analysis = TrendAnalysis(
            service=service,
            resource_type=resource_type,
            direction=direction,
            growth_rate_pct=growth_rate,
            days_to_exhaustion=days_to_exhaust,
            current_utilization=current_util,
            recommended_action=action,
        )
        self._analyses[analysis.id] = analysis
        if len(self._analyses) > self._max_analyses:
            oldest = next(iter(self._analyses))
            del self._analyses[oldest]

        logger.info(
            "capacity_trend_analyzer.trend_analyzed",
            analysis_id=analysis.id,
            service=service,
            resource_type=resource_type,
            direction=direction,
            growth_rate_pct=growth_rate,
            days_to_exhaustion=days_to_exhaust,
        )
        return analysis

    def get_at_risk_resources(
        self,
        threshold: float | None = None,
    ) -> list[TrendAnalysis]:
        """Return analyses for resources approaching exhaustion."""
        thresh = threshold or self._exhaustion_threshold
        at_risk: list[TrendAnalysis] = []
        # Deduplicate by (service, resource_type) — latest only
        seen: set[tuple[str, str]] = set()
        for analysis in reversed(list(self._analyses.values())):
            key = (analysis.service, analysis.resource_type)
            if key in seen:
                continue
            seen.add(key)
            if analysis.current_utilization >= thresh or (
                analysis.days_to_exhaustion is not None and analysis.days_to_exhaustion < 30
            ):
                at_risk.append(analysis)
        return at_risk

    def get_snapshots(
        self,
        service: str | None = None,
        resource_type: ResourceType | None = None,
        limit: int = 100,
    ) -> list[CapacitySnapshot]:
        """List snapshots with optional filters."""
        results = list(self._snapshots)
        if service is not None:
            results = [s for s in results if s.service == service]
        if resource_type is not None:
            results = [s for s in results if s.resource_type == resource_type]
        return results[-limit:]

    def get_analysis(
        self,
        analysis_id: str,
    ) -> TrendAnalysis | None:
        """Retrieve an analysis by ID."""
        return self._analyses.get(analysis_id)

    def list_analyses(
        self,
        service: str | None = None,
        direction: TrendDirection | None = None,
    ) -> list[TrendAnalysis]:
        """List analyses with optional filters."""
        results = list(self._analyses.values())
        if service is not None:
            results = [a for a in results if a.service == service]
        if direction is not None:
            results = [a for a in results if a.direction == direction]
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        services: set[str] = set()
        resource_counts: dict[str, int] = {}
        for s in self._snapshots:
            services.add(s.service)
            rt = s.resource_type
            resource_counts[rt] = resource_counts.get(rt, 0) + 1
        at_risk = self.get_at_risk_resources()
        return {
            "total_snapshots": len(self._snapshots),
            "total_analyses": len(self._analyses),
            "services_tracked": len(services),
            "resource_distribution": resource_counts,
            "at_risk_count": len(at_risk),
        }
