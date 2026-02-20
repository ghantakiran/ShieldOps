"""Tests for sliding-window rate limiter middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.sliding_window import (
    _EXEMPT_PATHS,
    METHOD_TIERS,
    TIER_LIMITS,
    SlidingWindowRateLimiter,
)

# ── Helpers ──────────────────────────────────────────────────────────


async def _ok_endpoint(request: Request) -> Response:
    """Minimal endpoint that returns 200 with a JSON body."""
    return JSONResponse({"status": "ok"})


async def _auth_endpoint(request: Request) -> Response:
    """Minimal auth endpoint."""
    return JSONResponse({"status": "authenticated"})


def _build_app(
    redis: AsyncMock | None = None,
) -> Starlette:
    """Build a minimal Starlette app with the sliding window middleware."""
    app = Starlette(
        routes=[
            Route("/health", _ok_endpoint),
            Route("/ready", _ok_endpoint),
            Route("/metrics", _ok_endpoint),
            Route("/api/v1/agents", _ok_endpoint, methods=["GET"]),
            Route(
                "/api/v1/agents",
                _ok_endpoint,
                methods=["POST"],
            ),
            Route(
                "/api/v1/agents/{agent_id}",
                _ok_endpoint,
                methods=["DELETE"],
            ),
            Route(
                "/api/v1/auth/login",
                _auth_endpoint,
                methods=["POST"],
            ),
        ],
    )
    app.add_middleware(SlidingWindowRateLimiter, redis=redis)
    return app


def _make_redis_mock(
    current_count: int = 1,
) -> AsyncMock:
    """Create a mock Redis client with pipeline support.

    The pipeline mock simulates:
      results[0] = zremrangebyscore (removed count)
      results[1] = zadd (added count)
      results[2] = zcard (current_count)
      results[3] = expire (True)
    """
    pipeline = AsyncMock()
    pipeline.zremrangebyscore = MagicMock(return_value=pipeline)
    pipeline.zadd = MagicMock(return_value=pipeline)
    pipeline.zcard = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[0, 1, current_count, True])

    redis = AsyncMock()
    redis.pipeline = MagicMock(return_value=pipeline)
    redis._pipeline = pipeline  # expose for test manipulation
    return redis


# ── Test: Exempt paths ───────────────────────────────────────────────


class TestExemptPaths:
    def test_exempt_path_bypasses_limiter(self) -> None:
        """Requests to /health, /ready, /metrics skip rate limiting."""
        redis = _make_redis_mock()
        app = _build_app(redis=redis)
        client = TestClient(app)

        for path in _EXEMPT_PATHS:
            resp = client.get(path)
            assert resp.status_code == 200
            assert "x-ratelimit-limit" not in resp.headers

        # Redis pipeline should never have been called
        redis.pipeline.assert_not_called()


# ── Test: Tier resolution ────────────────────────────────────────────


class TestTierResolution:
    def test_get_request_uses_read_tier(self) -> None:
        """GET /api/v1/agents should resolve to the 'read' tier."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        limit = int(resp.headers["x-ratelimit-limit"])
        expected_limit = TIER_LIMITS["read"][0]
        assert limit == expected_limit

    def test_post_request_uses_write_tier(self) -> None:
        """POST /api/v1/agents should resolve to the 'write' tier."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200
        limit = int(resp.headers["x-ratelimit-limit"])
        expected_limit = TIER_LIMITS["write"][0]
        assert limit == expected_limit

    def test_delete_request_uses_admin_tier(self) -> None:
        """DELETE should resolve to the 'admin' tier."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.delete("/api/v1/agents/agent-1")
        assert resp.status_code == 200
        limit = int(resp.headers["x-ratelimit-limit"])
        expected_limit = TIER_LIMITS["admin"][0]
        assert limit == expected_limit

    def test_auth_path_uses_auth_tier(self) -> None:
        """POST to /auth/login should override to 'auth' tier."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.post("/api/v1/auth/login")
        assert resp.status_code == 200
        limit = int(resp.headers["x-ratelimit-limit"])
        expected_limit = TIER_LIMITS["auth"][0]
        assert limit == expected_limit

    def test_method_tier_mapping_completeness(self) -> None:
        """All standard HTTP methods should be mapped to a tier."""
        expected_methods = {
            "GET",
            "HEAD",
            "OPTIONS",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
        assert expected_methods == set(METHOD_TIERS.keys())


# ── Test: Rate limit headers ─────────────────────────────────────────


class TestRateLimitHeaders:
    def test_rate_limit_headers_present(self) -> None:
        """Successful responses include X-RateLimit-* headers."""
        redis = _make_redis_mock(current_count=5)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-reset" in resp.headers

    def test_remaining_calculation(self) -> None:
        """Remaining should equal limit - current_count."""
        count = 10
        redis = _make_redis_mock(current_count=count)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        limit = int(resp.headers["x-ratelimit-limit"])
        remaining = int(resp.headers["x-ratelimit-remaining"])
        assert remaining == limit - count


# ── Test: Rate limit exceeded ─────────────────────────────────────────


class TestRateLimitExceeded:
    def test_rate_limit_exceeded_returns_429(self) -> None:
        """When count exceeds limit, a 429 response is returned."""
        # Set count higher than any tier limit
        redis = _make_redis_mock(current_count=999)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"] == "Rate limit exceeded"
        assert "retry_after" in body

    def test_retry_after_header_on_429(self) -> None:
        """429 responses include Retry-After and X-RateLimit-* headers."""
        redis = _make_redis_mock(current_count=999)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers
        assert "x-ratelimit-limit" in resp.headers
        assert resp.headers["x-ratelimit-remaining"] == "0"

        retry_after = int(resp.headers["retry-after"])
        assert retry_after > 0

    def test_429_body_has_correct_retry_after(self) -> None:
        """The retry_after in the body should match the header."""
        redis = _make_redis_mock(current_count=999)
        app = _build_app(redis=redis)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 429
        body_retry = resp.json()["retry_after"]
        header_retry = int(resp.headers["retry-after"])
        assert body_retry == header_retry


# ── Test: No Redis (pass-through) ─────────────────────────────────────


class TestNoRedisPassthrough:
    def test_no_redis_passes_through(self) -> None:
        """When redis=None, all requests pass through without headers."""
        app = _build_app(redis=None)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" not in resp.headers


# ── Test: Sliding window mechanics ────────────────────────────────────


class TestSlidingWindowMechanics:
    def test_sliding_window_removes_old_entries(self) -> None:
        """Pipeline should call zremrangebyscore to purge old entries."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        client.get("/api/v1/agents")

        pipeline = redis._pipeline
        # Verify zremrangebyscore was called to clean old entries
        pipeline.zremrangebyscore.assert_called_once()
        args = pipeline.zremrangebyscore.call_args
        assert args[0][0].startswith("ratelimit:")
        assert args[0][1] == "-inf"
        # The third arg is (now - window); it should be a float
        assert isinstance(args[0][2], float)

    def test_pipeline_adds_current_timestamp(self) -> None:
        """Pipeline should zadd the current timestamp."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        client.get("/api/v1/agents")

        pipeline = redis._pipeline
        pipeline.zadd.assert_called_once()
        args = pipeline.zadd.call_args
        key = args[0][0]
        score_map = args[0][1]
        assert key.startswith("ratelimit:")
        # Score map should have one entry: {"<timestamp>": <float>}
        assert len(score_map) == 1
        for ts_str, ts_float in score_map.items():
            assert isinstance(ts_float, float)
            assert float(ts_str) == ts_float

    def test_pipeline_sets_expiry(self) -> None:
        """Pipeline should set expiry on the key to window + 1."""
        redis = _make_redis_mock(current_count=1)
        app = _build_app(redis=redis)
        client = TestClient(app)

        client.get("/api/v1/agents")

        pipeline = redis._pipeline
        pipeline.expire.assert_called_once()
        args = pipeline.expire.call_args
        # expire(key, window + 1) => second arg = 61 for read tier
        _, window = TIER_LIMITS["read"]
        assert args[0][1] == window + 1


# ── Test: Identity resolution ──────────────────────────────────────────


class TestIdentityResolution:
    def test_tenant_org_id_used_as_identity(self) -> None:
        """When request.state.organization_id is set, use it as key."""
        redis = _make_redis_mock(current_count=1)
        pipeline = redis._pipeline

        org_id = "org-acme-123"

        # Track keys passed to zremrangebyscore
        captured_keys: list[str] = []
        original_zrem = pipeline.zremrangebyscore

        def _capture_zrem(key: str, *a: object) -> object:
            captured_keys.append(key)
            return original_zrem(key, *a)

        pipeline.zremrangebyscore = MagicMock(side_effect=_capture_zrem)

        async def _set_org_state(
            request: Request,
        ) -> Response:
            request.state.organization_id = org_id
            return JSONResponse({"status": "ok"})

        app = Starlette(
            routes=[
                Route("/api/v1/agents", _set_org_state),
            ],
        )
        # We need a middleware that sets state BEFORE the rate limiter.
        # Since Starlette processes add_middleware in LIFO, we add
        # the rate limiter first, then a state-setter middleware.

        from starlette.middleware.base import (
            BaseHTTPMiddleware,
            RequestResponseEndpoint,
        )

        class OrgSetter(BaseHTTPMiddleware):
            async def dispatch(
                self,
                request: Request,
                call_next: RequestResponseEndpoint,
            ) -> Response:
                request.state.organization_id = org_id
                return await call_next(request)

        app.add_middleware(SlidingWindowRateLimiter, redis=redis)
        app.add_middleware(OrgSetter)

        client = TestClient(app)
        client.get("/api/v1/agents")

        assert len(captured_keys) == 1
        assert org_id in captured_keys[0]

    def test_fallback_to_ip_when_no_auth(self) -> None:
        """Without org_id or user_id, IP address is used as identity."""
        redis = _make_redis_mock(current_count=1)
        pipeline = redis._pipeline

        captured_keys: list[str] = []
        original_zrem = pipeline.zremrangebyscore

        def _capture_zrem(key: str, *a: object) -> object:
            captured_keys.append(key)
            return original_zrem(key, *a)

        pipeline.zremrangebyscore = MagicMock(side_effect=_capture_zrem)

        app = _build_app(redis=redis)
        client = TestClient(app)
        client.get("/api/v1/agents")

        assert len(captured_keys) == 1
        key = captured_keys[0]
        # Key should contain an IP-like identity (testclient uses
        # 'testclient' or a loopback address)
        assert key.startswith("ratelimit:read:")
        # The identity portion should not be empty
        identity_part = key.split(":", 2)[2]
        assert len(identity_part) > 0
