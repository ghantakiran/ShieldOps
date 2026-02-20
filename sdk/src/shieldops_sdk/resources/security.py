"""Security resource -- sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.models import PaginatedResponse, SecurityScan


class SecurityResource:
    """Synchronous security API."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list_scans(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        scan_type: str | None = None,
    ) -> PaginatedResponse[SecurityScan]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if scan_type is not None:
            params["scan_type"] = scan_type
        resp = self._http.get("/security/scans", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[SecurityScan](
            items=[SecurityScan(**s) for s in data.get("scans", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    def get_scan(self, scan_id: str) -> SecurityScan:
        resp = self._http.get(f"/security/scans/{scan_id}")
        handle_response(resp)
        return SecurityScan(**resp.json())

    def trigger_scan(
        self,
        *,
        environment: str = "production",
        scan_type: str = "full",
        target_resources: list[str] | None = None,
        compliance_frameworks: list[str] | None = None,
        execute_actions: bool = False,
    ) -> dict[str, Any]:
        """Trigger an asynchronous security scan (returns 202)."""
        payload: dict[str, Any] = {
            "environment": environment,
            "scan_type": scan_type,
            "execute_actions": execute_actions,
        }
        if target_resources is not None:
            payload["target_resources"] = target_resources
        if compliance_frameworks is not None:
            payload["compliance_frameworks"] = compliance_frameworks
        resp = self._http.post("/security/scans", json=payload)
        handle_response(resp)
        return resp.json()

    def get_posture(self) -> dict[str, Any]:
        """Get overall security posture from the most recent scan."""
        resp = self._http.get("/security/posture")
        handle_response(resp)
        return resp.json()

    def list_cves(
        self,
        *,
        severity: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CVEs from the most recent scan."""
        params: dict[str, Any] = {"limit": limit}
        if severity is not None:
            params["severity"] = severity
        resp = self._http.get("/security/cves", params=params)
        handle_response(resp)
        return resp.json()

    def get_compliance(self, framework: str) -> dict[str, Any]:
        """Get compliance status for a specific framework."""
        resp = self._http.get(f"/security/compliance/{framework}")
        handle_response(resp)
        return resp.json()


class AsyncSecurityResource:
    """Asynchronous security API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list_scans(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        scan_type: str | None = None,
    ) -> PaginatedResponse[SecurityScan]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if scan_type is not None:
            params["scan_type"] = scan_type
        resp = await self._http.get("/security/scans", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[SecurityScan](
            items=[SecurityScan(**s) for s in data.get("scans", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    async def get_scan(self, scan_id: str) -> SecurityScan:
        resp = await self._http.get(f"/security/scans/{scan_id}")
        handle_response(resp)
        return SecurityScan(**resp.json())

    async def trigger_scan(
        self,
        *,
        environment: str = "production",
        scan_type: str = "full",
        target_resources: list[str] | None = None,
        compliance_frameworks: list[str] | None = None,
        execute_actions: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "environment": environment,
            "scan_type": scan_type,
            "execute_actions": execute_actions,
        }
        if target_resources is not None:
            payload["target_resources"] = target_resources
        if compliance_frameworks is not None:
            payload["compliance_frameworks"] = compliance_frameworks
        resp = await self._http.post("/security/scans", json=payload)
        handle_response(resp)
        return resp.json()

    async def get_posture(self) -> dict[str, Any]:
        resp = await self._http.get("/security/posture")
        handle_response(resp)
        return resp.json()

    async def list_cves(
        self,
        *,
        severity: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if severity is not None:
            params["severity"] = severity
        resp = await self._http.get("/security/cves", params=params)
        handle_response(resp)
        return resp.json()

    async def get_compliance(self, framework: str) -> dict[str, Any]:
        resp = await self._http.get(f"/security/compliance/{framework}")
        handle_response(resp)
        return resp.json()
