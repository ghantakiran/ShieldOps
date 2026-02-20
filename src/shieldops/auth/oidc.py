"""OIDC / SSO authentication support.

Implements OpenID Connect Authorization Code Flow:
1. GET /auth/oidc/login  -> redirect to IdP
2. GET /auth/oidc/callback -> exchange code -> create/find user -> JWT

Works with any OIDC-compliant provider (Okta, Auth0, Azure AD, Google).
"""

import secrets
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class OIDCClient:
    """Stateless OIDC client that discovers endpoints from issuer."""

    def __init__(
        self,
        issuer_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str = "openid email profile",
    ) -> None:
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._scopes = scopes
        self._discovery: dict[str, Any] | None = None

    async def discover(self) -> dict[str, Any]:
        """Fetch OIDC discovery document (cached after first call)."""
        if self._discovery is not None:
            return self._discovery
        url = f"{self._issuer_url}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._discovery = resp.json()
        return self._discovery

    async def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Build IdP authorization URL. Returns (url, state)."""
        discovery = await self.discover()
        auth_endpoint = discovery["authorization_endpoint"]
        state = state or secrets.token_urlsafe(32)
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": self._scopes,
            "state": state,
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{auth_endpoint}?{qs}", state

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""
        discovery = await self.discover()
        token_endpoint = discovery["token_endpoint"]
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch user info from the OIDC provider."""
        discovery = await self.discover()
        userinfo_endpoint = discovery["userinfo_endpoint"]
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
