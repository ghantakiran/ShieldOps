"""Agent collaboration protocol for inter-agent messaging and shared memory.

Allows agents to send messages, share memory within scoped sessions,
and collaborate on complex multi-agent investigations.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class MessagePriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MemoryScope(enum.StrEnum):
    GLOBAL = "global"
    INCIDENT = "incident"
    SESSION = "session"


class SessionStatus(enum.StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"


# ── Models ───────────────────────────────────────────────────────────


class AgentMessage(BaseModel):
    """Message between agents."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_agent: str
    to_agent: str
    subject: str
    body: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str = ""
    reply_to: str | None = None
    expires_at: float | None = None
    acknowledged: bool = False
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SharedMemoryEntry(BaseModel):
    """Shared memory entry for inter-agent data sharing."""

    key: str
    value: Any = None
    written_by: str = ""
    scope: MemoryScope = MemoryScope.GLOBAL
    scope_id: str = ""  # incident_id or session_id
    version: int = 1
    ttl_seconds: int | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return time.time() > self.updated_at + self.ttl_seconds


class CollaborationSession(BaseModel):
    """Scoped collaboration session between agents."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    participants: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)  # message IDs
    shared_memory_keys: list[str] = Field(default_factory=list)
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: float = Field(default_factory=time.time)
    ended_at: float | None = None
    timeout_minutes: int = 60
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return time.time() > self.created_at + self.timeout_minutes * 60


# ── Protocol ─────────────────────────────────────────────────────────


class AgentCollaborationProtocol:
    """Inter-agent messaging and shared memory coordination.

    Parameters
    ----------
    max_messages:
        Maximum total messages stored.
    session_timeout_minutes:
        Default timeout for collaboration sessions.
    """

    def __init__(
        self,
        max_messages: int = 1000,
        session_timeout_minutes: int = 60,
    ) -> None:
        self._messages: dict[str, AgentMessage] = {}
        self._memory: dict[str, SharedMemoryEntry] = {}
        self._sessions: dict[str, CollaborationSession] = {}
        self._max_messages = max_messages
        self._session_timeout = session_timeout_minutes

    # ── Messaging ────────────────────────────────────────────────

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Send a message from one agent to another."""
        self._messages[message.id] = message
        # Add to session if correlation_id matches
        for session in self._sessions.values():
            if session.session_id == message.correlation_id:
                session.messages.append(message.id)
        # Prune old messages
        self._prune_messages()
        logger.debug(
            "agent_message_sent",
            from_agent=message.from_agent,
            to_agent=message.to_agent,
            subject=message.subject,
        )
        return message

    def get_message(self, message_id: str) -> AgentMessage | None:
        return self._messages.get(message_id)

    def get_inbox(
        self,
        agent_type: str,
        unacknowledged_only: bool = False,
        limit: int = 50,
    ) -> list[AgentMessage]:
        """Get messages for a specific agent."""
        messages = [
            m
            for m in self._messages.values()
            if m.to_agent == agent_type and not (m.expires_at and time.time() > m.expires_at)
        ]
        if unacknowledged_only:
            messages = [m for m in messages if not m.acknowledged]
        messages.sort(key=lambda m: m.created_at, reverse=True)
        return messages[:limit]

    def acknowledge(self, message_id: str) -> bool:
        msg = self._messages.get(message_id)
        if msg is None:
            return False
        msg.acknowledged = True
        return True

    def broadcast(
        self,
        from_agent: str,
        subject: str,
        body: str = "",
        agent_types: list[str] | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> list[AgentMessage]:
        """Broadcast a message to multiple agents."""
        targets = agent_types or [
            "investigation",
            "remediation",
            "security",
            "cost",
            "learning",
            "prediction",
            "supervisor",
        ]
        messages: list[AgentMessage] = []
        for target in targets:
            if target == from_agent:
                continue
            msg = AgentMessage(
                from_agent=from_agent,
                to_agent=target,
                subject=subject,
                body=body,
                priority=priority,
            )
            self.send_message(msg)
            messages.append(msg)
        return messages

    def _prune_messages(self) -> None:
        # Remove expired
        now = time.time()
        expired_ids = [
            mid for mid, m in self._messages.items() if m.expires_at and now > m.expires_at
        ]
        for mid in expired_ids:
            del self._messages[mid]
        # Trim to max size
        if len(self._messages) > self._max_messages:
            sorted_msgs = sorted(self._messages.items(), key=lambda x: x[1].created_at)
            to_remove = sorted_msgs[: len(self._messages) - self._max_messages]
            for mid, _ in to_remove:
                del self._messages[mid]

    # ── Shared Memory ────────────────────────────────────────────

    def write_memory(
        self,
        key: str,
        value: Any,
        written_by: str = "",
        scope: MemoryScope = MemoryScope.GLOBAL,
        scope_id: str = "",
        ttl_seconds: int | None = None,
    ) -> SharedMemoryEntry:
        """Write a value to shared memory."""
        fq_key = f"{scope.value}:{scope_id}:{key}" if scope_id else f"{scope.value}:{key}"
        existing = self._memory.get(fq_key)
        version = existing.version + 1 if existing else 1
        entry = SharedMemoryEntry(
            key=key,
            value=value,
            written_by=written_by,
            scope=scope,
            scope_id=scope_id,
            version=version,
            ttl_seconds=ttl_seconds,
        )
        self._memory[fq_key] = entry
        return entry

    def read_memory(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        scope_id: str = "",
    ) -> SharedMemoryEntry | None:
        fq_key = f"{scope.value}:{scope_id}:{key}" if scope_id else f"{scope.value}:{key}"
        entry = self._memory.get(fq_key)
        if entry and entry.expired:
            del self._memory[fq_key]
            return None
        return entry

    def list_memory(
        self,
        scope: MemoryScope | None = None,
        scope_id: str = "",
    ) -> list[SharedMemoryEntry]:
        entries: list[SharedMemoryEntry] = []
        for entry in self._memory.values():
            if entry.expired:
                continue
            if scope and entry.scope != scope:
                continue
            if scope_id and entry.scope_id != scope_id:
                continue
            entries.append(entry)
        return entries

    def delete_memory(
        self,
        key: str,
        scope: MemoryScope = MemoryScope.GLOBAL,
        scope_id: str = "",
    ) -> bool:
        fq_key = f"{scope.value}:{scope_id}:{key}" if scope_id else f"{scope.value}:{key}"
        return self._memory.pop(fq_key, None) is not None

    # ── Sessions ─────────────────────────────────────────────────

    def create_session(
        self,
        participants: list[str],
        timeout_minutes: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CollaborationSession:
        session = CollaborationSession(
            participants=participants,
            timeout_minutes=timeout_minutes or self._session_timeout,
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        logger.info(
            "collaboration_session_created",
            session_id=session.session_id,
            participants=participants,
        )
        return session

    def get_session(self, session_id: str) -> CollaborationSession | None:
        session = self._sessions.get(session_id)
        if session and session.expired and session.status == SessionStatus.ACTIVE:
            session.status = SessionStatus.EXPIRED
        return session

    def end_session(self, session_id: str) -> CollaborationSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.status = SessionStatus.ENDED
        session.ended_at = time.time()
        return session

    def list_sessions(
        self,
        status: SessionStatus | None = None,
        limit: int = 50,
    ) -> list[CollaborationSession]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sessions[:limit]

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        active_sessions = sum(
            1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE
        )
        return {
            "total_messages": len(self._messages),
            "total_memory_entries": len(self._memory),
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "max_messages": self._max_messages,
        }
