"""Analytics and reporting API endpoints."""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

if TYPE_CHECKING:
    from shieldops.analytics.engine import AnalyticsEngine

router = APIRouter()

_engine: AnalyticsEngine | None = None


def set_engine(engine: AnalyticsEngine | None) -> None:
    global _engine
    _engine = engine


def _parse_period_seconds(period: str) -> int:
    """Convert a period string like '7d', '24h', '30m' to seconds."""
    unit = period[-1]
    value = int(period[:-1])
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    return value * multipliers.get(unit, 86400)


def _seed_for_period(period: str) -> int:
    """Deterministic seed so demo data is stable per period."""
    return int(
        hashlib.md5(period.encode(), usedforsecurity=False).hexdigest()[:8],
        16,
    )


def _generate_agent_performance_demo(
    period: str,
    agent_type_filter: str | None,
) -> dict[str, Any]:
    """Generate realistic demo data for agent performance."""
    rng = random.Random(_seed_for_period(period))  # noqa: S311
    period_seconds = _parse_period_seconds(period)
    now = datetime.now(UTC)

    agent_types = [
        "investigation",
        "remediation",
        "security",
        "learning",
    ]
    if agent_type_filter:
        agent_types = [t for t in agent_types if t == agent_type_filter]

    # Base profiles per agent type for realistic variation
    profiles: dict[str, dict[str, Any]] = {
        "investigation": {
            "base_executions": 145,
            "success_rate": 0.92,
            "avg_duration": 34.5,
            "p50": 28.0,
            "p95": 65.0,
            "p99": 120.0,
        },
        "remediation": {
            "base_executions": 89,
            "success_rate": 0.88,
            "avg_duration": 52.3,
            "p50": 40.0,
            "p95": 95.0,
            "p99": 180.0,
        },
        "security": {
            "base_executions": 67,
            "success_rate": 0.95,
            "avg_duration": 78.1,
            "p50": 60.0,
            "p95": 140.0,
            "p99": 250.0,
        },
        "learning": {
            "base_executions": 34,
            "success_rate": 0.97,
            "avg_duration": 120.8,
            "p50": 100.0,
            "p95": 200.0,
            "p99": 350.0,
        },
    }

    # Scale executions by period length relative to 7d
    scale = period_seconds / (7 * 86400)

    agents: list[dict[str, Any]] = []
    total_executions = 0
    total_errors = 0
    weighted_success = 0.0
    weighted_duration = 0.0

    for agent in agent_types:
        profile = profiles[agent]
        noise = rng.uniform(0.9, 1.1)
        execs = max(1, round(profile["base_executions"] * scale * noise))
        sr = min(
            1.0,
            max(0.0, profile["success_rate"] + rng.uniform(-0.05, 0.03)),
        )
        sr = round(sr, 4)
        errors = max(0, round(execs * (1 - sr)))
        avg_dur = round(profile["avg_duration"] * rng.uniform(0.85, 1.15), 1)

        # Build daily trend
        if period_seconds <= 3600:
            num_points = max(1, period_seconds // 300)
            fmt = "minute"
        elif period_seconds <= 86400:
            num_points = max(1, period_seconds // 3600)
            fmt = "hour"
        else:
            num_points = max(1, period_seconds // 86400)
            fmt = "day"

        trend: list[dict[str, Any]] = []
        for i in range(int(num_points)):
            if fmt == "day":
                dt = now - timedelta(days=int(num_points) - 1 - i)
                label = dt.strftime("%Y-%m-%d")
            elif fmt == "hour":
                dt = now - timedelta(hours=int(num_points) - 1 - i)
                label = dt.strftime("%Y-%m-%d %H:00")
            else:
                dt = now - timedelta(minutes=(int(num_points) - 1 - i) * 5)
                label = dt.strftime("%H:%M")

            pt_execs = max(
                1,
                round(execs / num_points * rng.uniform(0.6, 1.4)),
            )
            pt_sr = min(1.0, max(0.0, sr + rng.uniform(-0.08, 0.08)))
            trend.append(
                {
                    "date": label,
                    "executions": pt_execs,
                    "success_rate": round(pt_sr, 4),
                }
            )

        agents.append(
            {
                "agent_type": agent,
                "total_executions": execs,
                "success_rate": sr,
                "avg_duration_seconds": avg_dur,
                "error_count": errors,
                "p50_duration": round(profile["p50"] * rng.uniform(0.9, 1.1), 1),
                "p95_duration": round(profile["p95"] * rng.uniform(0.9, 1.1), 1),
                "p99_duration": round(profile["p99"] * rng.uniform(0.9, 1.1), 1),
                "trend": trend,
            }
        )

        total_executions += execs
        total_errors += errors
        weighted_success += sr * execs
        weighted_duration += avg_dur * execs

    # Hourly heatmap (7 days x 24 hours)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hourly_heatmap: list[dict[str, Any]] = []
    for day in days:
        for hour in range(24):
            # More activity during business hours
            base = 3 if 9 <= hour <= 17 else 1
            if day in ("Sat", "Sun"):
                base = max(1, base // 2)
            count = max(0, round(base * scale * rng.uniform(0.3, 2.5)))
            hourly_heatmap.append(
                {
                    "hour": hour,
                    "day": day,
                    "count": count,
                }
            )

    avg_success = round(weighted_success / total_executions, 4) if total_executions else 0.0
    avg_duration = round(weighted_duration / total_executions, 1) if total_executions else 0.0

    return {
        "period": period,
        "summary": {
            "total_executions": total_executions,
            "avg_success_rate": avg_success,
            "avg_duration_seconds": avg_duration,
            "total_errors": total_errors,
        },
        "agents": agents,
        "hourly_heatmap": hourly_heatmap,
    }


@router.get("/analytics/mttr")
async def get_mttr_trends(
    period: str = "30d",
    environment: str | None = None,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get Mean Time to Resolution trends."""
    if _engine:
        return await _engine.mttr_trends(period=period, environment=environment)
    return {"period": period, "data_points": [], "current_mttr_minutes": 0}


@router.get("/analytics/resolution-rate")
async def get_resolution_rate(
    period: str = "30d",
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get automated vs manual resolution rates."""
    if _engine:
        return await _engine.resolution_rate(period=period)
    return {
        "period": period,
        "automated_rate": 0.0,
        "manual_rate": 0.0,
        "total_incidents": 0,
    }


@router.get("/analytics/agent-accuracy")
async def get_agent_accuracy(
    period: str = "30d",
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get agent diagnosis accuracy over time."""
    if _engine:
        return await _engine.agent_accuracy(period=period)
    return {"period": period, "accuracy": 0.0, "total_investigations": 0}


@router.get("/analytics/cost-savings")
async def get_cost_savings(
    period: str = "30d",
    engineer_hourly_rate: float = 75.0,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Estimate cost savings from automated operations."""
    if _engine:
        return await _engine.cost_savings(period=period, hourly_rate=engineer_hourly_rate)
    return {
        "period": period,
        "hours_saved": 0,
        "estimated_savings_usd": 0.0,
        "engineer_hourly_rate": engineer_hourly_rate,
    }


@router.get("/analytics/summary")
async def get_analytics_summary(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get aggregated analytics summary for the dashboard."""
    if _engine:
        summary = await _engine.summary()
        if summary:
            return summary

    return {
        "total_investigations": 0,
        "total_remediations": 0,
        "auto_resolved_percent": 0.0,
        "mean_time_to_resolve_seconds": 0,
        "investigations_by_status": {},
        "remediations_by_status": {},
    }


@router.get("/analytics/agent-performance")
async def get_agent_performance(
    period: str = Query("7d", pattern=r"^\d+[dhm]$"),
    agent_type: str | None = Query(None),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed agent performance metrics.

    Returns per-agent-type metrics with time series data,
    percentile latencies, and an hourly activity heatmap.
    """
    if _engine:
        result = await _engine.agent_performance(period=period, agent_type=agent_type)
        if result:
            return result

    return _generate_agent_performance_demo(
        period=period,
        agent_type_filter=agent_type,
    )
