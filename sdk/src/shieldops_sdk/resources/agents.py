"""Agents resource -- sync and async."""

from __future__ import annotations

from typing import Any

import httpx

from shieldops_sdk._response import handle_response
from shieldops_sdk.models import Agent


class AgentsResource:
    """Synchronous agents API."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        environment: str | None = None,
        status: str | None = None,
    ) -> list[Agent]:
        """List all deployed agents with optional filters."""
        params: dict[str, Any] = {}
        if environment is not None:
            params["environment"] = environment
        if status is not None:
            params["status"] = status
        resp = self._http.get("/agents", params=params)
        handle_response(resp)
        data = resp.json()
        return [Agent(**a) for a in data.get("agents", [])]

    def get(self, agent_id: str) -> Agent:
        """Get detailed agent information."""
        resp = self._http.get(f"/agents/{agent_id}")
        handle_response(resp)
        return Agent(**resp.json())

    def enable(self, agent_id: str) -> dict[str, Any]:
        """Enable a disabled agent."""
        resp = self._http.post(f"/agents/{agent_id}/enable")
        handle_response(resp)
        return resp.json()

    def disable(self, agent_id: str) -> dict[str, Any]:
        """Disable an active agent (graceful shutdown)."""
        resp = self._http.post(f"/agents/{agent_id}/disable")
        handle_response(resp)
        return resp.json()


class AsyncAgentsResource:
    """Asynchronous agents API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list(
        self,
        *,
        environment: str | None = None,
        status: str | None = None,
    ) -> list[Agent]:
        params: dict[str, Any] = {}
        if environment is not None:
            params["environment"] = environment
        if status is not None:
            params["status"] = status
        resp = await self._http.get("/agents", params=params)
        handle_response(resp)
        data = resp.json()
        return [Agent(**a) for a in data.get("agents", [])]

    async def get(self, agent_id: str) -> Agent:
        resp = await self._http.get(f"/agents/{agent_id}")
        handle_response(resp)
        return Agent(**resp.json())

    async def enable(self, agent_id: str) -> dict[str, Any]:
        resp = await self._http.post(f"/agents/{agent_id}/enable")
        handle_response(resp)
        return resp.json()

    async def disable(self, agent_id: str) -> dict[str, Any]:
        resp = await self._http.post(f"/agents/{agent_id}/disable")
        handle_response(resp)
        return resp.json()
