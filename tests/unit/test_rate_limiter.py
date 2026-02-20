"""Tests for HTTP rate limiting middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.auth.service import create_access_token


def _make_app():
    """Build a fresh app instance for test isolation."""
    from shieldops.api.app import create_app

    return create_app()


def _auth_header(role: str = "admin", user_id: str = "user-1") -> dict[str, str]:
    """Create a valid Bearer token header."""
    token = create_access_token(subject=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_redis():
    """Mock Redis client that tracks INCR counts per key."""
    store: dict[str, int] = {}
    client = AsyncMock()

    async def _incr(key: str) -> int:
        store[key] = store.get(key, 0) + 1
        return store[key]

    async def _expire(key: str, ttl: int) -> None:
        pass

    client.incr = AsyncMock(side_effect=_incr)
    client.expire = AsyncMock(side_effect=_expire)
    client._store = store
    return client


@pytest.fixture
async def client(mock_redis):
    """AsyncClient with _ensure_client patched to return mock Redis."""
    app = _make_app()

    async def _fake_ensure(self):
        return mock_redis

    with (
        patch(
            "shieldops.api.middleware.rate_limiter.RateLimitMiddleware._ensure_client",
            _fake_ensure,
        ),
        patch("shieldops.api.middleware.rate_limiter.settings") as mock_settings,
    ):
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_window_seconds = 60
        mock_settings.rate_limit_admin = 300
        mock_settings.rate_limit_operator = 120
        mock_settings.rate_limit_viewer = 60
        mock_settings.rate_limit_default = 60
        mock_settings.rate_limit_auth_login = 10
        mock_settings.rate_limit_auth_register = 5
        mock_settings.api_prefix = "/api/v1"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


class TestRateLimitHeaders:
    @pytest.mark.asyncio
    async def test_headers_present_on_success(self, client):
        response = await client.get("/api/v1/agents", headers=_auth_header())
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers

    @pytest.mark.asyncio
    async def test_remaining_decrements(self, client):
        headers = _auth_header()
        r1 = await client.get("/api/v1/agents", headers=headers)
        r2 = await client.get("/api/v1/agents", headers=headers)
        rem1 = int(r1.headers["x-ratelimit-remaining"])
        rem2 = int(r2.headers["x-ratelimit-remaining"])
        assert rem2 < rem1


class TestRateLimitEnforcement:
    @pytest.mark.asyncio
    async def test_429_when_limit_exceeded(self, client, mock_redis):
        headers = _auth_header(role="viewer", user_id="flood-user")

        call_count = 0
        original_incr = mock_redis.incr.side_effect

        async def _incr_over_limit(key: str) -> int:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_redis._store[key] = 61
                return 61
            return await original_incr(key)

        mock_redis.incr = AsyncMock(side_effect=_incr_over_limit)

        r1 = await client.get("/api/v1/agents", headers=headers)
        assert r1.status_code != 429

        r2 = await client.get("/api/v1/agents", headers=headers)
        assert r2.status_code == 429

    @pytest.mark.asyncio
    async def test_429_response_body(self, client, mock_redis):
        headers = _auth_header(role="viewer", user_id="body-test-user")
        mock_redis.incr = AsyncMock(return_value=999)

        response = await client.get("/api/v1/agents", headers=headers)
        assert response.status_code == 429
        body = response.json()
        assert body["detail"] == "Rate limit exceeded"
        assert "retry_after" in body
        assert "request_id" in body

    @pytest.mark.asyncio
    async def test_429_has_retry_after_header(self, client, mock_redis):
        headers = _auth_header(role="viewer", user_id="retry-user")
        mock_redis.incr = AsyncMock(return_value=999)

        response = await client.get("/api/v1/agents", headers=headers)
        assert response.status_code == 429
        assert "retry-after" in response.headers


class TestRoleTieredLimits:
    @pytest.mark.asyncio
    async def test_admin_has_higher_limit_than_viewer(self, client):
        admin_resp = await client.get(
            "/api/v1/agents", headers=_auth_header(role="admin", user_id="admin-1")
        )
        viewer_resp = await client.get(
            "/api/v1/agents", headers=_auth_header(role="viewer", user_id="viewer-1")
        )
        admin_limit = int(admin_resp.headers["x-ratelimit-limit"])
        viewer_limit = int(viewer_resp.headers["x-ratelimit-limit"])
        assert admin_limit > viewer_limit

    @pytest.mark.asyncio
    async def test_operator_limit_between_admin_and_viewer(self, client):
        admin_resp = await client.get(
            "/api/v1/agents", headers=_auth_header(role="admin", user_id="a1")
        )
        op_resp = await client.get(
            "/api/v1/agents", headers=_auth_header(role="operator", user_id="o1")
        )
        viewer_resp = await client.get(
            "/api/v1/agents", headers=_auth_header(role="viewer", user_id="v1")
        )
        admin_limit = int(admin_resp.headers["x-ratelimit-limit"])
        op_limit = int(op_resp.headers["x-ratelimit-limit"])
        viewer_limit = int(viewer_resp.headers["x-ratelimit-limit"])
        assert admin_limit > op_limit > viewer_limit


class TestExemptPaths:
    @pytest.mark.asyncio
    async def test_health_no_rate_limit_headers(self, client):
        response = await client.get("/health")
        assert "x-ratelimit-limit" not in response.headers

    @pytest.mark.asyncio
    async def test_docs_no_rate_limit_headers(self, client):
        response = await client.get("/api/v1/docs")
        assert "x-ratelimit-limit" not in response.headers

    @pytest.mark.asyncio
    async def test_ready_no_rate_limit_headers(self, client):
        response = await client.get("/ready")
        assert "x-ratelimit-limit" not in response.headers


class TestAuthEndpointProtection:
    @pytest.mark.asyncio
    async def test_login_uses_stricter_limit(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "test", "password": "test"},
        )
        if "x-ratelimit-limit" in response.headers:
            limit = int(response.headers["x-ratelimit-limit"])
            assert limit == 10

    @pytest.mark.asyncio
    async def test_login_rate_limit_is_ip_based(self, client, mock_redis):
        """Two different IPs should have independent counters."""
        calls: list[str] = []

        async def _tracking_incr(key: str) -> int:
            calls.append(key)
            mock_redis._store[key] = mock_redis._store.get(key, 0) + 1
            return mock_redis._store[key]

        mock_redis.incr = AsyncMock(side_effect=_tracking_incr)

        await client.post(
            "/api/v1/auth/login",
            json={"username": "a", "password": "b"},
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        await client.post(
            "/api/v1/auth/login",
            json={"username": "a", "password": "b"},
            headers={"X-Forwarded-For": "5.6.7.8"},
        )

        assert len(calls) == 2
        assert calls[0] != calls[1]


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_redis_failure_allows_request(self):
        """When Redis is unavailable, requests pass through without headers."""
        app = _make_app()

        failing_client = AsyncMock()
        failing_client.incr = AsyncMock(side_effect=ConnectionError("Redis down"))

        async def _failing_ensure(self):
            return failing_client

        with patch(
            "shieldops.api.middleware.rate_limiter.RateLimitMiddleware._ensure_client",
            _failing_ensure,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/v1/agents", headers=_auth_header())
                assert response.status_code != 429
                assert "x-ratelimit-limit" not in response.headers


class TestRateLimitDisabled:
    @pytest.mark.asyncio
    async def test_no_headers_when_disabled(self):
        """rate_limit_enabled=False skips all rate limiting."""
        with patch("shieldops.api.middleware.rate_limiter.settings") as mock_settings:
            mock_settings.rate_limit_enabled = False
            mock_settings.api_prefix = "/api/v1"
            mock_settings.redis_url = "redis://localhost:6379/0"

            app = _make_app()

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/v1/agents", headers=_auth_header())
                assert "x-ratelimit-limit" not in response.headers


class TestIPExtraction:
    @pytest.mark.asyncio
    async def test_x_forwarded_for_respected(self, client, mock_redis):
        """X-Forwarded-For should be used for IP extraction."""
        calls: list[str] = []

        async def _tracking_incr(key: str) -> int:
            calls.append(key)
            mock_redis._store[key] = mock_redis._store.get(key, 0) + 1
            return mock_redis._store[key]

        mock_redis.incr = AsyncMock(side_effect=_tracking_incr)

        await client.get(
            "/api/v1/agents",
            headers={"X-Forwarded-For": "203.0.113.50"},
        )

        assert any("ip:203.0.113.50" in key for key in calls)

    @pytest.mark.asyncio
    async def test_different_ips_independent_counters(self, client, mock_redis):
        """Different IPs should have separate rate limit counters."""
        calls: list[str] = []

        async def _tracking_incr(key: str) -> int:
            calls.append(key)
            mock_redis._store[key] = mock_redis._store.get(key, 0) + 1
            return mock_redis._store[key]

        mock_redis.incr = AsyncMock(side_effect=_tracking_incr)

        await client.get(
            "/api/v1/agents",
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        await client.get(
            "/api/v1/agents",
            headers={"X-Forwarded-For": "10.0.0.2"},
        )

        assert len(calls) == 2
        assert calls[0] != calls[1]
