"""Tests for shieldops.api.middleware.idempotency module.

Covers InMemoryIdempotencyStore, IdempotencyStore protocol, IdempotencyMiddleware,
composite key building, TTL expiry, and cache replay behavior.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.idempotency import (
    DEFAULT_TTL,
    IDEMPOTENCY_HEADER,
    IDEMPOTENT_METHODS,
    IdempotencyMiddleware,
    IdempotencyStore,
    InMemoryIdempotencyStore,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_idempotent_methods(self) -> None:
        assert {"POST", "PUT", "PATCH"} == IDEMPOTENT_METHODS

    def test_idempotency_header_name(self) -> None:
        assert IDEMPOTENCY_HEADER == "Idempotency-Key"

    def test_default_ttl(self) -> None:
        assert DEFAULT_TTL == 86400


# ---------------------------------------------------------------------------
# IdempotencyStore protocol
# ---------------------------------------------------------------------------


class TestIdempotencyStoreProtocol:
    """Tests for the IdempotencyStore runtime-checkable protocol."""

    def test_in_memory_store_satisfies_protocol(self) -> None:
        store = InMemoryIdempotencyStore()
        assert isinstance(store, IdempotencyStore)

    def test_custom_store_satisfies_protocol(self) -> None:
        class CustomStore:
            async def get(self, key: str) -> dict[str, Any] | None:
                return None

            async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
                pass

            async def delete(self, key: str) -> None:
                pass

        store = CustomStore()
        assert isinstance(store, IdempotencyStore)

    def test_incomplete_store_does_not_satisfy_protocol(self) -> None:
        class BadStore:
            async def get(self, key: str) -> None:
                return None

        store = BadStore()
        assert not isinstance(store, IdempotencyStore)


# ---------------------------------------------------------------------------
# InMemoryIdempotencyStore — basic operations
# ---------------------------------------------------------------------------


class TestInMemoryIdempotencyStoreBasic:
    """Tests for InMemoryIdempotencyStore basic get/set/delete."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self) -> None:
        store = InMemoryIdempotencyStore()
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        store = InMemoryIdempotencyStore()
        data = {"body": {"msg": "ok"}, "status_code": 200}
        await store.set("key1", data, ttl=60)
        result = await store.get("key1")
        assert result == data

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self) -> None:
        store = InMemoryIdempotencyStore()
        await store.set("key1", {"v": 1}, ttl=60)
        await store.set("key1", {"v": 2}, ttl=60)
        result = await store.get("key1")
        assert result == {"v": 2}

    @pytest.mark.asyncio
    async def test_delete_existing_key(self) -> None:
        store = InMemoryIdempotencyStore()
        await store.set("key1", {"v": 1}, ttl=60)
        await store.delete("key1")
        result = await store.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key_is_safe(self) -> None:
        store = InMemoryIdempotencyStore()
        await store.delete("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_keys(self) -> None:
        store = InMemoryIdempotencyStore()
        await store.set("a", {"v": 1}, ttl=60)
        await store.set("b", {"v": 2}, ttl=60)
        await store.set("c", {"v": 3}, ttl=60)
        assert await store.get("a") == {"v": 1}
        assert await store.get("b") == {"v": 2}
        assert await store.get("c") == {"v": 3}


# ---------------------------------------------------------------------------
# InMemoryIdempotencyStore — TTL and cleanup
# ---------------------------------------------------------------------------


class TestInMemoryIdempotencyStoreTTL:
    """Tests for TTL expiry and cleanup behavior."""

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self) -> None:
        store = InMemoryIdempotencyStore(ttl=1)
        await store.set("key1", {"v": 1}, ttl=0)  # Already expired effectively
        # We need to manipulate the internal expiry time
        store._store["key1"] = ({"v": 1}, time.monotonic() - 1)
        result = await store.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_from_set_overrides_default(self) -> None:
        store = InMemoryIdempotencyStore(ttl=3600)
        await store.set("key1", {"v": 1}, ttl=1)
        # Entry should still be valid right now
        result = await store.get("key1")
        assert result == {"v": 1}

    @pytest.mark.asyncio
    async def test_default_ttl_used_when_none(self) -> None:
        store = InMemoryIdempotencyStore(ttl=3600)
        await store.set("key1", {"v": 1})  # ttl=None uses default
        result = await store.get("key1")
        assert result == {"v": 1}

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_entries(self) -> None:
        store = InMemoryIdempotencyStore(ttl=3600)
        # Insert entries with already-expired timestamps
        store._store["expired1"] = ({"v": 1}, time.monotonic() - 100)
        store._store["expired2"] = ({"v": 2}, time.monotonic() - 50)
        store._store["valid"] = ({"v": 3}, time.monotonic() + 3600)

        store._cleanup()
        assert "expired1" not in store._store
        assert "expired2" not in store._store
        assert "valid" in store._store

    @pytest.mark.asyncio
    async def test_size_excludes_expired(self) -> None:
        store = InMemoryIdempotencyStore(ttl=3600)
        store._store["expired"] = ({"v": 1}, time.monotonic() - 100)
        store._store["valid"] = ({"v": 2}, time.monotonic() + 3600)
        assert store.size == 1

    @pytest.mark.asyncio
    async def test_size_empty_store(self) -> None:
        store = InMemoryIdempotencyStore()
        assert store.size == 0

    @pytest.mark.asyncio
    async def test_size_all_valid(self) -> None:
        store = InMemoryIdempotencyStore()
        await store.set("a", {"v": 1}, ttl=3600)
        await store.set("b", {"v": 2}, ttl=3600)
        assert store.size == 2


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — build_key
# ---------------------------------------------------------------------------


class TestBuildKey:
    """Tests for the composite key building logic."""

    def test_build_key_deterministic(self) -> None:
        key1 = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "abc-123")
        key2 = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "abc-123")
        assert key1 == key2

    def test_build_key_different_methods(self) -> None:
        key_post = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "abc-123")
        key_put = IdempotencyMiddleware._build_key("PUT", "/api/v1/actions", "abc-123")
        assert key_post != key_put

    def test_build_key_different_paths(self) -> None:
        key1 = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "abc-123")
        key2 = IdempotencyMiddleware._build_key("POST", "/api/v1/other", "abc-123")
        assert key1 != key2

    def test_build_key_different_idempotency_keys(self) -> None:
        key1 = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "abc-123")
        key2 = IdempotencyMiddleware._build_key("POST", "/api/v1/actions", "def-456")
        assert key1 != key2

    def test_build_key_is_sha256_hex(self) -> None:
        key = IdempotencyMiddleware._build_key("POST", "/path", "idem-key")
        assert len(key) == 64  # SHA-256 hex digest length
        int(key, 16)  # Should be valid hexadecimal

    def test_build_key_matches_manual_computation(self) -> None:
        raw = "POST:/api/v1/test:my-key"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        actual = IdempotencyMiddleware._build_key("POST", "/api/v1/test", "my-key")
        assert actual == expected


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — HTTP method filtering
# ---------------------------------------------------------------------------


def _create_test_app(store: IdempotencyStore | None = None) -> Starlette:
    """Create a minimal Starlette app with the idempotency middleware for testing."""
    call_count = {"value": 0}

    async def endpoint(request: Request) -> JSONResponse:
        call_count["value"] += 1
        return JSONResponse(
            content={"message": "ok", "call_count": call_count["value"]},
            status_code=200,
        )

    app = Starlette(
        routes=[
            Route("/api/test", endpoint, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
        ],
    )
    app.add_middleware(IdempotencyMiddleware, store=store)
    return app


class TestIdempotencyMiddlewarePassthrough:
    """Tests for requests that should bypass idempotency caching."""

    def test_get_request_passes_through(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        assert resp.status_code == 200

    def test_delete_request_passes_through(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.delete("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        assert resp.status_code == 200

    def test_post_without_header_passes_through(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.post("/api/test")
        assert resp.status_code == 200

    def test_put_without_header_passes_through(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.put("/api/test")
        assert resp.status_code == 200

    def test_patch_without_header_passes_through(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.patch("/api/test")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — caching behavior
# ---------------------------------------------------------------------------


class TestIdempotencyMiddlewareCaching:
    """Tests for idempotency caching and replay."""

    def test_post_with_key_caches_response(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp1 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["call_count"] == 1

    def test_duplicate_key_returns_cached_response(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp1 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        resp2 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        # Both should return the same response body
        assert resp1.json() == resp2.json()
        assert resp1.json()["call_count"] == 1

    def test_duplicate_returns_replayed_header(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        resp2 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        assert resp2.headers.get("x-idempotency-replayed") == "true"

    def test_first_request_does_not_have_replayed_header(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-new"})
        assert resp.headers.get("x-idempotency-replayed") is None

    def test_different_keys_get_different_responses(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp1 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-1"})
        resp2 = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "key-2"})
        # Different keys should trigger separate calls
        assert resp1.json()["call_count"] == 1
        assert resp2.json()["call_count"] == 2

    def test_put_with_key_is_cached(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp1 = client.put("/api/test", headers={IDEMPOTENCY_HEADER: "put-key-1"})
        resp2 = client.put("/api/test", headers={IDEMPOTENCY_HEADER: "put-key-1"})
        assert resp1.json() == resp2.json()

    def test_patch_with_key_is_cached(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        resp1 = client.patch("/api/test", headers={IDEMPOTENCY_HEADER: "patch-key-1"})
        resp2 = client.patch("/api/test", headers={IDEMPOTENCY_HEADER: "patch-key-1"})
        assert resp1.json() == resp2.json()

    def test_same_key_different_method_not_cached(self) -> None:
        """POST and PUT with the same idempotency key should NOT share cache."""
        app = _create_test_app()
        client = TestClient(app)
        resp_post = client.post("/api/test", headers={IDEMPOTENCY_HEADER: "shared-key"})
        resp_put = client.put("/api/test", headers={IDEMPOTENCY_HEADER: "shared-key"})
        assert resp_post.json()["call_count"] != resp_put.json()["call_count"]


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — custom store injection
# ---------------------------------------------------------------------------


class TestIdempotencyMiddlewareCustomStore:
    """Tests for using a custom store with the middleware."""

    @pytest.mark.asyncio
    async def test_uses_injected_store(self) -> None:
        custom_store = InMemoryIdempotencyStore(ttl=60)
        app = _create_test_app(store=custom_store)
        client = TestClient(app)
        client.post("/api/test", headers={IDEMPOTENCY_HEADER: "custom-key"})
        # The custom store should contain the cached response
        assert custom_store.size >= 1

    def test_default_store_created_when_none(self) -> None:
        """When no store is passed, middleware creates an InMemoryIdempotencyStore."""
        app = Starlette(routes=[])
        middleware = IdempotencyMiddleware(app)
        assert isinstance(middleware.store, InMemoryIdempotencyStore)


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — cached status code preservation
# ---------------------------------------------------------------------------


class TestIdempotencyMiddlewareStatusCode:
    """Tests that cached responses preserve the original status code."""

    def test_cached_201_status(self) -> None:
        async def created_endpoint(request: Request) -> JSONResponse:
            return JSONResponse(content={"id": "new"}, status_code=201)

        app = Starlette(
            routes=[Route("/api/create", created_endpoint, methods=["POST"])],
        )
        app.add_middleware(IdempotencyMiddleware)
        client = TestClient(app)

        resp1 = client.post("/api/create", headers={IDEMPOTENCY_HEADER: "create-key"})
        assert resp1.status_code == 201

        resp2 = client.post("/api/create", headers={IDEMPOTENCY_HEADER: "create-key"})
        assert resp2.status_code == 201
        assert resp2.json() == {"id": "new"}

    def test_cached_422_status(self) -> None:
        async def validation_endpoint(request: Request) -> JSONResponse:
            return JSONResponse(content={"error": "invalid"}, status_code=422)

        app = Starlette(
            routes=[Route("/api/validate", validation_endpoint, methods=["POST"])],
        )
        app.add_middleware(IdempotencyMiddleware)
        client = TestClient(app)

        resp1 = client.post("/api/validate", headers={IDEMPOTENCY_HEADER: "val-key"})
        assert resp1.status_code == 422

        resp2 = client.post("/api/validate", headers={IDEMPOTENCY_HEADER: "val-key"})
        assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# IdempotencyMiddleware — TTL configuration
# ---------------------------------------------------------------------------


class TestIdempotencyMiddlewareTTL:
    """Tests for TTL configuration."""

    def test_custom_ttl_passed_to_default_store(self) -> None:
        app = Starlette(routes=[])
        middleware = IdempotencyMiddleware(app, ttl=120)
        assert middleware.ttl == 120

    def test_default_ttl_value(self) -> None:
        app = Starlette(routes=[])
        middleware = IdempotencyMiddleware(app)
        assert middleware.ttl == DEFAULT_TTL
