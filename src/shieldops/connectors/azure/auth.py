"""Azure AD authentication via OAuth2 client credentials flow.

Acquires tokens from the Microsoft identity platform using direct REST
calls (no Azure SDK dependency).  Tokens are cached and automatically
refreshed before expiry.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class AzureAuthProvider:
    """Provides OAuth2 access tokens for Azure REST API calls.

    Parameters
    ----------
    tenant_id:
        Azure AD tenant ID.  Falls back to ``AZURE_TENANT_ID`` env var.
    client_id:
        Application (service principal) client ID.  Falls back to
        ``AZURE_CLIENT_ID`` env var.
    client_secret:
        Application client secret.  Falls back to ``AZURE_CLIENT_SECRET``
        env var.
    subscription_id:
        Azure subscription ID.  Falls back to ``AZURE_SUBSCRIPTION_ID``
        env var.
    """

    _TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"  # noqa: S105
    _DEFAULT_SCOPE = "https://management.azure.com/.default"

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id or os.environ["AZURE_TENANT_ID"]
        self.client_id = client_id or os.environ["AZURE_CLIENT_ID"]
        self._client_secret = client_secret or os.environ["AZURE_CLIENT_SECRET"]
        self.subscription_id = subscription_id or os.environ["AZURE_SUBSCRIPTION_ID"]

        self._token: str | None = None
        self._expiry: float = 0.0
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_access_token(self) -> str:
        """Return a valid OAuth2 access token, refreshing if needed."""
        if self._token and time.time() < self._expiry - 60:
            return self._token

        await self._refresh_token()
        assert self._token is not None
        return self._token

    async def get_auth_headers(self) -> dict[str, str]:
        """Return HTTP headers with a valid Bearer token."""
        token = await self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _refresh_token(self) -> None:
        """Acquire a new token via the client credentials grant."""
        url = self._TOKEN_URL.format(tenant_id=self.tenant_id)
        form_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "scope": self._DEFAULT_SCOPE,
        }

        client = await self._get_client()
        resp = await client.post(
            url,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()

        self._token = result["access_token"]
        # expires_in is seconds from now; default to 55 min if missing
        expires_in = int(result.get("expires_in", 3300))
        self._expiry = time.time() + expires_in

        logger.debug(
            "azure_auth_token_refreshed",
            expires_in=expires_in,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
