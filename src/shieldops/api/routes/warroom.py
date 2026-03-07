"""War room API routes — create, manage, and close incident war rooms.

Integrates with PagerDuty for on-call paging and Slack for communication channels.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.warroom.coordinator import WarRoomCoordinator, WarRoomStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/warrooms", tags=["War Rooms"])

_coordinator: WarRoomCoordinator | None = None


def set_coordinator(coordinator: WarRoomCoordinator) -> None:
    """Inject the war room coordinator at startup."""
    global _coordinator
    _coordinator = coordinator


def _get_coordinator() -> WarRoomCoordinator:
    if _coordinator is None:
        raise HTTPException(503, "War room service unavailable")
    return _coordinator


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateWarRoomRequest(BaseModel):
    incident_id: str
    title: str
    severity: str = "P2"
    service_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class PageRequest(BaseModel):
    service_ids: list[str]


class EscalateRequest(BaseModel):
    service_ids: list[str] = Field(default_factory=list)


class CloseRequest(BaseModel):
    resolution_summary: str = ""


class PostUpdateRequest(BaseModel):
    message: str
    author: str = "system"


class AddResponderRequest(BaseModel):
    user_name: str
    user_email: str = ""
    role: str = "responder"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("")
async def create_war_room(
    body: CreateWarRoomRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Create a new war room for an incident.

    Automatically creates a Slack channel, pages on-call teams from PagerDuty,
    and posts an initial timeline message.
    """
    coord = _get_coordinator()
    room = await coord.create_war_room(
        incident_id=body.incident_id,
        title=body.title,
        severity=body.severity,
        service_ids=body.service_ids if body.service_ids else None,
        metadata=body.metadata,
    )
    logger.info("api_war_room_created", war_room_id=room.id)
    return room.model_dump(mode="json")


@router.get("")
async def list_war_rooms(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    """List active war rooms, optionally filtered by status."""
    coord = _get_coordinator()
    ws: WarRoomStatus | None = None
    if status:
        try:
            ws = WarRoomStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}") from None
    rooms = coord.list_war_rooms(status=ws)
    return [r.model_dump(mode="json") for r in rooms]


@router.get("/{war_room_id}")
async def get_war_room(
    war_room_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Get war room details including responders, timeline, and agents."""
    coord = _get_coordinator()
    room = coord.get_war_room(war_room_id)
    if room is None:
        raise HTTPException(404, f"War room '{war_room_id}' not found")
    return room.model_dump(mode="json")


@router.post("/{war_room_id}/page")
async def page_teams(
    war_room_id: str,
    body: PageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Page additional on-call teams into the war room."""
    coord = _get_coordinator()
    try:
        responders = await coord.page_responders(war_room_id, body.service_ids)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "war_room_id": war_room_id,
        "paged": [r.model_dump(mode="json") for r in responders],
    }


@router.post("/{war_room_id}/escalate")
async def escalate_war_room(
    war_room_id: str,
    body: EscalateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Escalate the war room to the next tier."""
    coord = _get_coordinator()
    try:
        new_level = await coord.escalate(
            war_room_id,
            service_ids=body.service_ids if body.service_ids else None,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"war_room_id": war_room_id, "escalation_level": new_level}


@router.post("/{war_room_id}/close")
async def close_war_room(
    war_room_id: str,
    body: CloseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Close the war room: archive channel, post summary, resolve PD incident."""
    coord = _get_coordinator()
    try:
        room = await coord.close_war_room(war_room_id, body.resolution_summary)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return room.model_dump(mode="json")


@router.post("/{war_room_id}/update")
async def post_update(
    war_room_id: str,
    body: PostUpdateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Post an update message to the war room timeline and Slack channel."""
    coord = _get_coordinator()
    try:
        entry = await coord.post_update(
            war_room_id,
            body.message,
            author=body.author,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return entry.model_dump(mode="json")


@router.post("/{war_room_id}/responders")
async def add_responder(
    war_room_id: str,
    body: AddResponderRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Manually add a responder to the war room."""
    coord = _get_coordinator()
    try:
        responder = await coord.add_responder(
            war_room_id,
            user_name=body.user_name,
            user_email=body.user_email,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return responder.model_dump(mode="json")
