"""Vulnerabilities resource -- sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.models import PaginatedResponse, Vulnerability


class VulnerabilitiesResource:
    """Synchronous vulnerabilities API."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        severity: str | None = None,
        scanner_type: str | None = None,
        team_id: str | None = None,
        sla_breached: bool | None = None,
    ) -> PaginatedResponse[Vulnerability]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if severity is not None:
            params["severity"] = severity
        if scanner_type is not None:
            params["scanner_type"] = scanner_type
        if team_id is not None:
            params["team_id"] = team_id
        if sla_breached is not None:
            params["sla_breached"] = sla_breached
        resp = self._http.get("/vulnerabilities", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Vulnerability](
            items=[Vulnerability(**v) for v in data.get("vulnerabilities", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    def get(self, vuln_id: str) -> dict[str, Any]:
        """Get vulnerability detail (includes comments)."""
        resp = self._http.get(f"/vulnerabilities/{vuln_id}")
        handle_response(resp)
        return resp.json()

    def update_status(
        self,
        vuln_id: str,
        *,
        status: str,
        reason: str = "",
    ) -> dict[str, Any]:
        resp = self._http.put(
            f"/vulnerabilities/{vuln_id}/status",
            json={"status": status, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    def assign(
        self,
        vuln_id: str,
        *,
        team_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        resp = self._http.post(
            f"/vulnerabilities/{vuln_id}/assign",
            json={"team_id": team_id, "user_id": user_id},
        )
        handle_response(resp)
        return resp.json()

    def add_comment(
        self,
        vuln_id: str,
        *,
        content: str,
        comment_type: str = "comment",
    ) -> dict[str, Any]:
        resp = self._http.post(
            f"/vulnerabilities/{vuln_id}/comments",
            json={"content": content, "comment_type": comment_type},
        )
        handle_response(resp)
        return resp.json()

    def list_comments(self, vuln_id: str) -> dict[str, Any]:
        resp = self._http.get(f"/vulnerabilities/{vuln_id}/comments")
        handle_response(resp)
        return resp.json()

    def accept_risk(
        self,
        vuln_id: str,
        *,
        reason: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"reason": reason}
        if expires_at is not None:
            payload["expires_at"] = expires_at
        resp = self._http.post(
            f"/vulnerabilities/{vuln_id}/accept-risk",
            json=payload,
        )
        handle_response(resp)
        return resp.json()

    def get_stats(self) -> dict[str, Any]:
        resp = self._http.get("/vulnerabilities/stats")
        handle_response(resp)
        return resp.json()

    def list_sla_breaches(self, *, limit: int = 50) -> dict[str, Any]:
        resp = self._http.get(
            "/vulnerabilities/sla-breaches",
            params={"limit": limit},
        )
        handle_response(resp)
        return resp.json()


class AsyncVulnerabilitiesResource:
    """Asynchronous vulnerabilities API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        severity: str | None = None,
        scanner_type: str | None = None,
        team_id: str | None = None,
        sla_breached: bool | None = None,
    ) -> PaginatedResponse[Vulnerability]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if severity is not None:
            params["severity"] = severity
        if scanner_type is not None:
            params["scanner_type"] = scanner_type
        if team_id is not None:
            params["team_id"] = team_id
        if sla_breached is not None:
            params["sla_breached"] = sla_breached
        resp = await self._http.get("/vulnerabilities", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Vulnerability](
            items=[Vulnerability(**v) for v in data.get("vulnerabilities", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    async def get(self, vuln_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/vulnerabilities/{vuln_id}")
        handle_response(resp)
        return resp.json()

    async def update_status(
        self,
        vuln_id: str,
        *,
        status: str,
        reason: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.put(
            f"/vulnerabilities/{vuln_id}/status",
            json={"status": status, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    async def assign(
        self,
        vuln_id: str,
        *,
        team_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/vulnerabilities/{vuln_id}/assign",
            json={"team_id": team_id, "user_id": user_id},
        )
        handle_response(resp)
        return resp.json()

    async def add_comment(
        self,
        vuln_id: str,
        *,
        content: str,
        comment_type: str = "comment",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/vulnerabilities/{vuln_id}/comments",
            json={"content": content, "comment_type": comment_type},
        )
        handle_response(resp)
        return resp.json()

    async def list_comments(self, vuln_id: str) -> dict[str, Any]:
        resp = await self._http.get(f"/vulnerabilities/{vuln_id}/comments")
        handle_response(resp)
        return resp.json()

    async def accept_risk(
        self,
        vuln_id: str,
        *,
        reason: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"reason": reason}
        if expires_at is not None:
            payload["expires_at"] = expires_at
        resp = await self._http.post(
            f"/vulnerabilities/{vuln_id}/accept-risk",
            json=payload,
        )
        handle_response(resp)
        return resp.json()

    async def get_stats(self) -> dict[str, Any]:
        resp = await self._http.get("/vulnerabilities/stats")
        handle_response(resp)
        return resp.json()

    async def list_sla_breaches(self, *, limit: int = 50) -> dict[str, Any]:
        resp = await self._http.get(
            "/vulnerabilities/sla-breaches",
            params={"limit": limit},
        )
        handle_response(resp)
        return resp.json()
