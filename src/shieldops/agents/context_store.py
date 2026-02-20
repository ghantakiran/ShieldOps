"""Persistent context store for agent cross-incident memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class AgentContextStore:
    """Read/write persistent context for agents.

    Wraps repository calls to provide agent-friendly API.
    Supports TTL-based expiry for stale context.
    """

    def __init__(self, repository: Any) -> None:
        self._repo = repository

    async def get(self, agent_type: str, key: str) -> dict[str, Any] | None:
        """Get context value by agent type and key.

        Returns None if the entry is missing or expired.
        """
        record = await self._repo.get_agent_context(agent_type, key)
        if record is None:
            return None

        # Check expiry client-side for safety
        if record.get("expires_at") is not None:
            expires_at = record["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at < datetime.now(UTC):
                logger.debug(
                    "context_expired",
                    agent_type=agent_type,
                    key=key,
                )
                return None

        return record.get("context_value")  # type: ignore[no-any-return]

    async def set(
        self,
        agent_type: str,
        key: str,
        value: dict[str, Any],
        ttl_hours: int | None = None,
    ) -> None:
        """Set or update context value.

        If ttl_hours is provided, context auto-expires after that
        duration from now.
        """
        expires_at: datetime | None = None
        if ttl_hours is not None:
            expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

        await self._repo.upsert_agent_context(
            agent_type=agent_type,
            key=key,
            value=value,
            ttl_hours=ttl_hours,
            expires_at=expires_at,
        )
        logger.info(
            "context_set",
            agent_type=agent_type,
            key=key,
            ttl_hours=ttl_hours,
        )

    async def delete(self, agent_type: str, key: str) -> bool:
        """Delete a context entry. Returns True if found and deleted."""
        deleted = await self._repo.delete_agent_context(agent_type, key)
        if deleted:
            logger.info(
                "context_deleted",
                agent_type=agent_type,
                key=key,
            )
        return deleted  # type: ignore[no-any-return]

    async def search(
        self,
        agent_type: str,
        key_pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search context entries by agent type.

        Optionally filter by key pattern (substring match).
        Expired entries are filtered out of the results.
        """
        records = await self._repo.search_agent_context(agent_type, key_pattern)
        now = datetime.now(UTC)
        results: list[dict[str, Any]] = []
        for record in records:
            expires_at = record.get("expires_at")
            if expires_at is not None:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if expires_at < now:
                    continue
            results.append(record)
        return results

    async def cleanup_expired(self) -> int:
        """Delete all expired context entries.

        Returns count of entries deleted.
        """
        count = await self._repo.cleanup_expired_context()
        if count:
            logger.info("context_cleanup", deleted_count=count)
        return count  # type: ignore[no-any-return]
