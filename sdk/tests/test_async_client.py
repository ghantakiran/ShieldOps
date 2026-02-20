"""Tests for the asynchronous AsyncShieldOpsClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from shieldops_sdk import AsyncShieldOpsClient
from shieldops_sdk.exceptions import NotFoundError

BASE = "http://localhost:8000/api/v1"


class TestAsyncClientLifecycle:
    @pytest.mark.asyncio
    async def test_async_client_context_manager(self) -> None:
        async with AsyncShieldOpsClient(api_key="k") as client:
            assert client.investigations is not None
            assert client.agents is not None
        assert client._http.is_closed


class TestAsyncInvestigations:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_client_list_investigations(self) -> None:
        respx.get(f"{BASE}/investigations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "investigations": [
                        {
                            "investigation_id": "inv-async-1",
                            "alert_id": "a1",
                            "alert_name": "Latency",
                            "status": "running",
                            "confidence": 0.0,
                            "hypotheses_count": 0,
                            "duration_ms": 0,
                        },
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        async with AsyncShieldOpsClient(api_key="k") as client:
            page = await client.investigations.list()
        assert page.total == 1
        assert page.items[0].investigation_id == "inv-async-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_get_investigation_not_found(self) -> None:
        respx.get(f"{BASE}/investigations/inv-missing").mock(
            return_value=httpx.Response(404, json={"detail": "Investigation not found"})
        )
        async with AsyncShieldOpsClient(api_key="k") as client:
            with pytest.raises(NotFoundError):
                await client.investigations.get("inv-missing")


class TestAsyncHealthCheck:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_health(self) -> None:
        respx.get("http://localhost:8000/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy", "version": "1.0.0"})
        )
        async with AsyncShieldOpsClient() as client:
            result = await client.health()
        assert result["status"] == "healthy"
