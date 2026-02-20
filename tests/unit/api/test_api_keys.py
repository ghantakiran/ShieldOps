"""Tests for API key management.

Tests cover:
- Key generation (format, uniqueness, hash verification)
- POST /api-keys (create, returns full key once, scope validation)
- GET /api-keys (list, never returns full key or hash)
- DELETE /api-keys/{key_id} (revoke, not-found)
- Expired key rejection
- Invalid key format
- Auth middleware API key fallback
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.api_keys import (
    VALID_SCOPES,
    generate_api_key,
    hash_api_key,
    validate_key_format,
    validate_scopes,
)
from shieldops.api.routes import api_keys

# ── Helpers ──────────────────────────────────────────────────


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_keys.router, prefix="/api/v1")
    return app


def _make_key_record(
    key_id: str = "key-abc123",
    user_id: str = "usr-admin1",
    name: str = "CI Key",
    scopes: list[str] | None = None,
    is_active: bool = True,
    expires_at: str | None = None,
    key_hash: str = "deadbeef",
    key_prefix: str = "sk-abcde",
) -> dict[str, Any]:
    return {
        "id": key_id,
        "user_id": user_id,
        "organization_id": None,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "name": name,
        "scopes": scopes or ["read"],
        "expires_at": expires_at,
        "last_used_at": None,
        "is_active": is_active,
        "created_at": "2026-02-19T12:00:00+00:00",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo() -> Any:
    original = api_keys._repository
    api_keys._repository = None
    yield
    api_keys._repository = original


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_api_key = AsyncMock(return_value=_make_key_record())
    repo.list_api_keys_for_user = AsyncMock(
        return_value=[
            _make_key_record(),
            _make_key_record(key_id="key-def456", name="Deploy Key"),
        ]
    )
    repo.revoke_api_key = AsyncMock(return_value=True)
    repo.get_api_key_by_hash = AsyncMock(return_value=None)
    repo.update_api_key_last_used = AsyncMock()
    return repo


def _build_client(
    app: FastAPI,
    mock_repo: AsyncMock,
    user_id: str = "usr-admin1",
    role: str = "admin",
) -> TestClient:
    """Wire dependency overrides for an authenticated user."""
    api_keys.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import (
        get_current_user,
    )
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id=user_id,
        email="admin@test.com",
        name="Admin",
        role=UserRole(role),
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ================================================================
# Unit tests — key generation utilities
# ================================================================


class TestKeyGeneration:
    def test_generated_key_starts_with_prefix(self) -> None:
        full_key, prefix, key_hash = generate_api_key()
        assert full_key.startswith("sk-")
        assert prefix == full_key[:8]

    def test_generated_key_hash_is_sha256(self) -> None:
        full_key, _prefix, key_hash = generate_api_key()
        assert key_hash == hash_api_key(full_key)
        assert len(key_hash) == 64  # SHA-256 hex digest

    def test_keys_are_unique(self) -> None:
        keys = {generate_api_key()[0] for _ in range(50)}
        assert len(keys) == 50

    def test_hash_deterministic(self) -> None:
        full_key, _, expected_hash = generate_api_key()
        assert hash_api_key(full_key) == expected_hash
        assert hash_api_key(full_key) == expected_hash

    def test_validate_key_format_valid(self) -> None:
        full_key, _, _ = generate_api_key()
        assert validate_key_format(full_key) is True

    def test_validate_key_format_invalid_prefix(self) -> None:
        assert validate_key_format("pk-abc12345678") is False

    def test_validate_key_format_too_short(self) -> None:
        assert validate_key_format("sk-short") is False

    def test_validate_key_format_empty(self) -> None:
        assert validate_key_format("") is False


class TestScopeValidation:
    def test_valid_scopes(self) -> None:
        result = validate_scopes(["read", "write"])
        assert result == ["read", "write"]

    def test_all_valid_scopes(self) -> None:
        result = validate_scopes(["read", "write", "admin"])
        assert set(result) == VALID_SCOPES

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid scopes"):
            validate_scopes(["read", "delete"])

    def test_empty_scopes_valid(self) -> None:
        result = validate_scopes([])
        assert result == []


# ================================================================
# POST /api-keys — Create
# ================================================================


class TestCreateAPIKey:
    def test_create_api_key_returns_full_key(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.post(
            "/api/v1/api-keys",
            json={"name": "CI Key", "scopes": ["read"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("sk-")
        assert data["name"] == "CI Key"
        assert data["scopes"] == ["read"]
        assert data["id"] == "key-abc123"
        mock_repo.create_api_key.assert_called_once()

    def test_create_api_key_invalid_scope(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.post(
            "/api/v1/api-keys",
            json={
                "name": "Bad Key",
                "scopes": ["read", "destroy"],
            },
        )
        assert resp.status_code == 400
        assert "Invalid scopes" in resp.json()["detail"]

    def test_create_api_key_empty_name_rejected(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.post(
            "/api/v1/api-keys",
            json={"name": "", "scopes": []},
        )
        assert resp.status_code == 422

    def test_create_api_key_expired_date_rejected(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        resp = client.post(
            "/api/v1/api-keys",
            json={
                "name": "Expired Key",
                "scopes": [],
                "expires_at": past,
            },
        )
        assert resp.status_code == 400
        assert "future" in resp.json()["detail"]

    def test_create_api_key_with_future_expiry(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        resp = client.post(
            "/api/v1/api-keys",
            json={
                "name": "Temp Key",
                "scopes": ["read"],
                "expires_at": future,
            },
        )
        assert resp.status_code == 201


# ================================================================
# GET /api-keys — List
# ================================================================


class TestListAPIKeys:
    def test_list_api_keys(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/api-keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_list_api_keys_never_returns_full_key(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/api-keys")
        data = resp.json()
        for item in data["items"]:
            assert "key" not in item
            assert "key_hash" not in item
            assert "key_prefix" in item

    def test_list_api_keys_pagination(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/api-keys?limit=10&offset=5")
        assert resp.status_code == 200
        mock_repo.list_api_keys_for_user.assert_called_once_with(
            user_id="usr-admin1", limit=10, offset=5
        )

    def test_list_only_own_keys(self, mock_repo: AsyncMock) -> None:
        """Ensures the user_id is passed to filter keys."""
        app = _create_test_app()
        client = _build_client(app, mock_repo, user_id="usr-other")

        client.get("/api/v1/api-keys")
        mock_repo.list_api_keys_for_user.assert_called_once_with(
            user_id="usr-other", limit=50, offset=0
        )


# ================================================================
# DELETE /api-keys/{key_id} — Revoke
# ================================================================


class TestRevokeAPIKey:
    def test_revoke_api_key(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.delete("/api/v1/api-keys/key-abc123")
        assert resp.status_code == 204
        mock_repo.revoke_api_key.assert_called_once_with(key_id="key-abc123", user_id="usr-admin1")

    def test_revoke_api_key_not_found(self, mock_repo: AsyncMock) -> None:
        mock_repo.revoke_api_key = AsyncMock(return_value=False)
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.delete("/api/v1/api-keys/key-nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_revoke_other_users_key_returns_404(self, mock_repo: AsyncMock) -> None:
        """Repository checks user ownership — returns False for mismatch."""
        mock_repo.revoke_api_key = AsyncMock(return_value=False)
        app = _create_test_app()
        client = _build_client(app, mock_repo, user_id="usr-attacker")

        resp = client.delete("/api/v1/api-keys/key-abc123")
        assert resp.status_code == 404


# ================================================================
# Auth middleware — API key authentication
# ================================================================


class TestAPIKeyAuth:
    def test_api_key_auth_validates_format(self) -> None:
        """validate_key_format rejects non-sk- tokens."""
        assert validate_key_format("jwt.token.here") is False
        assert validate_key_format("sk-valid1234567") is True

    def test_hash_api_key_consistency(self) -> None:
        """Same key always produces the same hash."""
        key = "sk-test123456789abcdef"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_different_keys_different_hashes(self) -> None:
        k1, _, h1 = generate_api_key()
        k2, _, h2 = generate_api_key()
        assert k1 != k2
        assert h1 != h2


# ================================================================
# Database unavailable
# ================================================================


class TestDatabaseUnavailable:
    def test_create_api_key_no_db(self) -> None:
        app = _create_test_app()
        # No repository set — should return 503
        from shieldops.api.auth.dependencies import (
            get_current_user,
        )
        from shieldops.api.auth.models import (
            UserResponse,
            UserRole,
        )

        user = UserResponse(
            id="usr-1",
            email="u@t.com",
            name="U",
            role=UserRole.ADMIN,
            is_active=True,
        )

        async def _mock() -> UserResponse:
            return user

        app.dependency_overrides[get_current_user] = _mock
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/v1/api-keys",
            json={"name": "Key", "scopes": []},
        )
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()
