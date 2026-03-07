"""Usage-based billing API endpoints.

Exposes usage summaries, cost breakdowns, forecasts, analytics,
and alert management for metered billing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse
from shieldops.billing.usage_alerts import UsageAlertManager
from shieldops.billing.usage_billing import UsageBillingEngine
from shieldops.billing.usage_models import UsageEventType
from shieldops.billing.usage_tracker import UsageTracker

logger = structlog.get_logger()

router = APIRouter()

# ------------------------------------------------------------------
# Module-level singletons — wired from app.py lifespan
# ------------------------------------------------------------------

_tracker: UsageTracker | None = None
_billing_engine: UsageBillingEngine | None = None
_alert_manager: UsageAlertManager | None = None


def configure_usage_billing(
    tracker: UsageTracker,
    billing_engine: UsageBillingEngine,
    alert_manager: UsageAlertManager,
) -> None:
    """Inject service instances (called during app startup)."""
    global _tracker, _billing_engine, _alert_manager
    _tracker = tracker
    _billing_engine = billing_engine
    _alert_manager = alert_manager


def _get_tracker() -> UsageTracker:
    if _tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking not configured",
        )
    return _tracker


def _get_engine() -> UsageBillingEngine:
    if _billing_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Usage billing not configured",
        )
    return _billing_engine


def _get_alert_manager() -> UsageAlertManager:
    if _alert_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Usage alerts not configured",
        )
    return _alert_manager


def _get_org_id(user: UserResponse) -> str:
    """Derive org_id from the authenticated user."""
    return getattr(user, "org_id", None) or user.id


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class RecordEventRequest(BaseModel):
    """Request body for recording a usage event."""

    event_type: UsageEventType
    quantity: int = 1
    metadata: dict[str, str] | None = None


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/billing/usage")
async def get_current_usage(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return usage summary for the current billing period."""
    tracker = _get_tracker()
    org_id = _get_org_id(user)
    summary = await tracker.get_current_period_usage(org_id)
    return summary.model_dump(mode="json")


@router.get("/billing/usage/history")
async def get_usage_history(
    start: str = Query(
        ...,
        description="Period start (ISO 8601)",
    ),
    end: str = Query(
        ...,
        description="Period end (ISO 8601)",
    ),
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return usage summary for a historical date range."""
    tracker = _get_tracker()
    org_id = _get_org_id(user)

    try:
        period_start = datetime.fromisoformat(start).replace(tzinfo=UTC)
        period_end = datetime.fromisoformat(end).replace(tzinfo=UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {exc}",
        ) from exc

    summary = await tracker.get_usage_summary(
        org_id,
        period_start,
        period_end,
    )
    return summary.model_dump(mode="json")


@router.get("/billing/usage/breakdown")
async def get_cost_breakdown(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return cost breakdown by event type for the current period."""
    engine = _get_engine()
    org_id = _get_org_id(user)
    return await engine.get_cost_breakdown(org_id)


@router.get("/billing/usage/forecast")
async def get_monthly_forecast(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return projected monthly cost based on current usage trend."""
    engine = _get_engine()
    org_id = _get_org_id(user)
    return await engine.forecast_monthly_cost(org_id)


@router.get("/billing/usage/analytics")
async def get_usage_analytics(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days to analyse",
    ),
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return usage analytics: daily trends, peak hours, top features."""
    engine = _get_engine()
    org_id = _get_org_id(user)
    return await engine.get_usage_analytics(org_id, days=days)


@router.get("/billing/alerts")
async def get_billing_alerts(
    resolved: bool = Query(
        default=False,
        description="Return resolved alerts instead of active",
    ),
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return active (or resolved) billing alerts for the org."""
    manager = _get_alert_manager()
    org_id = _get_org_id(user)
    alerts = manager.get_alerts(org_id, resolved=resolved)
    return {
        "org_id": org_id,
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "count": len(alerts),
    }


@router.post("/billing/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Dismiss (resolve) a billing alert."""
    manager = _get_alert_manager()
    dismissed = manager.dismiss_alert(alert_id)
    if not dismissed:
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found",
        )
    return {"alert_id": alert_id, "dismissed": True}


@router.post("/billing/usage/event")
async def record_usage_event(
    body: RecordEventRequest,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a usage event (internal API).

    Typically called by agent orchestration or middleware to track
    billable actions.
    """
    tracker = _get_tracker()
    org_id = _get_org_id(user)

    event = await tracker.record_event(
        org_id=org_id,
        event_type=body.event_type,
        quantity=body.quantity,
        metadata=body.metadata,
    )
    return {
        "event_id": str(event.event_id),
        "org_id": org_id,
        "event_type": event.event_type.value,
        "quantity": event.quantity,
        "recorded": True,
    }
