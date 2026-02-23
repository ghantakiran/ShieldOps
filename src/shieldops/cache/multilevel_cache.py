"""Multi-level cache: L1 in-memory LRU + L2 Redis.

Every cache read currently hits Redis over the network. This module adds an
in-process LRU cache (L1) in front of Redis (L2) with auto-promotion,
per-namespace statistics, and TTL-based eviction.
"""

from __future__ import annotations

import enum
import threading
import time
from collections import OrderedDict
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class CacheLevel(enum.StrEnum):
    """Where a cache hit occurred."""

    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    MISS = "miss"


# ── Stats model ──────────────────────────────────────────────────────


class CacheStats(BaseModel):
    """Per-namespace and aggregate cache statistics."""

    l1_hits: int = 0
    l2_hits: int = 0
    misses: int = 0
    l1_evictions: int = 0
    l1_size: int = 0
    l1_max_size: int = 0
    total_requests: int = 0
    l1_hit_ratio: float = 0.0
    l2_hit_ratio: float = 0.0
    overall_hit_ratio: float = 0.0


class _L1Entry:
    """Single entry in the L1 cache with timestamp for TTL."""

    __slots__ = ("value", "expires_at", "namespace")

    def __init__(self, value: Any, ttl: int, namespace: str) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl
        self.namespace = namespace

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class MultiLevelCache:
    """L1 (in-memory LRU) + L2 (Redis) cache with auto-promotion.

    Parameters
    ----------
    l2_cache:
        An existing ``RedisCache`` instance used as the L2 layer.
    l1_max_size:
        Maximum number of entries in the in-memory LRU.
    l1_ttl_seconds:
        Default TTL for L1 entries. A shorter TTL keeps L1 fresher.
    l1_enabled:
        When ``False``, L1 is bypassed and all reads go straight to L2.
    """

    def __init__(
        self,
        l2_cache: Any,
        l1_max_size: int = 1000,
        l1_ttl_seconds: int = 60,
        l1_enabled: bool = True,
    ) -> None:
        self._l2 = l2_cache
        self._l1_max_size = l1_max_size
        self._l1_ttl = l1_ttl_seconds
        self._l1_enabled = l1_enabled

        # LRU implemented via OrderedDict (most-recently-used at end)
        self._l1: OrderedDict[str, _L1Entry] = OrderedDict()
        self._lock = threading.Lock()

        # Stats counters
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0
        self._l1_evictions = 0

    # ── Key helpers ──────────────────────────────────────────────

    @staticmethod
    def _fq(key: str, namespace: str) -> str:
        return f"{namespace}:{key}"

    # ── L1 operations (thread-safe) ──────────────────────────────

    def _l1_get(self, fq_key: str) -> tuple[bool, Any]:
        """Get from L1. Returns (found, value)."""
        if not self._l1_enabled:
            return False, None
        with self._lock:
            entry = self._l1.get(fq_key)
            if entry is None:
                return False, None
            if entry.expired:
                del self._l1[fq_key]
                return False, None
            # Move to end (most-recently-used)
            self._l1.move_to_end(fq_key)
            return True, entry.value

    def _l1_put(self, fq_key: str, value: Any, ttl: int | None, namespace: str) -> None:
        """Insert/update L1 entry, evicting LRU if at capacity."""
        if not self._l1_enabled:
            return
        effective_ttl = ttl if ttl is not None else self._l1_ttl
        with self._lock:
            if fq_key in self._l1:
                self._l1.move_to_end(fq_key)
                self._l1[fq_key] = _L1Entry(value, effective_ttl, namespace)
                return
            # Evict LRU entries if at capacity
            while len(self._l1) >= self._l1_max_size:
                self._l1.popitem(last=False)
                self._l1_evictions += 1
            self._l1[fq_key] = _L1Entry(value, effective_ttl, namespace)

    def _l1_delete(self, fq_key: str) -> None:
        with self._lock:
            self._l1.pop(fq_key, None)

    def _l1_clear(self) -> int:
        """Clear all L1 entries. Returns count removed."""
        with self._lock:
            count = len(self._l1)
            self._l1.clear()
            return count

    # ── Public API ───────────────────────────────────────────────

    async def get(self, key: str, namespace: str = "default") -> Any | None:
        """Retrieve value: L1 → L2 (auto-promote) → MISS."""
        fq_key = self._fq(key, namespace)

        # L1 check
        found, value = self._l1_get(fq_key)
        if found:
            self._l1_hits += 1
            return value

        # L2 check
        value = await self._l2.get(key, namespace=namespace)
        if value is not None:
            self._l2_hits += 1
            # Auto-promote to L1
            self._l1_put(fq_key, value, None, namespace)
            return value

        self._misses += 1
        return None

    async def get_with_level(
        self, key: str, namespace: str = "default"
    ) -> tuple[Any | None, CacheLevel]:
        """Like ``get`` but also returns which cache level served the value."""
        fq_key = self._fq(key, namespace)

        found, value = self._l1_get(fq_key)
        if found:
            self._l1_hits += 1
            return value, CacheLevel.L1_MEMORY

        value = await self._l2.get(key, namespace=namespace)
        if value is not None:
            self._l2_hits += 1
            self._l1_put(fq_key, value, None, namespace)
            return value, CacheLevel.L2_REDIS

        self._misses += 1
        return None, CacheLevel.MISS

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        namespace: str = "default",
    ) -> None:
        """Write to both L1 and L2."""
        fq_key = self._fq(key, namespace)
        self._l1_put(fq_key, value, ttl, namespace)
        await self._l2.set(key, value, ttl=ttl, namespace=namespace)

    async def delete(self, key: str, namespace: str = "default") -> None:
        """Remove from both L1 and L2."""
        fq_key = self._fq(key, namespace)
        self._l1_delete(fq_key)
        await self._l2.delete(key, namespace=namespace)

    async def invalidate_namespace(self, namespace: str) -> int:
        """Clear all L1 entries for *namespace* and invalidate L2 pattern."""
        l1_removed = 0
        with self._lock:
            keys_to_remove = [k for k, e in self._l1.items() if e.namespace == namespace]
            for k in keys_to_remove:
                del self._l1[k]
                l1_removed += 1

        l2_removed = await self._l2.invalidate_pattern(f"{namespace}:*")
        logger.info(
            "namespace_invalidated",
            namespace=namespace,
            l1_removed=l1_removed,
            l2_removed=l2_removed,
        )
        return l1_removed + int(l2_removed)

    async def flush_all(self) -> int:
        """Clear both L1 and L2 completely."""
        l1_count = self._l1_clear()
        l2_count = await self._l2.flush_all()
        return l1_count + int(l2_count)

    async def warmup(self, keys: list[dict[str, str]]) -> int:
        """Pre-populate L1 from L2 for a list of keys.

        Each item should have ``key`` and optionally ``namespace``.
        Returns the number of entries warmed up.
        """
        warmed = 0
        for item in keys:
            key = item.get("key", "")
            ns = item.get("namespace", "default")
            if not key:
                continue
            value = await self._l2.get(key, namespace=ns)
            if value is not None:
                fq_key = self._fq(key, ns)
                self._l1_put(fq_key, value, None, ns)
                warmed += 1
        logger.info("cache_warmup_complete", warmed=warmed, requested=len(keys))
        return warmed

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> CacheStats:
        """Return aggregate cache statistics."""
        total = self._l1_hits + self._l2_hits + self._misses
        with self._lock:
            l1_size = len(self._l1)
        return CacheStats(
            l1_hits=self._l1_hits,
            l2_hits=self._l2_hits,
            misses=self._misses,
            l1_evictions=self._l1_evictions,
            l1_size=l1_size,
            l1_max_size=self._l1_max_size,
            total_requests=total,
            l1_hit_ratio=round(self._l1_hits / total * 100, 2) if total else 0.0,
            l2_hit_ratio=round(self._l2_hits / total * 100, 2) if total else 0.0,
            overall_hit_ratio=(
                round((self._l1_hits + self._l2_hits) / total * 100, 2) if total else 0.0
            ),
        )

    def reset_stats(self) -> None:
        """Reset all hit/miss counters."""
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0
        self._l1_evictions = 0

    @property
    def l1_enabled(self) -> bool:
        return self._l1_enabled

    @l1_enabled.setter
    def l1_enabled(self, value: bool) -> None:
        self._l1_enabled = value
        if not value:
            self._l1_clear()
