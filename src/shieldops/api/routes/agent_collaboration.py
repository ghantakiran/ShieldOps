"""Agent collaboration protocol API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.collaboration import (
    AgentMessage,
    MemoryScope,
    MessagePriority,
    SessionStatus,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/agents/collaboration", tags=["Agent Collaboration"])

_protocol: Any = None


def set_protocol(protocol: Any) -> None:
    global _protocol
    _protocol = protocol


def _get_protocol() -> Any:
    if _protocol is None:
        raise HTTPException(503, "Collaboration service unavailable")
    return _protocol


class SendMessageRequest(BaseModel):
    from_agent: str
    to_agent: str
    subject: str
    body: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str = ""
    expires_in_seconds: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WriteMemoryRequest(BaseModel):
    key: str
    value: Any = None
    written_by: str = ""
    scope: MemoryScope = MemoryScope.GLOBAL
    scope_id: str = ""
    ttl_seconds: int | None = None


class CreateSessionRequest(BaseModel):
    participants: list[str]
    timeout_minutes: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BroadcastRequest(BaseModel):
    from_agent: str
    subject: str
    body: str = ""
    agent_types: list[str] | None = None
    priority: MessagePriority = MessagePriority.NORMAL


@router.post("/messages")
async def send_message(
    body: SendMessageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    import time

    expires_at = time.time() + body.expires_in_seconds if body.expires_in_seconds else None
    msg = AgentMessage(
        from_agent=body.from_agent,
        to_agent=body.to_agent,
        subject=body.subject,
        body=body.body,
        priority=body.priority,
        correlation_id=body.correlation_id,
        expires_at=expires_at,
        metadata=body.metadata,
    )
    return proto.send_message(msg).model_dump()


@router.get("/messages/{agent_type}")
async def get_inbox(
    agent_type: str,
    unacknowledged_only: bool = False,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    proto = _get_protocol()
    return [m.model_dump() for m in proto.get_inbox(agent_type, unacknowledged_only, limit)]


@router.post("/messages/{message_id}/acknowledge")
async def acknowledge_message(
    message_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, bool]:
    proto = _get_protocol()
    return {"acknowledged": proto.acknowledge(message_id)}


@router.post("/messages/broadcast")
async def broadcast_message(
    body: BroadcastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    proto = _get_protocol()
    msgs = proto.broadcast(
        body.from_agent,
        body.subject,
        body.body,
        body.agent_types,
        body.priority,
    )
    return [m.model_dump() for m in msgs]


@router.post("/memory")
async def write_memory(
    body: WriteMemoryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    entry = proto.write_memory(
        body.key,
        body.value,
        body.written_by,
        body.scope,
        body.scope_id,
        body.ttl_seconds,
    )
    return entry.model_dump()


@router.get("/memory")
async def list_memory(
    scope: MemoryScope | None = None,
    scope_id: str = "",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    proto = _get_protocol()
    return [e.model_dump() for e in proto.list_memory(scope, scope_id)]


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    session = proto.create_session(body.participants, body.timeout_minutes, body.metadata)
    return session.model_dump()


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    session = proto.get_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return session.model_dump()


@router.put("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    session = proto.end_session(session_id)
    if session is None:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return session.model_dump()


@router.get("/sessions")
async def list_sessions(
    status: SessionStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    proto = _get_protocol()
    return [s.model_dump() for s in proto.list_sessions(status, limit)]


@router.get("/stats")
async def get_collaboration_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    proto = _get_protocol()
    return proto.get_stats()
