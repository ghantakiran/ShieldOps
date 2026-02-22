"""Tests for the Redis cache layer.

Covers:
- RedisCache core operations (get, set, delete, invalidate_pattern, get_or_set)
- Hit/miss counter tracking
- Key namespacing
- JSON serialization (dict, list, Pydantic model)
- Cache decorators (cached, cache_invalidate)
- API routes (stats, invalidate, health)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from shieldops.api.routes import cache as cache_routes
from shieldops.cache.decorators import (
    _build_cache_key,
    cache_invalidate,
    cached,
    set_cache,
)
from shieldops.cache.redis_cache import RedisCache

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_cache() -> Any:
    """Reset module-level cache singleton between tests."""
    cache_routes._cache = None
    set_cache(None)
    yield
    cache_routes._cache = None
    set_cache(None)


def _make_mock_client() -> AsyncMock:
    """Build a mock redis.asyncio client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    # scan_iter returns an async iterator
    client.scan_iter = _make_scan_iter([])
    return client


def _make_scan_iter(keys: list[bytes]) -> Any:
    """Create a callable that returns an async iterator over *keys*."""

    def scan_iter(match: str | None = None) -> Any:
        async def _aiter():
            for k in keys:
                yield k

        return _aiter()

    return scan_iter


# ── RedisCache Unit Tests ────────────────────────────────────────


class TestRedisCacheGetSet:
    @pytest.mark.asyncio
    async def test_set_and_get_round_trip(self) -> None:
        """set() then get() should return the same value."""
        cache = RedisCache(redis_url="redis://localhost:6379/0", default_ttl=60)
        cache._client = _make_mock_client()

        stored: dict[str, bytes] = {}

        async def fake_set(key: str, value: bytes, ex: int | None = None) -> None:
            stored[key] = value

        async def fake_get(key: str) -> bytes | None:
            return stored.get(key)

        cache._client.set = AsyncMock(side_effect=fake_set)
        cache._client.get = AsyncMock(side_effect=fake_get)

        await cache.set("mykey", {"foo": "bar"}, namespace="test")
        result = await cache.get("mykey", namespace="test")

        assert result == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl(self) -> None:
        """set() without explicit TTL should use the default."""
        cache = RedisCache(redis_url="redis://localhost:6379/0", default_ttl=120)
        cache._client = _make_mock_client()

        await cache.set("k", "v", namespace="ns")

        cache._client.set.assert_awaited_once()
        call_kwargs = cache._client.set.call_args
        assert call_kwargs[1]["ex"] == 120 or call_kwargs[0][2] == 120

    @pytest.mark.asyncio
    async def test_set_with_explicit_ttl_overrides_default(self) -> None:
        """Explicit TTL parameter should override the default."""
        cache = RedisCache(redis_url="redis://localhost:6379/0", default_ttl=120)
        cache._client = _make_mock_client()

        await cache.set("k", "v", ttl=42, namespace="ns")

        cache._client.set.assert_awaited_once()
        _, kwargs = cache._client.set.call_args
        assert kwargs["ex"] == 42

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self) -> None:
        """get() should return None when the key does not exist."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.get = AsyncMock(return_value=None)

        result = await cache.get("nonexistent", namespace="ns")

        assert result is None


class TestRedisCacheDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_key(self) -> None:
        """delete() should call Redis DEL with the correct key."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        await cache.delete("mykey", namespace="test")

        cache._client.delete.assert_awaited_once_with("shieldops:test:mykey")


class TestRedisCacheInvalidatePattern:
    @pytest.mark.asyncio
    async def test_invalidate_pattern_deletes_matching_keys(self) -> None:
        """invalidate_pattern should delete all keys matching the glob."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        keys = [b"shieldops:inv:k1", b"shieldops:inv:k2"]
        cache._client.scan_iter = _make_scan_iter(keys)

        deleted = await cache.invalidate_pattern("inv:*")

        assert deleted == 2
        assert cache._client.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_pattern_returns_zero_when_no_match(self) -> None:
        """invalidate_pattern should return 0 when nothing matches."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.scan_iter = _make_scan_iter([])

        deleted = await cache.invalidate_pattern("empty:*")

        assert deleted == 0


class TestRedisCacheGetOrSet:
    @pytest.mark.asyncio
    async def test_get_or_set_returns_cached_on_hit(self) -> None:
        """get_or_set should return the cached value without calling factory."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        import orjson

        cache._client.get = AsyncMock(return_value=orjson.dumps({"cached": True}))

        factory = AsyncMock(return_value={"fresh": True})
        result = await cache.get_or_set("k", factory, namespace="ns")

        assert result == {"cached": True}
        factory.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_or_set_calls_factory_on_miss(self) -> None:
        """get_or_set should call factory and cache its result on miss."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.get = AsyncMock(return_value=None)

        factory = AsyncMock(return_value={"fresh": True})
        result = await cache.get_or_set("k", factory, namespace="ns")

        assert result == {"fresh": True}
        factory.assert_awaited_once()
        cache._client.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_or_set_works_with_sync_factory(self) -> None:
        """get_or_set should support a synchronous factory callable."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.get = AsyncMock(return_value=None)

        def sync_factory() -> dict:
            return {"sync": True}

        result = await cache.get_or_set("k", sync_factory, namespace="ns")

        assert result == {"sync": True}


class TestRedisCacheHitMissTracking:
    @pytest.mark.asyncio
    async def test_hit_miss_counters(self) -> None:
        """Hits and misses should be tracked accurately."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        import orjson

        # First call: miss
        cache._client.get = AsyncMock(return_value=None)
        await cache.get("k1", namespace="ns")

        # Second call: hit
        cache._client.get = AsyncMock(return_value=orjson.dumps("hello"))
        await cache.get("k2", namespace="ns")

        # Third call: miss
        cache._client.get = AsyncMock(return_value=None)
        await cache.get("k3", namespace="ns")

        assert cache._hits == 1
        assert cache._misses == 2


class TestRedisCacheKeyNamespacing:
    def test_key_format(self) -> None:
        """Keys should follow {prefix}:{namespace}:{key} format."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            key_prefix="myapp",
        )
        assert cache._make_key("foo", "bar") == "myapp:bar:foo"
        assert cache._make_key("x", "default") == "myapp:default:x"

    def test_default_prefix(self) -> None:
        """Default key prefix should be 'shieldops'."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._make_key("k", "ns") == "shieldops:ns:k"


class TestRedisCacheJsonSerialization:
    @pytest.mark.asyncio
    async def test_serialize_dict(self) -> None:
        """Dicts should round-trip through JSON serialization."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        store: dict[str, bytes] = {}

        async def fake_set(key: str, value: bytes, ex: int | None = None) -> None:
            store[key] = value

        async def fake_get(key: str) -> bytes | None:
            return store.get(key)

        cache._client.set = AsyncMock(side_effect=fake_set)
        cache._client.get = AsyncMock(side_effect=fake_get)

        data = {"id": "inv-1", "status": "complete", "score": 0.95}
        await cache.set("d", data, namespace="test")
        result = await cache.get("d", namespace="test")
        assert result == data

    @pytest.mark.asyncio
    async def test_serialize_list(self) -> None:
        """Lists should round-trip through JSON serialization."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        store: dict[str, bytes] = {}

        async def fake_set(key: str, value: bytes, ex: int | None = None) -> None:
            store[key] = value

        async def fake_get(key: str) -> bytes | None:
            return store.get(key)

        cache._client.set = AsyncMock(side_effect=fake_set)
        cache._client.get = AsyncMock(side_effect=fake_get)

        data = [1, "two", {"three": 3}]
        await cache.set("l", data, namespace="test")
        result = await cache.get("l", namespace="test")
        assert result == data

    @pytest.mark.asyncio
    async def test_serialize_pydantic_model(self) -> None:
        """Pydantic model dicts should round-trip through cache."""

        class AlertModel(BaseModel):
            alert_id: str
            severity: str
            score: float

        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()

        store: dict[str, bytes] = {}

        async def fake_set(key: str, value: bytes, ex: int | None = None) -> None:
            store[key] = value

        async def fake_get(key: str) -> bytes | None:
            return store.get(key)

        cache._client.set = AsyncMock(side_effect=fake_set)
        cache._client.get = AsyncMock(side_effect=fake_get)

        model = AlertModel(alert_id="a-1", severity="critical", score=0.99)
        await cache.set("m", model.model_dump(), namespace="test")
        result = await cache.get("m", namespace="test")
        assert result == {"alert_id": "a-1", "severity": "critical", "score": 0.99}


class TestRedisCacheStats:
    @pytest.mark.asyncio
    async def test_get_stats_returns_counters(self) -> None:
        """get_stats should return hit/miss counters and key count."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._hits = 10
        cache._misses = 5

        keys = [b"shieldops:ns:k1", b"shieldops:ns:k2"]
        cache._client.scan_iter = _make_scan_iter(keys)

        stats = await cache.get_stats()

        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["total_requests"] == 15
        assert stats["hit_ratio_pct"] == pytest.approx(66.67, abs=0.01)
        assert stats["keys_count"] == 2


# ── Decorator Tests ──────────────────────────────────────────────


class TestCachedDecorator:
    @pytest.mark.asyncio
    async def test_cached_decorator_caches_result(self) -> None:
        """@cached should cache the function result on first call."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        set_cache(mock_cache)

        call_count = 0

        @cached(ttl=60, namespace="items")
        async def fetch_items() -> list[str]:
            nonlocal call_count
            call_count += 1
            return ["a", "b"]

        result = await fetch_items()

        assert result == ["a", "b"]
        assert call_count == 1
        mock_cache.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_returns_cached_on_hit(self) -> None:
        """@cached should return cached data without calling the function."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=["cached"])
        set_cache(mock_cache)

        call_count = 0

        @cached(ttl=60, namespace="items")
        async def fetch_items() -> list[str]:
            nonlocal call_count
            call_count += 1
            return ["fresh"]

        result = await fetch_items()

        assert result == ["cached"]
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_cached_decorator_falls_through_when_no_cache(self) -> None:
        """@cached should call the function when cache is not configured."""
        set_cache(None)

        @cached(ttl=60, namespace="items")
        async def fetch_items() -> list[str]:
            return ["direct"]

        result = await fetch_items()
        assert result == ["direct"]


class TestCacheInvalidateDecorator:
    @pytest.mark.asyncio
    async def test_cache_invalidate_clears_namespace(self) -> None:
        """@cache_invalidate should clear the namespace after execution."""
        mock_cache = AsyncMock()
        mock_cache.invalidate_pattern = AsyncMock(return_value=3)
        set_cache(mock_cache)

        @cache_invalidate(namespace="items")
        async def save_item(data: dict) -> dict:
            return {"saved": True}

        result = await save_item({"name": "test"})

        assert result == {"saved": True}
        mock_cache.invalidate_pattern.assert_awaited_once_with("items:*")

    @pytest.mark.asyncio
    async def test_cache_invalidate_noop_when_no_cache(self) -> None:
        """@cache_invalidate should still work when cache is not configured."""
        set_cache(None)

        @cache_invalidate(namespace="items")
        async def save_item() -> dict:
            return {"saved": True}

        result = await save_item()
        assert result == {"saved": True}


class TestBuildCacheKey:
    def test_deterministic_key(self) -> None:
        """Same function + args should produce the same cache key."""

        async def my_func(a: int, b: str) -> None:
            pass

        key1 = _build_cache_key(my_func, (1,), {"b": "x"})
        key2 = _build_cache_key(my_func, (1,), {"b": "x"})
        assert key1 == key2

    def test_different_args_produce_different_keys(self) -> None:
        """Different arguments should produce different cache keys."""

        async def my_func(a: int) -> None:
            pass

        key1 = _build_cache_key(my_func, (1,), {})
        key2 = _build_cache_key(my_func, (2,), {})
        assert key1 != key2


# ── API Route Tests ──────────────────────────────────────────────


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(cache_routes.router, prefix="/api/v1")
    return app


def _build_client_with_auth(
    app: FastAPI,
    mock_cache: AsyncMock | None = None,
) -> TestClient:
    """Wire the mock cache and override auth for an admin user."""
    if mock_cache is not None:
        cache_routes.set_cache(mock_cache)

    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    admin = UserResponse(
        id="u-admin",
        email="admin@test.com",
        name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return admin

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


class TestCacheAPIRoutes:
    def _build_client(self, mock_cache: AsyncMock) -> TestClient:
        app = _create_test_app()
        return _build_client_with_auth(app, mock_cache)

    def test_health_endpoint_healthy(self) -> None:
        mock_cache = AsyncMock()
        mock_cache.health_check = AsyncMock(return_value={"status": "healthy"})
        client = self._build_client(mock_cache)

        resp = client.get("/api/v1/cache/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_endpoint_unavailable_without_cache(self) -> None:
        app = _create_test_app()
        cache_routes._cache = None
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/cache/health")

        assert resp.status_code == 503

    def test_stats_endpoint(self) -> None:
        mock_cache = AsyncMock()
        mock_cache.get_stats = AsyncMock(
            return_value={
                "hits": 50,
                "misses": 10,
                "total_requests": 60,
                "hit_ratio_pct": 83.33,
                "keys_count": 25,
            }
        )
        client = self._build_client(mock_cache)

        resp = client.get("/api/v1/cache/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["hits"] == 50
        assert data["keys_count"] == 25

    def test_invalidate_endpoint_all(self) -> None:
        mock_cache = AsyncMock()
        mock_cache.flush_all = AsyncMock(return_value=10)
        client = self._build_client(mock_cache)

        resp = client.post("/api/v1/cache/invalidate", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["invalidated"] is True
        assert data["keys_deleted"] == 10

    def test_invalidate_endpoint_by_namespace(self) -> None:
        mock_cache = AsyncMock()
        mock_cache.invalidate_pattern = AsyncMock(return_value=3)
        client = self._build_client(mock_cache)

        resp = client.post(
            "/api/v1/cache/invalidate",
            json={"namespace": "investigations"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["invalidated"] is True
        assert data["keys_deleted"] == 3
        mock_cache.invalidate_pattern.assert_awaited_once_with("investigations:*")


class TestCacheHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self) -> None:
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.ping = AsyncMock(return_value=True)

        result = await cache.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_error(self) -> None:
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._client = _make_mock_client()
        cache._client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))

        result = await cache.health_check()
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]
