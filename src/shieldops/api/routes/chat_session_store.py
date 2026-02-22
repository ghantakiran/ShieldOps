"""Redis-backed chat session persistence for the Security Chat API.

Replaces the in-memory ``_sessions`` dict in ``security_chat.py`` with a
pluggable store that survives restarts and works across multiple replicas.

Two implementations are provided:

* :class:`InMemoryChatStore` -- dict-based fallback for local dev and tests.
* :class:`RedisChatSessionStore` -- production store using ``redis.asyncio``.

Key pattern (Redis): ``shieldops:chat:{session_id}``
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single message within a chat session."""

    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ChatSession(BaseModel):
    """Full state for one chat session."""

    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class ChatSessionStore(ABC):
    """Abstract interface for chat session persistence backends.

    Follows the protocol-based abstraction pattern established in
    ``shieldops.agents.security.protocols`` (CredentialStore, CVESource, etc.).
    """

    store_name: str

    @abstractmethod
    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a session by ID.

        Returns ``None`` when the session does not exist or has expired.
        """

    @abstractmethod
    async def save_session(self, session: ChatSession) -> None:
        """Persist the session, creating or replacing it atomically."""

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID.

        Returns ``True`` if the session existed and was deleted, ``False``
        otherwise.
        """

    @abstractmethod
    async def list_sessions(self) -> list[ChatSession]:
        """Return all active (non-expired) sessions.

        Implementations may return lightweight summaries with truncated
        message lists for performance; callers that need full history
        should follow up with :meth:`get_session`.
        """


# ---------------------------------------------------------------------------
# In-memory implementation (dev / test fallback)
# ---------------------------------------------------------------------------


class InMemoryChatStore(ChatSessionStore):
    """Dict-backed session store for local development and tests.

    Not suitable for production: sessions are lost on restart and are not
    shared across replicas.
    """

    store_name: str = "in_memory"

    def __init__(self, max_messages: int = 50) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._max_messages = max_messages

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Return the session for *session_id*, or ``None`` if not found."""
        return self._sessions.get(session_id)

    async def save_session(self, session: ChatSession) -> None:
        """Persist *session*, trimming to ``max_messages`` oldest first."""
        if len(session.messages) > self._max_messages:
            session = session.model_copy(
                update={"messages": session.messages[-self._max_messages :]},
            )
        session.updated_at = datetime.now(UTC).isoformat()
        self._sessions[session.session_id] = session
        logger.debug(
            "session_saved",
            store="in_memory",
            session_id=session.session_id,
            message_count=len(session.messages),
        )

    async def delete_session(self, session_id: str) -> bool:
        """Remove *session_id* from the store. Returns ``True`` if it existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("session_deleted", store="in_memory", session_id=session_id)
            return True
        return False

    async def list_sessions(self) -> list[ChatSession]:
        """Return all sessions currently held in memory."""
        return list(self._sessions.values())


# ---------------------------------------------------------------------------
# Redis implementation (production)
# ---------------------------------------------------------------------------

_DEFAULT_TTL: int = 86_400  # 24 hours
_DEFAULT_MAX_MESSAGES: int = 50
_KEY_PREFIX: str = "shieldops:chat"


class RedisChatSessionStore(ChatSessionStore):
    """Redis-backed session store for production multi-replica deployments.

    Key format: ``shieldops:chat:{session_id}``

    Sessions are stored as JSON-serialized :class:`ChatSession` objects and
    have a configurable TTL (default 24 h).  Each :meth:`save_session` call
    refreshes the TTL so that active conversations stay alive.

    Parameters
    ----------
    redis_url:
        Redis connection string (e.g. ``redis://localhost:6379/0``).
    ttl:
        Time-to-live in seconds for each session key.  Refreshed on every
        :meth:`save_session` call.
    max_messages:
        Maximum number of messages retained per session.  Oldest messages
        are trimmed on :meth:`save_session`.
    """

    store_name: str = "redis"

    def __init__(
        self,
        redis_url: str,
        ttl: int = _DEFAULT_TTL,
        max_messages: int = _DEFAULT_MAX_MESSAGES,
    ) -> None:
        self._redis_url = redis_url
        self._ttl = ttl
        self._max_messages = max_messages
        self._client: Any = None

    # -- Lifecycle --------------------------------------------------------

    async def connect(self) -> None:
        """Open the async Redis connection pool."""
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        logger.info(
            "chat_session_store_connected",
            store="redis",
            redis_url=self._redis_url,
            ttl=self._ttl,
            max_messages=self._max_messages,
        )

    async def disconnect(self) -> None:
        """Close the async Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("chat_session_store_disconnected", store="redis")

    # -- Key helpers -------------------------------------------------------

    @staticmethod
    def _make_key(session_id: str) -> str:
        """Build the fully-qualified Redis key for a session."""
        return f"{_KEY_PREFIX}:{session_id}"

    # -- Serialization -----------------------------------------------------

    @staticmethod
    def _serialize(session: ChatSession) -> str:
        """Serialize a ChatSession to a JSON string via Pydantic."""
        return session.model_dump_json()

    @staticmethod
    def _deserialize(raw: str) -> ChatSession:
        """Deserialize a JSON string back to a ChatSession."""
        return ChatSession.model_validate_json(raw)

    # -- Guards ------------------------------------------------------------

    def _ensure_connected(self) -> None:
        """Raise if :meth:`connect` has not been called."""
        if self._client is None:
            raise RuntimeError("RedisChatSessionStore is not connected. Call connect() first.")

    # -- Store interface ---------------------------------------------------

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Retrieve a session by ID from Redis.

        Returns ``None`` when the key does not exist (expired or never
        created).
        """
        self._ensure_connected()
        key = self._make_key(session_id)

        try:
            raw: str | None = await self._client.get(key)
        except Exception:
            logger.exception("chat_store_get_error", session_id=session_id)
            return None

        if raw is None:
            return None

        try:
            session = self._deserialize(raw)
        except (json.JSONDecodeError, ValueError):
            logger.error(
                "chat_store_deserialize_error",
                session_id=session_id,
            )
            return None

        logger.debug(
            "session_loaded",
            store="redis",
            session_id=session_id,
            message_count=len(session.messages),
        )
        return session

    async def save_session(self, session: ChatSession) -> None:
        """Persist a session to Redis, trimming messages and refreshing TTL."""
        self._ensure_connected()

        # Enforce max messages by keeping only the most recent N
        if len(session.messages) > self._max_messages:
            session = session.model_copy(
                update={"messages": session.messages[-self._max_messages :]},
            )

        session.updated_at = datetime.now(UTC).isoformat()
        key = self._make_key(session.session_id)
        payload = self._serialize(session)

        try:
            await self._client.set(key, payload, ex=self._ttl)
        except Exception:
            logger.exception(
                "chat_store_save_error",
                session_id=session.session_id,
            )
            raise

        logger.debug(
            "session_saved",
            store="redis",
            session_id=session.session_id,
            message_count=len(session.messages),
            ttl=self._ttl,
        )

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session key from Redis.

        Returns ``True`` when the key existed and was removed.
        """
        self._ensure_connected()
        key = self._make_key(session_id)

        try:
            deleted_count: int = await self._client.delete(key)
        except Exception:
            logger.exception("chat_store_delete_error", session_id=session_id)
            return False

        if deleted_count > 0:
            logger.info("session_deleted", store="redis", session_id=session_id)
            return True
        return False

    async def list_sessions(self) -> list[ChatSession]:
        """Scan for all session keys and return their deserialized state.

        Uses ``SCAN`` (via ``scan_iter``) to avoid blocking Redis on large
        keyspaces.  Sessions that fail to deserialize are silently skipped
        and logged as warnings.
        """
        self._ensure_connected()
        pattern = f"{_KEY_PREFIX}:*"
        sessions: list[ChatSession] = []

        try:
            async for key in self._client.scan_iter(match=pattern):
                raw: str | None = await self._client.get(key)
                if raw is None:
                    continue  # Expired between SCAN and GET
                try:
                    sessions.append(self._deserialize(raw))
                except (json.JSONDecodeError, ValueError):
                    logger.warning("chat_store_skip_corrupt_session", key=key)
        except Exception:
            logger.exception("chat_store_list_error")

        logger.debug("sessions_listed", store="redis", count=len(sessions))
        return sessions

    # -- Utilities ---------------------------------------------------------

    async def health_check(self) -> dict[str, str]:
        """Verify Redis connectivity for the chat store."""
        self._ensure_connected()
        try:
            await self._client.ping()
            return {"status": "healthy"}
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}
