"""Action rate limiter using Redis for OPA rate-limit context enrichment."""

from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()


class ActionRateLimiter:
    """Tracks action counts per environment using Redis INCR with 1-hour TTL.

    Provides context for OPA's rate-limiting deny rules.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._client: Redis | None = None

    async def _ensure_client(self) -> Redis:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(  # type: ignore[no-untyped-call]
                self._redis_url, decode_responses=True
            )
        return self._client

    def _key(self, environment: str) -> str:
        hour = datetime.now(UTC).strftime("%Y%m%d%H")
        return f"shieldops:rate:{environment}:{hour}"

    async def count_recent_actions(self, environment: str) -> int:
        """Get the number of actions in the current hour for an environment."""
        try:
            client = await self._ensure_client()
            count = await client.get(self._key(environment))
            return int(count) if count else 0
        except Exception as e:
            logger.warning("rate_limiter_read_failed", error=str(e))
            return 0

    async def increment(self, environment: str) -> int:
        """Increment the action count and return the new total."""
        try:
            client = await self._ensure_client()
            key = self._key(environment)
            count = await client.incr(key)
            await client.expire(key, 3600)
            return int(count)
        except Exception as e:
            logger.warning("rate_limiter_incr_failed", error=str(e))
            return 0

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
