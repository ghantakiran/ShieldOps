"""Change Tracking & Deployment Correlation API endpoints.

Records deployment/change events from Kubernetes, GitHub, CI/CD pipelines,
and manual entries.  Provides correlation scoring against incidents to
identify which changes most likely caused an outage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse
from shieldops.changes.tracker import (
    ChangeTracker,
    RecordChangeRequest,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/changes", tags=["Changes"])

# ------------------------------------------------------------------
# Module-level singleton -- wired from app.py lifespan
# ------------------------------------------------------------------

_tracker: ChangeTracker | None = None


def set_tracker(tracker: ChangeTracker) -> None:
    """Inject the ChangeTracker instance (called from app.py)."""
    global _tracker
    _tracker = tracker


def _get_tracker() -> ChangeTracker:
    if _tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Change tracking service unavailable",
        )
    return _tracker


# ------------------------------------------------------------------
# Request / response helpers
# ------------------------------------------------------------------


class CompleteRequest(BaseModel):
    """Body for marking a change as completed."""

    status: str = "completed"


class CorrelateQuery(BaseModel):
    """Query parameters for incident correlation."""

    service: str
    environment: str
    time: str  # ISO-8601 datetime
    time_window_minutes: int = 60


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/record")
async def record_change(
    body: RecordChangeRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a new deployment or infrastructure change."""
    tracker = _get_tracker()
    record = tracker.record_change(body)
    return {"change": record.model_dump(mode="json")}


@router.put("/{change_id}/complete")
async def complete_change(
    change_id: str,
    body: CompleteRequest | None = None,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark an in-progress change as completed (or failed)."""
    tracker = _get_tracker()
    status_val = body.status if body else "completed"
    record = tracker.complete_change(change_id, status=status_val)
    if record is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return {"change": record.model_dump(mode="json")}


@router.get("")
async def list_changes(
    service: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List changes with optional service/environment filters."""
    tracker = _get_tracker()
    changes = tracker.list_changes(
        service=service,
        environment=environment,
        limit=limit,
    )
    return {
        "changes": [c.model_dump(mode="json") for c in changes],
        "count": len(changes),
    }


@router.get("/timeline")
async def get_timeline(
    start: str | None = Query(default=None, description="ISO-8601 start time"),
    end: str | None = Query(default=None, description="ISO-8601 end time"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve a change timeline within an optional time range."""
    tracker = _get_tracker()
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    timeline = tracker.get_timeline(start=start_dt, end=end_dt)
    return timeline.model_dump(mode="json")


@router.get("/correlate/{incident_id}")
async def correlate_incident(
    incident_id: str,
    service: str = Query(..., description="Incident service"),
    environment: str = Query(..., description="Incident environment"),
    time: str = Query(..., description="Incident time (ISO-8601)"),
    time_window_minutes: int = Query(default=60, ge=1, le=1440),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Correlate an incident with recent changes and return scored results."""
    tracker = _get_tracker()
    incident_time = datetime.fromisoformat(time)
    results = tracker.correlate_with_incident(
        incident_id=incident_id,
        incident_service=service,
        incident_env=environment,
        incident_time=incident_time,
        time_window_minutes=time_window_minutes,
    )
    return {
        "incident_id": incident_id,
        "correlations": [r.model_dump(mode="json") for r in results],
        "count": len(results),
    }


@router.get("/{change_id}")
async def get_change(
    change_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve a single change record by ID."""
    tracker = _get_tracker()
    record = tracker.get_change(change_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return {"change": record.model_dump(mode="json")}


@router.post("/k8s")
async def record_k8s_event(
    event: dict[str, Any],
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a change from a Kubernetes rollout event."""
    tracker = _get_tracker()
    record = tracker.record_from_k8s_event(event)
    return {"change": record.model_dump(mode="json")}


@router.post("/github")
async def record_github_webhook(
    payload: dict[str, Any],
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a change from a GitHub webhook (push or deployment)."""
    tracker = _get_tracker()
    record = tracker.record_from_github_webhook(payload)
    return {"change": record.model_dump(mode="json")}


@router.post("/cicd")
async def record_cicd_event(
    pipeline: dict[str, Any],
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a change from a CI/CD pipeline event."""
    tracker = _get_tracker()
    record = tracker.record_from_cicd(pipeline)
    return {"change": record.model_dump(mode="json")}
