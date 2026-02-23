"""Deployment Velocity Tracker — per-team/service frequency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeploymentStage(StrEnum):
    COMMIT = "commit"
    BUILD = "build"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class VelocityTrend(StrEnum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"
    STALLED = "stalled"


class BottleneckType(StrEnum):
    BUILD = "build"
    TEST = "test"
    APPROVAL = "approval"
    DEPLOYMENT = "deployment"
    ROLLBACK = "rollback"


# --- Models ---


class DeploymentEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    team: str = ""
    stage: DeploymentStage = DeploymentStage.PRODUCTION
    duration_seconds: float = 0.0
    success: bool = True
    commit_sha: str = ""
    tags: list[str] = Field(default_factory=list)
    deployed_at: float = Field(default_factory=time.time)


class VelocityReport(BaseModel):
    service: str
    team: str = ""
    total_deployments: int = 0
    successful_deployments: int = 0
    avg_duration: float = 0.0
    deployments_per_day: float = 0.0
    trend: VelocityTrend = VelocityTrend.STABLE
    period_days: int = 30


# --- Tracker ---


class DeploymentVelocityTracker:
    """Tracks per-team/service deployment frequency, lead time, and bottlenecks."""

    def __init__(
        self,
        max_events: int = 100000,
        default_period_days: int = 30,
    ) -> None:
        self._max_events = max_events
        self._default_period_days = default_period_days
        self._events: list[DeploymentEvent] = []
        logger.info(
            "deployment_velocity.initialized",
            max_events=max_events,
            default_period_days=default_period_days,
        )

    def record_deployment(
        self,
        service: str,
        team: str = "",
        stage: DeploymentStage = DeploymentStage.PRODUCTION,
        duration_seconds: float = 0.0,
        success: bool = True,
        **kw: Any,
    ) -> DeploymentEvent:
        """Record a deployment event."""
        event = DeploymentEvent(
            service=service,
            team=team,
            stage=stage,
            duration_seconds=duration_seconds,
            success=success,
            **kw,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        logger.info(
            "deployment_velocity.event_recorded",
            event_id=event.id,
            service=service,
            stage=stage,
            success=success,
        )
        return event

    def get_velocity(
        self,
        service: str | None = None,
        team: str | None = None,
        period_days: int | None = None,
    ) -> VelocityReport:
        """Get deployment velocity for a service/team."""
        days = period_days or self._default_period_days
        cutoff = time.time() - (days * 86400)
        events = [e for e in self._events if e.deployed_at >= cutoff]
        if service is not None:
            events = [e for e in events if e.service == service]
        if team is not None:
            events = [e for e in events if e.team == team]
        total = len(events)
        successful = sum(1 for e in events if e.success)
        avg_dur = sum(e.duration_seconds for e in events) / total if total else 0.0
        per_day = total / days if days > 0 else 0.0
        return VelocityReport(
            service=service or "*",
            team=team or "*",
            total_deployments=total,
            successful_deployments=successful,
            avg_duration=round(avg_dur, 2),
            deployments_per_day=round(per_day, 4),
            trend=self._calculate_trend(events, days),
            period_days=days,
        )

    def _calculate_trend(
        self,
        events: list[DeploymentEvent],
        period_days: int,
    ) -> VelocityTrend:
        """Calculate velocity trend by comparing halves of the period."""
        if len(events) < 4:
            return VelocityTrend.STALLED
        now = time.time()
        half = period_days * 86400 / 2
        first_half = [e for e in events if e.deployed_at < now - half]
        second_half = [e for e in events if e.deployed_at >= now - half]
        if not first_half:
            return VelocityTrend.ACCELERATING
        if not second_half:
            return VelocityTrend.DECELERATING
        ratio = len(second_half) / len(first_half)
        if ratio > 1.2:
            return VelocityTrend.ACCELERATING
        elif ratio < 0.8:
            return VelocityTrend.DECELERATING
        return VelocityTrend.STABLE

    def get_trend(
        self,
        service: str,
        period_days: int | None = None,
    ) -> dict[str, Any]:
        """Get trend analysis for a service."""
        report = self.get_velocity(service=service, period_days=period_days)
        return {
            "service": service,
            "trend": report.trend,
            "deployments_per_day": report.deployments_per_day,
            "total_deployments": report.total_deployments,
        }

    def identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify deployment bottlenecks by stage duration."""
        stage_durations: dict[str, list[float]] = {}
        for e in self._events:
            stage_durations.setdefault(e.stage, []).append(e.duration_seconds)
        bottlenecks: list[dict[str, Any]] = []
        for stage, durations in stage_durations.items():
            avg = sum(durations) / len(durations) if durations else 0.0
            max_dur = max(durations) if durations else 0.0
            bottlenecks.append(
                {
                    "stage": stage,
                    "avg_duration": round(avg, 2),
                    "max_duration": round(max_dur, 2),
                    "event_count": len(durations),
                }
            )
        bottlenecks.sort(key=lambda b: b["avg_duration"], reverse=True)
        return bottlenecks

    def list_events(
        self,
        service: str | None = None,
        team: str | None = None,
        stage: DeploymentStage | None = None,
        limit: int = 100,
    ) -> list[DeploymentEvent]:
        """List deployment events with optional filters."""
        results = list(self._events)
        if service is not None:
            results = [e for e in results if e.service == service]
        if team is not None:
            results = [e for e in results if e.team == team]
        if stage is not None:
            results = [e for e in results if e.stage == stage]
        return results[-limit:]

    def compare_teams(self) -> list[dict[str, Any]]:
        """Compare deployment velocity across teams."""
        teams: set[str] = {e.team for e in self._events if e.team}
        comparisons: list[dict[str, Any]] = []
        for team in sorted(teams):
            report = self.get_velocity(team=team)
            comparisons.append(
                {
                    "team": team,
                    "total_deployments": report.total_deployments,
                    "deployments_per_day": report.deployments_per_day,
                    "avg_duration": report.avg_duration,
                    "trend": report.trend,
                }
            )
        return comparisons

    def get_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get deployment leaderboard by frequency."""
        service_counts: dict[str, int] = {}
        for e in self._events:
            service_counts[e.service] = service_counts.get(e.service, 0) + 1
        ranked = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"service": s, "deployment_count": c} for s, c in ranked[:limit]]

    def clear_events(self) -> int:
        """Clear all events. Returns count cleared."""
        count = len(self._events)
        self._events.clear()
        logger.info("deployment_velocity.events_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        stage_counts: dict[str, int] = {}
        for e in self._events:
            stage_counts[e.stage] = stage_counts.get(e.stage, 0) + 1
        total = len(self._events)
        successful = sum(1 for e in self._events if e.success)
        return {
            "total_events": total,
            "successful_events": successful,
            "success_rate": round(successful / total, 4) if total else 0.0,
            "stage_distribution": stage_counts,
        }
