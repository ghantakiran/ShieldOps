"""Per-user notification preference endpoints.

Routes:
    GET  /users/me/notification-preferences
    PUT  /users/me/notification-preferences
    DELETE /users/me/notification-preferences/{pref_id}
    GET  /notification-events
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(tags=["Notification Preferences"])

_repository: Any | None = None

VALID_CHANNELS = {"email", "slack", "webhook", "pagerduty"}

EVENT_TYPES = [
    "investigation.created",
    "investigation.completed",
    "investigation.failed",
    "remediation.created",
    "remediation.completed",
    "remediation.failed",
    "remediation.rollback",
    "security.scan_completed",
    "security.critical_cve",
    "agent.error",
    "agent.escalation",
    "system.health_degraded",
]

_VALID_EVENT_TYPES = set(EVENT_TYPES)


def set_repository(repo: Any) -> None:
    """Set the repository instance (called from app lifespan)."""
    global _repository  # noqa: PLW0603
    _repository = repo


def _get_repo(request: Request) -> Any:
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return repo


# ── Request / Response models ────────────────────────────────


class NotificationPrefItem(BaseModel):
    """A single preference to upsert."""

    channel: str = Field(..., description="email, slack, webhook, pagerduty")
    event_type: str = Field(..., description="e.g. investigation.created")
    enabled: bool = True
    config: dict[str, Any] | None = None


class BulkUpsertBody(BaseModel):
    """Bulk upsert request — list of preferences."""

    preferences: list[NotificationPrefItem] = Field(..., min_length=1, max_length=200)


class NotificationPrefResponse(BaseModel):
    id: str
    user_id: str
    channel: str
    event_type: str
    enabled: bool
    config: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class EventTypeInfo(BaseModel):
    event_type: str
    description: str


# ── Helpers ──────────────────────────────────────────────────

_EVENT_DESCRIPTIONS: dict[str, str] = {
    "investigation.created": "A new investigation was started",
    "investigation.completed": "An investigation finished",
    "investigation.failed": "An investigation encountered an error",
    "remediation.created": "A remediation action was initiated",
    "remediation.completed": "A remediation action succeeded",
    "remediation.failed": "A remediation action failed",
    "remediation.rollback": "A remediation was rolled back",
    "security.scan_completed": "A security scan finished",
    "security.critical_cve": "A critical CVE was discovered",
    "agent.error": "An agent encountered an error",
    "agent.escalation": "An agent escalated to a human",
    "system.health_degraded": "System health degradation detected",
}


def _validate_channel(channel: str) -> None:
    if channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Invalid channel '{channel}'. Must be one of: {sorted(VALID_CHANNELS)}"),
        )


def _validate_event_type(event_type: str) -> None:
    if event_type not in _VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Invalid event_type '{event_type}'. Must be one of: {EVENT_TYPES}"),
        )


# ── Endpoints ────────────────────────────────────────────────


@router.get("/users/me/notification-preferences")
async def list_my_preferences(
    request: Request,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List the current user's notification preferences."""
    repo = _get_repo(request)
    prefs = await repo.get_notification_preferences(user.id)
    return {"items": prefs, "total": len(prefs)}


@router.put("/users/me/notification-preferences")
async def bulk_upsert_preferences(
    request: Request,
    body: BulkUpsertBody,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Bulk upsert notification preferences.

    Each (channel, event_type) pair is upserted independently.
    """
    repo = _get_repo(request)

    # Validate all items up front before writing
    for item in body.preferences:
        _validate_channel(item.channel)
        _validate_event_type(item.event_type)

    results: list[dict[str, Any]] = []
    for item in body.preferences:
        pref = await repo.upsert_notification_preference(
            user_id=user.id,
            channel=item.channel,
            event_type=item.event_type,
            enabled=item.enabled,
            config=item.config,
        )
        results.append(pref)

    logger.info(
        "notification_preferences_bulk_upserted",
        user_id=user.id,
        count=len(results),
    )
    return {"items": results, "total": len(results)}


@router.delete(
    "/users/me/notification-preferences/{pref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_preference(
    request: Request,
    pref_id: str,
    user: UserResponse = Depends(get_current_user),
) -> Response:
    """Delete a notification preference. Ownership is enforced."""
    repo = _get_repo(request)
    deleted = await repo.delete_notification_preference(preference_id=pref_id, user_id=user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preference not found",
        )
    logger.info(
        "notification_preference_deleted_by_user",
        pref_id=pref_id,
        user_id=user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notification-events")
async def list_event_types(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all available notification event types."""
    items = [
        {
            "event_type": et,
            "description": _EVENT_DESCRIPTIONS.get(et, ""),
        }
        for et in EVENT_TYPES
    ]
    return {"items": items, "total": len(items)}
