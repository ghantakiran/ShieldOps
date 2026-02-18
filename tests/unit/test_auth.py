"""Tests for JWT authentication, password hashing, and RBAC enforcement."""

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app
from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserRole
from shieldops.api.auth.service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "s3cur3P@ss!"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed) is True

    def test_wrong_password_rejected(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_unique(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salts

    def test_malformed_hash_rejected(self):
        assert verify_password("anything", "nothash") is False
        assert verify_password("anything", "") is False


class TestJWTTokens:
    def test_create_and_decode(self):
        token = create_access_token(subject="user-1", role="admin")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"
        assert payload["role"] == "admin"

    def test_tampered_token_rejected(self):
        token = create_access_token(subject="user-1", role="admin")
        tampered = token[:-5] + "XXXXX"
        assert decode_token(tampered) is None

    def test_expired_token_rejected(self):
        from datetime import timedelta

        token = create_access_token(
            subject="user-1", role="admin", expires_delta=timedelta(seconds=-1)
        )
        assert decode_token(token) is None

    def test_malformed_token_rejected(self):
        assert decode_token("not.a.token") is None
        assert decode_token("") is None
        assert decode_token("only.two") is None


class TestAuthEndpoints:
    @pytest.fixture
    async def unauthenticated_client(self):
        # Remove auth override for these tests
        original = app.dependency_overrides.copy()
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides = original

    @pytest.fixture
    async def authenticated_client(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, unauthenticated_client):
        response = await unauthenticated_client.get("/api/v1/investigations")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, unauthenticated_client):
        response = await unauthenticated_client.get(
            "/api/v1/investigations",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_passes_with_override(self, authenticated_client):
        """Tests pass when auth is overridden (as in conftest.py)."""
        response = await authenticated_client.get("/api/v1/investigations")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_me_endpoint(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_login_without_db_returns_503(self, unauthenticated_client):
        response = await unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "password"},
        )
        assert response.status_code == 503


class TestRBAC:
    @pytest.fixture
    async def viewer_client(self):
        from shieldops.api.auth.models import UserResponse

        def _mock_viewer():
            return UserResponse(
                id="test-viewer",
                email="viewer@shieldops.test",
                name="Test Viewer",
                role=UserRole.VIEWER,
                is_active=True,
            )

        original = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = _mock_viewer
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides = original

    @pytest.mark.asyncio
    async def test_viewer_can_read(self, viewer_client):
        response = await viewer_client.get("/api/v1/investigations")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_post(self, viewer_client):
        response = await viewer_client.post(
            "/api/v1/investigations",
            json={
                "alert_id": "test",
                "alert_name": "test",
            },
        )
        assert response.status_code == 403
