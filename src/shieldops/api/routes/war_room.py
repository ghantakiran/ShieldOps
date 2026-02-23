"""Incident war room API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/war-rooms", tags=["War Rooms"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "War room service unavailable")
    return _manager


class CreateRoomRequest(BaseModel):
    incident_id: str
    title: str
    severity: str = "P2"
    created_by: str = ""
    metadata: dict[str, Any] | None = None


class AddParticipantRequest(BaseModel):
    user_id: str
    name: str
    role: str = "responder"


class AddActionRequest(BaseModel):
    description: str
    assignee: str = ""


@router.post("")
async def create_room(
    body: CreateRoomRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    room = mgr.create_room(**body.model_dump())
    return room.model_dump()


@router.get("")
async def list_rooms(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [r.model_dump() for r in mgr.list_rooms(status=status)]


@router.get("/stale")
async def get_stale_rooms(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [r.model_dump() for r in mgr.get_stale_rooms()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()


@router.get("/{room_id}")
async def get_room(
    room_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    room = mgr.get_room(room_id)
    if room is None:
        raise HTTPException(404, f"Room '{room_id}' not found")
    return room.model_dump()


@router.post("/{room_id}/participants")
async def add_participant(
    room_id: str,
    body: AddParticipantRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    participant = mgr.add_participant(room_id=room_id, **body.model_dump())
    if participant is None:
        raise HTTPException(404, f"Room '{room_id}' not found")
    return participant.model_dump()


@router.post("/{room_id}/actions")
async def add_action(
    room_id: str,
    body: AddActionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    action = mgr.add_action(room_id=room_id, **body.model_dump())
    if action is None:
        raise HTTPException(404, f"Room '{room_id}' not found")
    return action.model_dump()


@router.put("/{room_id}/close")
async def close_room(
    room_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    room = mgr.close_room(room_id)
    if room is None:
        raise HTTPException(404, f"Room '{room_id}' not found")
    return room.model_dump()
