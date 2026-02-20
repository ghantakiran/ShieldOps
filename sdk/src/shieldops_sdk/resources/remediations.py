"""Remediations resource -- sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.models import PaginatedResponse, Remediation


class RemediationsResource:
    """Synchronous remediations API."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        environment: str | None = None,
    ) -> PaginatedResponse[Remediation]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if environment is not None:
            params["environment"] = environment
        resp = self._http.get("/remediations", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Remediation](
            items=[Remediation(**r) for r in data.get("remediations", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    def get(self, remediation_id: str) -> Remediation:
        resp = self._http.get(f"/remediations/{remediation_id}")
        handle_response(resp)
        return Remediation(**resp.json())

    def create(
        self,
        *,
        action_type: str,
        target_resource: str,
        environment: str = "production",
        risk_level: str = "medium",
        parameters: dict[str, Any] | None = None,
        description: str = "",
        investigation_id: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a new remediation (async on server, returns 202)."""
        payload: dict[str, Any] = {
            "action_type": action_type,
            "target_resource": target_resource,
            "environment": environment,
            "risk_level": risk_level,
            "description": description,
        }
        if parameters is not None:
            payload["parameters"] = parameters
        if investigation_id is not None:
            payload["investigation_id"] = investigation_id
        resp = self._http.post("/remediations", json=payload)
        handle_response(resp)
        return resp.json()

    def approve(
        self,
        remediation_id: str,
        *,
        approver: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a pending remediation."""
        resp = self._http.post(
            f"/remediations/{remediation_id}/approve",
            json={"approver": approver, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    def deny(
        self,
        remediation_id: str,
        *,
        approver: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Deny a pending remediation."""
        resp = self._http.post(
            f"/remediations/{remediation_id}/deny",
            json={"approver": approver, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    def rollback(
        self,
        remediation_id: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Rollback a completed remediation."""
        resp = self._http.post(
            f"/remediations/{remediation_id}/rollback",
            json={"reason": reason},
        )
        handle_response(resp)
        return resp.json()


class AsyncRemediationsResource:
    """Asynchronous remediations API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        environment: str | None = None,
    ) -> PaginatedResponse[Remediation]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if environment is not None:
            params["environment"] = environment
        resp = await self._http.get("/remediations", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Remediation](
            items=[Remediation(**r) for r in data.get("remediations", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    async def get(self, remediation_id: str) -> Remediation:
        resp = await self._http.get(f"/remediations/{remediation_id}")
        handle_response(resp)
        return Remediation(**resp.json())

    async def create(
        self,
        *,
        action_type: str,
        target_resource: str,
        environment: str = "production",
        risk_level: str = "medium",
        parameters: dict[str, Any] | None = None,
        description: str = "",
        investigation_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action_type": action_type,
            "target_resource": target_resource,
            "environment": environment,
            "risk_level": risk_level,
            "description": description,
        }
        if parameters is not None:
            payload["parameters"] = parameters
        if investigation_id is not None:
            payload["investigation_id"] = investigation_id
        resp = await self._http.post("/remediations", json=payload)
        handle_response(resp)
        return resp.json()

    async def approve(
        self,
        remediation_id: str,
        *,
        approver: str,
        reason: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/remediations/{remediation_id}/approve",
            json={"approver": approver, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    async def deny(
        self,
        remediation_id: str,
        *,
        approver: str,
        reason: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/remediations/{remediation_id}/deny",
            json={"approver": approver, "reason": reason},
        )
        handle_response(resp)
        return resp.json()

    async def rollback(
        self,
        remediation_id: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.post(
            f"/remediations/{remediation_id}/rollback",
            json={"reason": reason},
        )
        handle_response(resp)
        return resp.json()
