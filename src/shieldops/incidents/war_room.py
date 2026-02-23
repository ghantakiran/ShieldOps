"""Incident war room for real-time coordination and escalation."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class WarRoomStatus(enum.StrEnum):
    OPEN = "open"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ParticipantRole(enum.StrEnum):
    COMMANDER = "commander"
    RESPONDER = "responder"
    OBSERVER = "observer"
    COMMUNICATOR = "communicator"


# -- Models --------------------------------------------------------------------


class WarRoomParticipant(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str
    name: str
    role: ParticipantRole = ParticipantRole.RESPONDER
    joined_at: float = Field(default_factory=time.time)


class WarRoomAction(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    war_room_id: str
    description: str
    assignee: str = ""
    status: str = "pending"
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


class WarRoom(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    title: str
    severity: str = "P2"
    status: WarRoomStatus = WarRoomStatus.OPEN
    participants: list[WarRoomParticipant] = Field(default_factory=list)
    actions: list[WarRoomAction] = Field(default_factory=list)
    summary: str = ""
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


# -- Manager -------------------------------------------------------------------


class WarRoomManager:
    """Manage incident war rooms for real-time coordination.

    Parameters
    ----------
    max_rooms:
        Maximum number of war rooms to store.
    auto_escalate_minutes:
        Minutes of inactivity before a room is considered stale.
    """

    def __init__(
        self,
        max_rooms: int = 200,
        auto_escalate_minutes: int = 30,
    ) -> None:
        self._rooms: dict[str, WarRoom] = {}
        self._max_rooms = max_rooms
        self._auto_escalate_minutes = auto_escalate_minutes

    def create_room(
        self,
        incident_id: str,
        title: str,
        severity: str = "P2",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WarRoom:
        if len(self._rooms) >= self._max_rooms:
            raise ValueError(f"Maximum rooms limit reached: {self._max_rooms}")
        room = WarRoom(
            incident_id=incident_id,
            title=title,
            severity=severity,
            created_by=created_by,
            metadata=metadata or {},
        )
        self._rooms[room.id] = room
        logger.info("war_room_created", room_id=room.id, incident_id=incident_id)
        return room

    def add_participant(
        self,
        room_id: str,
        user_id: str,
        name: str,
        role: ParticipantRole = ParticipantRole.RESPONDER,
    ) -> WarRoomParticipant | None:
        room = self._rooms.get(room_id)
        if room is None:
            raise ValueError(f"War room not found: {room_id}")
        participant = WarRoomParticipant(
            user_id=user_id,
            name=name,
            role=role,
        )
        room.participants.append(participant)
        if room.status == WarRoomStatus.OPEN:
            room.status = WarRoomStatus.ACTIVE
        logger.info(
            "war_room_participant_added",
            room_id=room_id,
            user_id=user_id,
            role=role,
        )
        return participant

    def add_action(
        self,
        room_id: str,
        description: str,
        assignee: str = "",
    ) -> WarRoomAction | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        action = WarRoomAction(
            war_room_id=room_id,
            description=description,
            assignee=assignee,
        )
        room.actions.append(action)
        logger.info("war_room_action_added", room_id=room_id, action_id=action.id)
        return action

    def complete_action(
        self,
        room_id: str,
        action_id: str,
    ) -> WarRoomAction | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        for action in room.actions:
            if action.id == action_id:
                action.status = "completed"
                action.completed_at = time.time()
                logger.info(
                    "war_room_action_completed",
                    room_id=room_id,
                    action_id=action_id,
                )
                return action
        return None

    def resolve_room(
        self,
        room_id: str,
        summary: str = "",
    ) -> WarRoom | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        room.status = WarRoomStatus.RESOLVED
        room.resolved_at = time.time()
        if summary:
            room.summary = summary
        logger.info("war_room_resolved", room_id=room_id)
        return room

    def close_room(self, room_id: str) -> WarRoom | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        room.status = WarRoomStatus.CLOSED
        logger.info("war_room_closed", room_id=room_id)
        return room

    def get_room(self, room_id: str) -> WarRoom | None:
        return self._rooms.get(room_id)

    def list_rooms(
        self,
        status: WarRoomStatus | None = None,
    ) -> list[WarRoom]:
        rooms = list(self._rooms.values())
        if status:
            rooms = [r for r in rooms if r.status == status]
        return rooms

    def get_stale_rooms(self) -> list[WarRoom]:
        now = time.time()
        threshold = self._auto_escalate_minutes * 60
        stale: list[WarRoom] = []
        for room in self._rooms.values():
            if room.status not in (WarRoomStatus.OPEN, WarRoomStatus.ACTIVE):
                continue
            # Find latest completed action timestamp
            last_activity = room.created_at
            for action in room.actions:
                if action.completed_at and action.completed_at > last_activity:
                    last_activity = action.completed_at
            if now - last_activity > threshold:
                stale.append(room)
        return stale

    def get_stats(self) -> dict[str, Any]:
        open_rooms = sum(1 for r in self._rooms.values() if r.status == WarRoomStatus.OPEN)
        active_rooms = sum(1 for r in self._rooms.values() if r.status == WarRoomStatus.ACTIVE)
        resolved_rooms = sum(1 for r in self._rooms.values() if r.status == WarRoomStatus.RESOLVED)
        total_actions = sum(len(r.actions) for r in self._rooms.values())
        completed_actions = sum(
            1 for r in self._rooms.values() for a in r.actions if a.status == "completed"
        )
        return {
            "total_rooms": len(self._rooms),
            "open_rooms": open_rooms,
            "active_rooms": active_rooms,
            "resolved_rooms": resolved_rooms,
            "stale_rooms": len(self.get_stale_rooms()),
            "total_actions": total_actions,
            "completed_actions": completed_actions,
        }
