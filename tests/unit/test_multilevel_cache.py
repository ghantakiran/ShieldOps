"""Tests for the multi-level cache (L1 in-memory LRU + L2 Redis)."""

from __future__ import annotations

import threading
import time
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.cache.multilevel_cache import CacheLevel, CacheStats, MultiLevelCache

# ── Helpers ──────────────────────────────────────────────────────────


def _make_l2(**overrides: object) -> AsyncMock:
    """Return an AsyncMock simulating a RedisCache with sensible defaults."""
    l2 = AsyncMock()
    l2.get = AsyncMock(return_value=None)
    l2.set = AsyncMock()
    l2.delete = AsyncMock()
    l2.invalidate_pattern = AsyncMock(return_value=0)
    l2.flush_all = AsyncMock(return_value=0)
    for k, v in overrides.items():
        setattr(l2, k, v)
    return l2


def _make_cache(l2: AsyncMock | None = None, **kwargs: object) -> MultiLevelCache:
    return MultiLevelCache(l2 or _make_l2(), **kwargs)


# =========================================================================
# L1 hit returns value without hitting L2
# =========================================================================


class TestL1Hit:
    @pytest.mark.asyncio
    async def test_l1_hit_returns_cached_value(self):
        l2 = _make_l2()
        cache = _make_cache(l2, l1_max_size=10)
        await cache.set("key1", "value1")
        l2.get.reset_mock()

        result = await cache.get("key1")

        assert result == "value1"
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_l1_hit_increments_l1_hits(self):
        cache = _make_cache()
        await cache.set("k", 42)
        await cache.get("k")

        stats = cache.get_stats()
        assert stats.l1_hits == 1

    @pytest.mark.asyncio
    async def test_l1_hit_with_namespace(self):
        l2 = _make_l2()
        cache = _make_cache(l2)
        await cache.set("k", "ns_val", namespace="ns1")
        l2.get.reset_mock()

        result = await cache.get("k", namespace="ns1")
        assert result == "ns_val"
        l2.get.assert_not_called()


# =========================================================================
# L2 hit auto-promotes to L1
# =========================================================================


class TestL2Hit:
    @pytest.mark.asyncio
    async def test_l2_hit_returns_value(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="from_redis")
        cache = _make_cache(l2)

        result = await cache.get("k")
        assert result == "from_redis"

    @pytest.mark.asyncio
    async def test_l2_hit_promotes_to_l1(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="promoted")
        cache = _make_cache(l2)

        await cache.get("k")
        # Second get should be L1 hit
        l2.get.reset_mock()
        result = await cache.get("k")
        assert result == "promoted"
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_l2_hit_increments_l2_hits(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="v")
        cache = _make_cache(l2)

        await cache.get("k")
        stats = cache.get_stats()
        assert stats.l2_hits == 1


# =========================================================================
# Cache miss
# =========================================================================


class TestCacheMiss:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self):
        cache = _make_cache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_miss_increments_misses(self):
        cache = _make_cache()
        await cache.get("nonexistent")
        stats = cache.get_stats()
        assert stats.misses == 1


# =========================================================================
# set() writes to both levels
# =========================================================================


class TestSet:
    @pytest.mark.asyncio
    async def test_set_writes_to_l2(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.set("k", "v")
        l2.set.assert_awaited_once_with("k", "v", ttl=None, namespace="default")

    @pytest.mark.asyncio
    async def test_set_populates_l1(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.set("k", "v")
        l2.get.reset_mock()
        result = await cache.get("k")
        assert result == "v"
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.set("k", "v", ttl=120)
        l2.set.assert_awaited_once_with("k", "v", ttl=120, namespace="default")

    @pytest.mark.asyncio
    async def test_set_with_namespace(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.set("k", "v", namespace="ns")
        l2.set.assert_awaited_once_with("k", "v", ttl=None, namespace="ns")

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_l1_entry(self):
        cache = _make_cache()
        await cache.set("k", "old")
        await cache.set("k", "new")

        result = await cache.get("k")
        assert result == "new"


# =========================================================================
# delete() removes from both levels
# =========================================================================


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_from_l2(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.delete("k")
        l2.delete.assert_awaited_once_with("k", namespace="default")

    @pytest.mark.asyncio
    async def test_delete_removes_from_l1(self):
        cache = _make_cache()
        await cache.set("k", "v")
        await cache.delete("k")

        result = await cache.get("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_with_namespace(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.delete("k", namespace="ns")
        l2.delete.assert_awaited_once_with("k", namespace="ns")


# =========================================================================
# LRU eviction when L1 at capacity
# =========================================================================


class TestLRUEviction:
    @pytest.mark.asyncio
    async def test_evicts_lru_when_at_capacity(self):
        cache = _make_cache(l1_max_size=2)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)  # should evict "a"

        result = await cache.get("a")
        # "a" was evicted from L1, L2 mock returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_eviction_increments_stats(self):
        cache = _make_cache(l1_max_size=1)
        await cache.set("a", 1)
        await cache.set("b", 2)

        stats = cache.get_stats()
        assert stats.l1_evictions >= 1

    @pytest.mark.asyncio
    async def test_recently_accessed_survives_eviction(self):
        l2 = _make_l2()
        cache = _make_cache(l2, l1_max_size=2)
        await cache.set("a", 1)
        await cache.set("b", 2)
        # Access "a" to make it recently used
        await cache.get("a")
        # Now insert "c" — should evict "b", not "a"
        await cache.set("c", 3)

        l2.get.reset_mock()
        result = await cache.get("a")
        assert result == 1
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_l1_size_never_exceeds_max(self):
        cache = _make_cache(l1_max_size=3)
        for i in range(10):
            await cache.set(f"key{i}", i)
        stats = cache.get_stats()
        assert stats.l1_size <= 3


# =========================================================================
# TTL expiration in L1
# =========================================================================


class TestTTLExpiration:
    @pytest.mark.asyncio
    async def test_expired_entry_returns_miss(self):
        cache = _make_cache(l1_ttl_seconds=1)
        await cache.set("k", "v")

        with patch("shieldops.cache.multilevel_cache.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 100
            found, _ = cache._l1_get("default:k")
            assert found is False

    @pytest.mark.asyncio
    async def test_non_expired_entry_found(self):
        cache = _make_cache(l1_ttl_seconds=3600)
        await cache.set("k", "v")

        found, val = cache._l1_get("default:k")
        assert found is True
        assert val == "v"


# =========================================================================
# invalidate_namespace()
# =========================================================================


class TestInvalidateNamespace:
    @pytest.mark.asyncio
    async def test_clears_l1_for_namespace(self):
        cache = _make_cache()
        await cache.set("a", 1, namespace="ns1")
        await cache.set("b", 2, namespace="ns1")
        await cache.set("c", 3, namespace="ns2")

        await cache.invalidate_namespace("ns1")

        # ns1 keys gone from L1
        assert await cache.get("a", namespace="ns1") is None
        # ns2 key still in L1
        result = await cache.get("c", namespace="ns2")
        assert result == 3

    @pytest.mark.asyncio
    async def test_calls_l2_invalidate_pattern(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        await cache.invalidate_namespace("ns1")
        l2.invalidate_pattern.assert_awaited_once_with("ns1:*")

    @pytest.mark.asyncio
    async def test_returns_total_removed_count(self):
        l2 = _make_l2()
        l2.invalidate_pattern = AsyncMock(return_value=5)
        cache = _make_cache(l2)
        await cache.set("k", "v", namespace="ns")

        count = await cache.invalidate_namespace("ns")
        assert count == 1 + 5  # 1 from L1 + 5 from L2


# =========================================================================
# flush_all()
# =========================================================================


class TestFlushAll:
    @pytest.mark.asyncio
    async def test_clears_both_levels(self):
        l2 = _make_l2()
        l2.flush_all = AsyncMock(return_value=10)
        cache = _make_cache(l2)
        await cache.set("k", "v")

        count = await cache.flush_all()
        assert count == 1 + 10

    @pytest.mark.asyncio
    async def test_l1_empty_after_flush(self):
        cache = _make_cache()
        await cache.set("k", "v")
        await cache.flush_all()

        stats = cache.get_stats()
        assert stats.l1_size == 0


# =========================================================================
# warmup()
# =========================================================================


class TestWarmup:
    @pytest.mark.asyncio
    async def test_populates_l1_from_l2(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="warmed")
        cache = _make_cache(l2)

        count = await cache.warmup([{"key": "k1"}, {"key": "k2"}])
        assert count == 2

        l2.get.reset_mock()
        result = await cache.get("k1")
        assert result == "warmed"
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_missing_keys(self):
        l2 = _make_l2()
        l2.get = AsyncMock(side_effect=[None, "found"])
        cache = _make_cache(l2)

        count = await cache.warmup([{"key": "missing"}, {"key": "present"}])
        assert count == 1

    @pytest.mark.asyncio
    async def test_skips_empty_key(self):
        l2 = _make_l2()
        cache = _make_cache(l2)

        count = await cache.warmup([{"key": ""}, {"namespace": "ns"}])
        assert count == 0
        l2.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_namespace(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="v")
        cache = _make_cache(l2)

        await cache.warmup([{"key": "k", "namespace": "ns"}])
        l2.get.assert_awaited_once_with("k", namespace="ns")


# =========================================================================
# get_with_level()
# =========================================================================


class TestGetWithLevel:
    @pytest.mark.asyncio
    async def test_l1_hit_returns_l1_memory(self):
        cache = _make_cache()
        await cache.set("k", "v")

        val, level = await cache.get_with_level("k")
        assert val == "v"
        assert level == CacheLevel.L1_MEMORY

    @pytest.mark.asyncio
    async def test_l2_hit_returns_l2_redis(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="from_l2")
        cache = _make_cache(l2)

        val, level = await cache.get_with_level("k")
        assert val == "from_l2"
        assert level == CacheLevel.L2_REDIS

    @pytest.mark.asyncio
    async def test_miss_returns_miss_level(self):
        cache = _make_cache()

        val, level = await cache.get_with_level("nope")
        assert val is None
        assert level == CacheLevel.MISS


# =========================================================================
# Stats tracking
# =========================================================================


class TestStats:
    @pytest.mark.asyncio
    async def test_initial_stats_all_zero(self):
        cache = _make_cache()
        stats = cache.get_stats()
        assert stats.l1_hits == 0
        assert stats.l2_hits == 0
        assert stats.misses == 0
        assert stats.l1_evictions == 0
        assert stats.total_requests == 0

    @pytest.mark.asyncio
    async def test_hit_ratios_calculated(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="val")
        cache = _make_cache(l2)

        # 1 L2 hit, then 1 L1 hit, then 1 miss
        await cache.get("k")  # L2 hit + promote
        l2.get.reset_mock()
        l2.get.return_value = None
        await cache.get("k")  # L1 hit
        await cache.get("other")  # miss

        stats = cache.get_stats()
        assert stats.total_requests == 3
        assert stats.l1_hits == 1
        assert stats.l2_hits == 1
        assert stats.misses == 1
        assert stats.l1_hit_ratio == pytest.approx(33.33, abs=0.01)
        assert stats.overall_hit_ratio == pytest.approx(66.67, abs=0.01)

    @pytest.mark.asyncio
    async def test_l1_size_tracked(self):
        cache = _make_cache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        stats = cache.get_stats()
        assert stats.l1_size == 2

    @pytest.mark.asyncio
    async def test_l1_max_size_reported(self):
        cache = _make_cache(l1_max_size=500)
        stats = cache.get_stats()
        assert stats.l1_max_size == 500

    @pytest.mark.asyncio
    async def test_stats_zero_division_safe(self):
        cache = _make_cache()
        stats = cache.get_stats()
        assert stats.l1_hit_ratio == 0.0
        assert stats.l2_hit_ratio == 0.0
        assert stats.overall_hit_ratio == 0.0


# =========================================================================
# l1_enabled=False bypasses L1
# =========================================================================


class TestL1Disabled:
    @pytest.mark.asyncio
    async def test_get_bypasses_l1(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="redis_only")
        cache = _make_cache(l2, l1_enabled=False)

        await cache.set("k", "v")
        result = await cache.get("k")
        assert result == "redis_only"
        l2.get.assert_awaited()

    @pytest.mark.asyncio
    async def test_set_still_writes_to_l2(self):
        l2 = _make_l2()
        cache = _make_cache(l2, l1_enabled=False)

        await cache.set("k", "v")
        l2.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_l1_enabled_property_getter(self):
        cache = _make_cache(l1_enabled=False)
        assert cache.l1_enabled is False

    @pytest.mark.asyncio
    async def test_l1_enabled_setter_clears_l1(self):
        cache = _make_cache(l1_enabled=True)
        await cache.set("k", "v")
        assert cache.get_stats().l1_size == 1

        cache.l1_enabled = False
        assert cache.get_stats().l1_size == 0


# =========================================================================
# reset_stats()
# =========================================================================


class TestResetStats:
    @pytest.mark.asyncio
    async def test_clears_all_counters(self):
        l2 = _make_l2()
        l2.get = AsyncMock(return_value="v")
        cache = _make_cache(l2)

        await cache.get("k")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.l1_hits == 0
        assert stats.l2_hits == 0
        assert stats.misses == 0
        assert stats.l1_evictions == 0
        assert stats.total_requests == 0

    @pytest.mark.asyncio
    async def test_l1_size_not_affected_by_reset(self):
        cache = _make_cache()
        await cache.set("k", "v")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.l1_size == 1


# =========================================================================
# Thread-safe operations
# =========================================================================


class TestThreadSafety:
    @pytest.mark.asyncio
    async def test_concurrent_l1_access(self):
        """Multiple threads reading/writing L1 should not raise."""
        cache = _make_cache(l1_max_size=50)

        errors: list[Exception] = []

        def writer(start: int) -> None:
            try:
                for i in range(start, start + 20):
                    cache._l1_put(f"key{i}", i, 60, "default")
            except Exception as exc:
                errors.append(exc)

        def reader(start: int) -> None:
            try:
                for i in range(start, start + 20):
                    cache._l1_get(f"key{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(20,)),
            threading.Thread(target=reader, args=(0,)),
            threading.Thread(target=reader, args=(10,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == []

    @pytest.mark.asyncio
    async def test_concurrent_l1_clear(self):
        cache = _make_cache(l1_max_size=50)
        for i in range(30):
            cache._l1_put(f"key{i}", i, 60, "default")

        errors: list[Exception] = []

        def do_clear() -> None:
            try:
                cache._l1_clear()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_clear) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == []


# =========================================================================
# CacheStats model
# =========================================================================


class TestCacheStatsModel:
    def test_defaults(self):
        stats = CacheStats()
        assert stats.l1_hits == 0
        assert stats.l2_hits == 0
        assert stats.misses == 0
        assert stats.l1_evictions == 0
        assert stats.total_requests == 0
        assert stats.l1_hit_ratio == 0.0

    def test_custom_values(self):
        stats = CacheStats(l1_hits=10, l2_hits=5, misses=2, total_requests=17)
        assert stats.l1_hits == 10
        assert stats.total_requests == 17


# =========================================================================
# CacheLevel enum
# =========================================================================


class TestCacheLevelEnum:
    def test_values(self):
        assert CacheLevel.L1_MEMORY == "l1_memory"
        assert CacheLevel.L2_REDIS == "l2_redis"
        assert CacheLevel.MISS == "miss"
