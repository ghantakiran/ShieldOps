"""Redis cache layer for ShieldOps.

Provides async cache-aside caching with JSON serialization,
key namespacing, TTL management, and hit/miss tracking.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

try:
    import orjson

    def _dumps(obj: Any) -> bytes:
        return orjson.dumps(obj)

    def _loads(data: bytes | str) -> Any:
        return orjson.loads(data)

except ImportError:
    import json

    def _dumps(obj: Any) -> bytes:  # type: ignore[misc]
        return json.dumps(obj, default=str).encode()

    def _loads(data: bytes | str) -> Any:  # type: ignore[misc]
        return json.loads(data)


logger = structlog.get_logger()


class RedisCache:
    """Async Redis cache with JSON serialization and hit/miss tracking.

    Key format: ``{prefix}:{namespace}:{key}``

    Parameters
    ----------
    redis_url:
        Redis connection string (e.g. ``redis://localhost:6379/0``).
    default_ttl:
        Default time-to-live in seconds for cached entries.
    key_prefix:
        Global prefix prepended to all cache keys.
    """

    def __init__(
        self,
        redis_url: str,
        default_ttl: int = 300,
        key_prefix: str = "shieldops",
    ) -> None:
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._key_prefix = key_prefix
        self._client: Any = None
        self._hits: int = 0
        self._misses: int = 0

    # ── Lifecycle ────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the async Redis connection pool."""
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._redis_url,
            decode_responses=False,
        )
        logger.info("redis_cache_connected", url=self._redis_url)

    async def disconnect(self) -> None:
        """Close the async Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("redis_cache_disconnected")

    # ── Key helpers ──────────────────────────────────────────────

    def _make_key(self, key: str, namespace: str = "default") -> str:
        """Build a fully-qualified cache key."""
        return f"{self._key_prefix}:{namespace}:{key}"

    # ── Core operations ──────────────────────────────────────────

    async def get(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve a cached value by key.

        Returns ``None`` on a cache miss and increments the miss counter.
        """
        fq_key = self._make_key(key, namespace)
        raw = await self._client.get(fq_key)
        if raw is None:
            self._misses += 1
            return None
        self._hits += 1
        return _loads(raw)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        namespace: str = "default",
    ) -> None:
        """Store a value in the cache with an optional TTL override."""
        fq_key = self._make_key(key, namespace)
        effective_ttl = ttl if ttl is not None else self._default_ttl
        serialized = _dumps(value)
        await self._client.set(fq_key, serialized, ex=effective_ttl)

    async def delete(self, key: str, namespace: str = "default") -> None:
        """Remove a single key from the cache."""
        fq_key = self._make_key(key, namespace)
        await self._client.delete(fq_key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern.

        Returns the number of keys deleted.
        """
        full_pattern = f"{self._key_prefix}:{pattern}"
        deleted = 0
        async for matched_key in self._client.scan_iter(match=full_pattern):
            await self._client.delete(matched_key)
            deleted += 1
        logger.info(
            "cache_invalidated",
            pattern=full_pattern,
            deleted=deleted,
        )
        return deleted

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int | None = None,
        namespace: str = "default",
    ) -> Any:
        """Cache-aside: return cached value or call *factory* and cache the result.

        The factory may be sync or async -- both are supported.
        """
        cached = await self.get(key, namespace=namespace)
        if cached is not None:
            return cached

        import asyncio

        result = factory()
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            result = await result

        await self.set(key, result, ttl=ttl, namespace=namespace)
        return result

    # ── Stats & health ───────────────────────────────────────────

    async def get_stats(self) -> dict[str, Any]:
        """Return cache statistics (hits, misses, total keys)."""
        total = self._hits + self._misses
        ratio = (self._hits / total * 100) if total > 0 else 0.0

        # Count keys under our prefix
        keys_count = 0
        async for _ in self._client.scan_iter(
            match=f"{self._key_prefix}:*",
        ):
            keys_count += 1

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_ratio_pct": round(ratio, 2),
            "keys_count": keys_count,
        }

    async def health_check(self) -> dict[str, str]:
        """Verify Redis connectivity."""
        try:
            await self._client.ping()
            return {"status": "healthy"}
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}

    async def flush_all(self) -> int:
        """Delete all keys under the configured prefix.

        Returns the number of keys deleted.
        """
        return await self.invalidate_pattern("*")
