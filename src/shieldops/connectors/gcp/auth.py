"""GCP authentication helper using google-auth for OAuth2 tokens.

Supports both service account JSON key files and Application Default
Credentials (ADC).  Tokens are cached and automatically refreshed when
they approach expiry.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger()

# Scopes required for Compute, GKE, Cloud SQL, and Monitoring APIs.
_DEFAULT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GCPAuthProvider:
    """Provides OAuth2 access tokens for GCP REST API calls.

    Parameters
    ----------
    credentials_path:
        Path to a service account JSON key file.  When *None*,
        Application Default Credentials are used instead.
    scopes:
        OAuth2 scopes.  Defaults to ``cloud-platform`` (full access).
    """

    def __init__(
        self,
        credentials_path: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        self._credentials_path = credentials_path
        self._scopes = scopes or _DEFAULT_SCOPES
        self._credentials: Any = None
        self._token: str | None = None
        self._expiry: float = 0.0

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

    def _load_credentials(self) -> Any:
        """Load google-auth credentials (lazy, first call only)."""
        import google.auth  # type: ignore[import-untyped]
        from google.oauth2 import service_account  # type: ignore[import-untyped]

        if self._credentials_path:
            logger.info(
                "gcp_auth_loading_service_account",
                path=self._credentials_path,
            )
            creds = service_account.Credentials.from_service_account_file(
                self._credentials_path,
                scopes=self._scopes,
            )
        else:
            logger.info("gcp_auth_using_adc")
            creds, _ = google.auth.default(scopes=self._scopes)

        return creds

    async def _refresh_token(self) -> None:
        """Refresh the cached access token."""
        import asyncio
        from functools import partial

        from google.auth.transport.requests import Request  # type: ignore[import-untyped]

        if self._credentials is None:
            self._credentials = self._load_credentials()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(self._credentials.refresh, Request()),
        )

        self._token = self._credentials.token
        # google-auth expiry is a datetime; fall back to 55-min window
        if hasattr(self._credentials, "expiry") and self._credentials.expiry:
            self._expiry = self._credentials.expiry.timestamp()
        else:
            self._expiry = time.time() + 3300  # 55 minutes

        logger.debug(
            "gcp_auth_token_refreshed",
            expires_in=int(self._expiry - time.time()),
        )
