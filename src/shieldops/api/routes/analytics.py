"""Analytics and reporting API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

if TYPE_CHECKING:
    from shieldops.analytics.engine import AnalyticsEngine

router = APIRouter()

_engine: AnalyticsEngine | None = None


def set_engine(engine: AnalyticsEngine | None) -> None:
    global _engine
    _engine = engine


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
