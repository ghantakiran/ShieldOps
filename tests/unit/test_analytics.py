"""Tests for the analytics engine and API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class TestAnalyticsEndpoints:
    """Test that analytics endpoints return proper structure (stub fallback)."""

    @pytest.mark.asyncio
    async def test_mttr_trends_returns_structure(self, client):
        response = await client.get("/api/v1/analytics/mttr")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "data_points" in data
        assert "current_mttr_minutes" in data
        assert isinstance(data["data_points"], list)

    @pytest.mark.asyncio
    async def test_mttr_with_environment_filter(self, client):
        response = await client.get("/api/v1/analytics/mttr?environment=production")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_resolution_rate_returns_structure(self, client):
        response = await client.get("/api/v1/analytics/resolution-rate")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "automated_rate" in data
        assert "manual_rate" in data
        assert "total_incidents" in data

    @pytest.mark.asyncio
    async def test_agent_accuracy_returns_structure(self, client):
        response = await client.get("/api/v1/analytics/agent-accuracy")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "accuracy" in data
        assert "total_investigations" in data

    @pytest.mark.asyncio
    async def test_cost_savings_returns_structure(self, client):
        response = await client.get("/api/v1/analytics/cost-savings")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "hours_saved" in data
        assert "estimated_savings_usd" in data
        assert "engineer_hourly_rate" in data

    @pytest.mark.asyncio
    async def test_cost_savings_custom_rate(self, client):
        response = await client.get(
            "/api/v1/analytics/cost-savings?engineer_hourly_rate=100"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["engineer_hourly_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_custom_period(self, client):
        response = await client.get("/api/v1/analytics/mttr?period=7d")
        assert response.status_code == 200
        assert response.json()["period"] == "7d"


class TestAnalyticsEngineParsing:
    """Test the period parsing utility."""

    def test_parse_period_default(self):
        from shieldops.analytics.engine import _parse_period
        cutoff = _parse_period("30d")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) - timedelta(days=30)
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_parse_period_7d(self):
        from shieldops.analytics.engine import _parse_period
        cutoff = _parse_period("7d")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) - timedelta(days=7)
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_parse_period_invalid_defaults_30(self):
        from shieldops.analytics.engine import _parse_period
        cutoff = _parse_period("invalid")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) - timedelta(days=30)
        assert abs((cutoff - expected).total_seconds()) < 2
