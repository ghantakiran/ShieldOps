"""Asynchronous ShieldOps API client."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.resources.agents import AsyncAgentsResource
from shieldops_sdk.resources.investigations import AsyncInvestigationsResource
from shieldops_sdk.resources.remediations import AsyncRemediationsResource
from shieldops_sdk.resources.security import AsyncSecurityResource
from shieldops_sdk.resources.vulnerabilities import AsyncVulnerabilitiesResource

_DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
_DEFAULT_TIMEOUT = 30.0


class AsyncShieldOpsClient:
    """Async client for the ShieldOps REST API.

    Usage::

        async with AsyncShieldOpsClient(api_key="sk-...") as client:
            invs = await client.investigations.list(limit=10)
            for inv in invs.items:
                print(inv.investigation_id, inv.status)
    """

    def __init__(
        self,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        headers: dict[str, str] = {"User-Agent": "shieldops-sdk/0.1.0"}
        if api_key:
            headers["X-API-Key"] = api_key
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

        # Resource namespaces
        self.investigations = AsyncInvestigationsResource(self._http)
        self.remediations = AsyncRemediationsResource(self._http)
        self.security = AsyncSecurityResource(self._http)
        self.vulnerabilities = AsyncVulnerabilitiesResource(self._http)
        self.agents = AsyncAgentsResource(self._http)

    # -- Async context manager --------------------------------------------

    async def __aenter__(self) -> AsyncShieldOpsClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP transport."""
        await self._http.aclose()

    # -- Convenience methods ----------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Check the API health endpoint."""
        base = str(self._http.base_url)
        root = base.rsplit("/api/", 1)[0] if "/api/" in base else base
        resp = await self._http.get(f"{root}/health")
        handle_response(resp)
        return resp.json()
