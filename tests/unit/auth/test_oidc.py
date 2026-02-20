"""Tests for OIDC client and authentication routes.

Covers:
- OIDCClient: discovery caching, authorization URL, code exchange, userinfo
- OIDC routes: login redirect, callback user provisioning, 501 when disabled
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.auth.oidc import OIDCClient
from shieldops.auth.routes import _pending_states, router, set_oidc_client

# ============================================================================
# Fixtures
# ============================================================================

DISCOVERY_DOC: dict[str, str] = {
    "authorization_endpoint": "https://idp.example.com/authorize",
    "token_endpoint": "https://idp.example.com/token",
    "userinfo_endpoint": "https://idp.example.com/userinfo",
}


@pytest.fixture
def oidc_client() -> OIDCClient:
    return OIDCClient(
        issuer_url="https://idp.example.com",
        client_id="test-client-id",
        client_secret="test-client-secret",  # noqa: S106
        redirect_uri="http://localhost:8000/api/v1/auth/oidc/callback",
        scopes="openid email profile",
    )


@pytest.fixture(autouse=True)
def _reset_oidc_routes():
    """Reset module-level state between tests."""
    original_states = _pending_states.copy()
    set_oidc_client(None)
    _pending_states.clear()
    yield
    set_oidc_client(None)
    _pending_states.clear()
    _pending_states.update(original_states)


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# ============================================================================
# OIDCClient tests
# ============================================================================


class TestOIDCClientDiscover:
    @pytest.mark.asyncio
    async def test_discover_caches_result(self, oidc_client: OIDCClient) -> None:
        """Discovery document should be fetched once and cached."""
        mock_response = MagicMock()
        mock_response.json.return_value = DISCOVERY_DOC
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "shieldops.auth.oidc.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # First call fetches
            result1 = await oidc_client.discover()
            assert result1 == DISCOVERY_DOC

            # Second call uses cache (no additional HTTP call)
            result2 = await oidc_client.discover()
            assert result2 == DISCOVERY_DOC

            # HTTP client was only created once
            assert mock_client.get.await_count == 1


class TestOIDCClientAuthorizationURL:
    @pytest.mark.asyncio
    async def test_get_authorization_url_builds_correct_url(self, oidc_client: OIDCClient) -> None:
        """Authorization URL should include all required params."""
        oidc_client._discovery = DISCOVERY_DOC

        url, state = await oidc_client.get_authorization_url(state="test-state-123")

        assert url.startswith("https://idp.example.com/authorize?")
        assert "response_type=code" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=" in url
        assert "scope=openid email profile" in url
        assert "state=test-state-123" in url
        assert state == "test-state-123"

    @pytest.mark.asyncio
    async def test_get_authorization_url_generates_state(self, oidc_client: OIDCClient) -> None:
        """When no state is provided, one should be generated."""
        oidc_client._discovery = DISCOVERY_DOC

        url, state = await oidc_client.get_authorization_url()

        assert len(state) > 0
        assert f"state={state}" in url


class TestOIDCClientExchangeCode:
    @pytest.mark.asyncio
    async def test_exchange_code_posts_to_token_endpoint(self, oidc_client: OIDCClient) -> None:
        """Code exchange should POST to token endpoint with correct data."""
        oidc_client._discovery = DISCOVERY_DOC

        token_response = {
            "access_token": "at-123",
            "token_type": "bearer",
            "id_token": "id-456",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = token_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "shieldops.auth.oidc.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await oidc_client.exchange_code("auth-code-789")

        assert result == token_response
        mock_client.post.assert_awaited_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == DISCOVERY_DOC["token_endpoint"]
        post_data = call_kwargs[1]["data"]
        assert post_data["grant_type"] == "authorization_code"
        assert post_data["code"] == "auth-code-789"
        assert post_data["client_id"] == "test-client-id"
        assert post_data["client_secret"] == "test-client-secret"  # noqa: S105


class TestOIDCClientUserinfo:
    @pytest.mark.asyncio
    async def test_get_userinfo_sends_bearer_token(self, oidc_client: OIDCClient) -> None:
        """Userinfo request should include Bearer token header."""
        oidc_client._discovery = DISCOVERY_DOC

        userinfo = {
            "sub": "user-001",
            "email": "alice@example.com",
            "name": "Alice",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = userinfo
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "shieldops.auth.oidc.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await oidc_client.get_userinfo("at-123")

        assert result == userinfo
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[0][0] == DISCOVERY_DOC["userinfo_endpoint"]
        headers = call_kwargs[1]["headers"]
        assert headers["Authorization"] == "Bearer at-123"


# ============================================================================
# OIDC route tests
# ============================================================================


class TestOIDCLoginRoute:
    def test_oidc_not_configured_returns_501(self) -> None:
        """Login should return 501 when OIDC client is not set."""
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/auth/oidc/login",
            follow_redirects=False,
        )
        assert resp.status_code == 501
        assert resp.json()["detail"] == "OIDC not configured"

    def test_oidc_login_redirects(self) -> None:
        """Login should redirect to the IdP authorization URL."""
        mock_client = AsyncMock()
        mock_client.get_authorization_url = AsyncMock(
            return_value=(
                "https://idp.example.com/authorize?client_id=x",
                "state-abc",
            )
        )

        app = _create_test_app()
        set_oidc_client(mock_client)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/auth/oidc/login",
            follow_redirects=False,
        )
        assert resp.status_code == 307
        assert resp.headers["location"] == "https://idp.example.com/authorize?client_id=x"


class TestOIDCCallbackRoute:
    def test_oidc_callback_provisions_user(self) -> None:
        """Callback should exchange code, fetch userinfo, and return JWT."""
        mock_oidc = AsyncMock()
        mock_oidc.exchange_code = AsyncMock(return_value={"access_token": "at-xyz"})
        mock_oidc.get_userinfo = AsyncMock(
            return_value={
                "email": "bob@example.com",
                "name": "Bob",
            }
        )

        mock_repo = AsyncMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=None)
        mock_repo.create_user = AsyncMock(
            return_value={
                "id": "user-new",
                "email": "bob@example.com",
                "name": "Bob",
                "role": "viewer",
                "is_active": True,
            }
        )

        app = _create_test_app()
        app.state.repository = mock_repo
        set_oidc_client(mock_oidc)

        # Seed a valid state
        _pending_states["valid-state"] = True

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "auth-code", "state": "valid-state"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105
        assert data["user"]["email"] == "bob@example.com"
        assert data["user"]["role"] == "viewer"

        # User was auto-provisioned
        mock_repo.create_user.assert_awaited_once()

    def test_oidc_callback_existing_user(self) -> None:
        """Callback should return JWT for an existing user."""
        mock_oidc = AsyncMock()
        mock_oidc.exchange_code = AsyncMock(return_value={"access_token": "at-xyz"})
        mock_oidc.get_userinfo = AsyncMock(
            return_value={
                "email": "alice@example.com",
                "name": "Alice",
            }
        )

        existing_user: dict[str, Any] = {
            "id": "user-existing",
            "email": "alice@example.com",
            "name": "Alice",
            "role": "operator",
            "is_active": True,
        }
        mock_repo = AsyncMock()
        mock_repo.get_user_by_email = AsyncMock(return_value=existing_user)

        app = _create_test_app()
        app.state.repository = mock_repo
        set_oidc_client(mock_oidc)

        _pending_states["state-existing"] = True

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/auth/oidc/callback",
            params={
                "code": "auth-code",
                "state": "state-existing",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["role"] == "operator"
        # Should NOT create a new user
        mock_repo.create_user.assert_not_awaited()

    def test_oidc_callback_invalid_state_returns_400(
        self,
    ) -> None:
        """Callback should reject requests with unknown state."""
        mock_oidc = AsyncMock()
        app = _create_test_app()
        set_oidc_client(mock_oidc)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/auth/oidc/callback",
            params={
                "code": "auth-code",
                "state": "invalid-state",
            },
        )

        assert resp.status_code == 400
        assert "Invalid state" in resp.json()["detail"]

    def test_oidc_callback_not_configured_returns_501(
        self,
    ) -> None:
        """Callback should return 501 when OIDC is not configured."""
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/api/v1/auth/oidc/callback",
            params={
                "code": "auth-code",
                "state": "some-state",
            },
        )
        assert resp.status_code == 501
