"""Investigations resource -- sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.models import Investigation, PaginatedResponse


class InvestigationsResource:
    """Synchronous investigations API."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> PaginatedResponse[Investigation]:
        """List investigations with optional status filter."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        resp = self._http.get("/investigations", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Investigation](
            items=[Investigation(**i) for i in data.get("investigations", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    def get(self, investigation_id: str) -> Investigation:
        """Retrieve a single investigation by ID."""
        resp = self._http.get(f"/investigations/{investigation_id}")
        handle_response(resp)
        return Investigation(**resp.json())

    def create(
        self,
        *,
        alert_id: str,
        alert_name: str,
        severity: str = "warning",
        source: str = "api",
        resource_id: str | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a new investigation (async on server, returns 202)."""
        payload: dict[str, Any] = {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "severity": severity,
            "source": source,
        }
        if resource_id is not None:
            payload["resource_id"] = resource_id
        if labels is not None:
            payload["labels"] = labels
        if annotations is not None:
            payload["annotations"] = annotations
        if description is not None:
            payload["description"] = description
        resp = self._http.post("/investigations", json=payload)
        handle_response(resp)
        return resp.json()


class AsyncInvestigationsResource:
    """Asynchronous investigations API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> PaginatedResponse[Investigation]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        resp = await self._http.get("/investigations", params=params)
        handle_response(resp)
        data = resp.json()
        return PaginatedResponse[Investigation](
            items=[Investigation(**i) for i in data.get("investigations", [])],
            total=data.get("total", 0),
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    async def get(self, investigation_id: str) -> Investigation:
        resp = await self._http.get(f"/investigations/{investigation_id}")
        handle_response(resp)
        return Investigation(**resp.json())

    async def create(
        self,
        *,
        alert_id: str,
        alert_name: str,
        severity: str = "warning",
        source: str = "api",
        resource_id: str | None = None,
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "severity": severity,
            "source": source,
        }
        if resource_id is not None:
            payload["resource_id"] = resource_id
        if labels is not None:
            payload["labels"] = labels
        if annotations is not None:
            payload["annotations"] = annotations
        if description is not None:
            payload["description"] = description
        resp = await self._http.post("/investigations", json=payload)
        handle_response(resp)
        return resp.json()
