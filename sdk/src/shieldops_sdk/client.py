"""Synchronous ShieldOps API client."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.resources.agents import AgentsResource
from shieldops_sdk.resources.investigations import InvestigationsResource
from shieldops_sdk.resources.remediations import RemediationsResource
from shieldops_sdk.resources.security import SecurityResource
from shieldops_sdk.resources.vulnerabilities import VulnerabilitiesResource

_DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
_DEFAULT_TIMEOUT = 30.0


class ShieldOpsClient:
    """Synchronous client for the ShieldOps REST API.

    Usage::

        with ShieldOpsClient(api_key="sk-...") as client:
            invs = client.investigations.list(limit=10)
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

        self._http = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

        # Resource namespaces
        self.investigations = InvestigationsResource(self._http)
        self.remediations = RemediationsResource(self._http)
        self.security = SecurityResource(self._http)
        self.vulnerabilities = VulnerabilitiesResource(self._http)
        self.agents = AgentsResource(self._http)

    # -- Context manager --------------------------------------------------

    def __enter__(self) -> ShieldOpsClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._http.close()

    # -- Convenience methods ----------------------------------------------

    def health(self) -> dict[str, Any]:
        """Check the API health endpoint."""
        # Health lives outside the /api/v1 prefix, so use an absolute URL.
        base = str(self._http.base_url)
        # Strip the API version path to reach the root.
        root = base.rsplit("/api/", 1)[0] if "/api/" in base else base
        resp = self._http.get(f"{root}/health")
        handle_response(resp)
        return resp.json()
