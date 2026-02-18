"""Tests for the agent fleet management endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class TestAgentListEndpoint:
    @pytest.mark.asyncio
    async def test_list_agents_returns_structure(self, client):
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert isinstance(data["agents"], list)

    @pytest.mark.asyncio
    async def test_list_agents_with_environment_filter(self, client):
        response = await client.get("/api/v1/agents?environment=production")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_agents_with_status_filter(self, client):
        response = await client.get("/api/v1/agents?status=idle")
        assert response.status_code == 200


class TestAgentDetailEndpoint:
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent_returns_404(self, client):
        response = await client.get("/api/v1/agents/nonexistent")
        assert response.status_code == 404


class TestAgentEnableDisable:
    @pytest.mark.asyncio
    async def test_enable_nonexistent_agent_returns_404(self, client):
        response = await client.post("/api/v1/agents/nonexistent/enable")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_nonexistent_agent_returns_404(self, client):
        response = await client.post("/api/v1/agents/nonexistent/disable")
        assert response.status_code == 404
