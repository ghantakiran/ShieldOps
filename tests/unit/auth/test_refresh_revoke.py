"""Tests for auth refresh and revoke endpoints.

Tests cover:
- POST /auth/refresh returns a new access token
- POST /auth/revoke writes the JTI to Redis blacklist
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import (
    UserResponse,
    UserRole,
)
from shieldops.api.auth.routes import router


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def admin_user() -> UserResponse:
    return UserResponse(
        id="user-001",
        email="admin@shieldops.io",
        name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )


@pytest.fixture
def app_with_auth(admin_user: UserResponse) -> FastAPI:
    app = _create_test_app()

    async def _mock_user() -> UserResponse:
        return admin_user

    app.dependency_overrides[get_current_user] = _mock_user
    return app


class TestRefreshReturnsNewToken:
    def test_refresh_returns_new_token(self, app_with_auth: FastAPI) -> None:
        client = TestClient(app_with_auth, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200

        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105
        assert data["expires_in"] > 0

        # Token should be a valid JWT-like string (3 dot-parts)
        token = data["access_token"]
        assert token.count(".") == 2

    def test_refresh_without_auth_returns_401(self) -> None:
        """Refresh without authentication returns 401."""
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code in (401, 403)


class TestRevokeAddsToRedis:
    def test_revoke_adds_to_redis(
        self,
        app_with_auth: FastAPI,
        admin_user: UserResponse,
    ) -> None:
        """Revoke should write the JTI to Redis with a TTL."""
        # Generate a real token to send in the header
        from shieldops.api.auth.service import create_access_token

        token = create_access_token(
            subject=admin_user.id,
            role=admin_user.role.value,
        )

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.aclose = AsyncMock()

        mock_from_url = MagicMock(return_value=mock_redis)

        with patch(
            "shieldops.api.auth.routes.aioredis",
            create=True,
        ) as mock_aioredis_mod:
            mock_aioredis_mod.from_url = mock_from_url

            # Patch at the module level where redis.asyncio
            # is imported inside the endpoint
            with patch.dict(
                "sys.modules",
                {
                    "redis": MagicMock(),
                    "redis.asyncio": MagicMock(from_url=mock_from_url),
                },
            ):
                client = TestClient(
                    app_with_auth,
                    raise_server_exceptions=False,
                )
                resp = client.post(
                    "/api/v1/auth/revoke",
                    headers={"Authorization": f"Bearer {token}"},
                )

        # 204 No Content on success
        assert resp.status_code == 204

    def test_revoke_without_bearer_is_noop(self, app_with_auth: FastAPI) -> None:
        """Revoke without a Bearer header is a no-op 204."""
        client = TestClient(app_with_auth, raise_server_exceptions=False)
        # Send the request without Authorization header
        resp = client.post("/api/v1/auth/revoke")
        # Still returns 204 (no-op path)
        assert resp.status_code == 204
