"""API routes for war room management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/war-rooms", tags=["war-rooms"])

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WarRoomStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class TimelineEventType(StrEnum):
    AGENT_ACTION = "agent_action"
    HUMAN_NOTE = "human_note"
    STATUS_CHANGE = "status_change"
    ESCALATION = "escalation"


class ResponderStatus(StrEnum):
    ACTIVE = "active"
    PAGED = "paged"
    ACKNOWLEDGED = "acknowledged"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Responder(BaseModel):
    user_id: str
    name: str
    role: str
    status: ResponderStatus = ResponderStatus.ACTIVE
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TimelineEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: TimelineEventType
    actor: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class WarRoom(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    severity: str
    status: WarRoomStatus = WarRoomStatus.ACTIVE
    description: str | None = None
    incident_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    timeline: list[TimelineEntry] = Field(default_factory=list)
    responders: list[Responder] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateWarRoomRequest(BaseModel):
    title: str
    severity: str
    incident_id: str | None = None
    description: str | None = None


class AddTimelineEntryRequest(BaseModel):
    event_type: TimelineEventType
    actor: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddResponderRequest(BaseModel):
    user_id: str
    name: str
    role: str


class ResolveWarRoomRequest(BaseModel):
    resolution_summary: str


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_war_rooms: dict[str, WarRoom] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_room_or_404(room_id: str) -> WarRoom:
    room = _war_rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="War room not found")
    return room


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def create_war_room(request: CreateWarRoomRequest) -> dict[str, Any]:
    """Create a new war room."""
    room = WarRoom(
        title=request.title,
        severity=request.severity,
        incident_id=request.incident_id,
        description=request.description,
    )
    _war_rooms[room.id] = room
    logger.info("war_room.created", room_id=room.id, title=room.title, severity=room.severity)
    return {"war_room": room.model_dump(mode="json")}


@router.get("")
async def list_war_rooms(
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
) -> dict[str, Any]:
    """List war rooms with optional filters."""
    rooms = list(_war_rooms.values())

    if status is not None:
        rooms = [r for r in rooms if r.status == status]
    if severity is not None:
        rooms = [r for r in rooms if r.severity == severity]

    # Sort newest first
    rooms.sort(key=lambda r: r.created_at, reverse=True)
    rooms = rooms[:limit]

    return {
        "war_rooms": [r.model_dump(mode="json") for r in rooms],
        "total": len(rooms),
    }


@router.get("/{room_id}")
async def get_war_room(room_id: str) -> dict[str, Any]:
    """Get war room details including timeline."""
    room = _get_room_or_404(room_id)
    return {"war_room": room.model_dump(mode="json")}


@router.post("/{room_id}/timeline")
async def add_timeline_entry(
    room_id: str,
    request: AddTimelineEntryRequest,
) -> dict[str, Any]:
    """Add a timeline entry to a war room."""
    room = _get_room_or_404(room_id)

    entry = TimelineEntry(
        event_type=request.event_type,
        actor=request.actor,
        content=request.content,
        metadata=request.metadata,
    )
    room.timeline.append(entry)

    logger.info(
        "war_room.timeline_entry_added",
        room_id=room_id,
        event_type=entry.event_type,
        actor=entry.actor,
    )
    return {"entry": entry.model_dump(mode="json")}


@router.post("/{room_id}/responders")
async def add_responder(
    room_id: str,
    request: AddResponderRequest,
) -> dict[str, Any]:
    """Add a responder to a war room."""
    room = _get_room_or_404(room_id)

    # Prevent duplicate responders
    for existing in room.responders:
        if existing.user_id == request.user_id:
            raise HTTPException(status_code=409, detail="Responder already in war room")

    responder = Responder(
        user_id=request.user_id,
        name=request.name,
        role=request.role,
    )
    room.responders.append(responder)

    logger.info(
        "war_room.responder_added",
        room_id=room_id,
        user_id=responder.user_id,
        role=responder.role,
    )
    return {"responder": responder.model_dump(mode="json")}


@router.post("/{room_id}/resolve")
async def resolve_war_room(
    room_id: str,
    request: ResolveWarRoomRequest,
) -> dict[str, Any]:
    """Mark a war room as resolved."""
    room = _get_room_or_404(room_id)

    if room.status == WarRoomStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="War room is already resolved")

    now = datetime.now(UTC)
    room.status = WarRoomStatus.RESOLVED
    room.resolved_at = now

    # Add a timeline entry for the resolution
    entry = TimelineEntry(
        event_type=TimelineEventType.STATUS_CHANGE,
        actor="system",
        content=request.resolution_summary,
        metadata={"new_status": WarRoomStatus.RESOLVED},
    )
    room.timeline.append(entry)

    logger.info("war_room.resolved", room_id=room_id)
    return {"war_room": room.model_dump(mode="json")}
