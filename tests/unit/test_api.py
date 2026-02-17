"""Unit tests for the FastAPI application."""

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestAgentEndpoints:
    @pytest.mark.asyncio
    async def test_list_agents(self, client):
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, client):
        response = await client.get("/api/v1/agents/nonexistent")
        assert response.status_code == 200  # Returns status not_found


class TestInvestigationEndpoints:
    @pytest.mark.asyncio
    async def test_list_investigations(self, client):
        response = await client.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert "investigations" in data


class TestRemediationEndpoints:
    @pytest.mark.asyncio
    async def test_list_remediations(self, client):
        response = await client.get("/api/v1/remediations")
        assert response.status_code == 200
        data = response.json()
        assert "remediations" in data


class TestAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_mttr_trends(self, client):
        response = await client.get("/api/v1/analytics/mttr")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_resolution_rate(self, client):
        response = await client.get("/api/v1/analytics/resolution-rate")
        assert response.status_code == 200


class TestSecurityEndpoints:
    @pytest.mark.asyncio
    async def test_security_posture(self, client):
        response = await client.get("/api/v1/security/posture")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_compliance_status(self, client):
        response = await client.get("/api/v1/security/compliance/soc2")
        assert response.status_code == 200
        data = response.json()
        assert data["framework"] == "soc2"
