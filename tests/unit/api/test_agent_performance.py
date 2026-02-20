"""Tests for the GET /analytics/agent-performance endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app
from shieldops.api.routes import analytics


@pytest.fixture(autouse=True)
def _reset_engine():
    """Reset the analytics engine between tests."""
    original = analytics._engine
    analytics._engine = None
    yield
    analytics._engine = original


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestAgentPerformance:
    """Tests for GET /api/v1/analytics/agent-performance."""

    def test_default_period_response_structure(self, client: TestClient):
        """Default 7d period returns correct top-level keys."""
        resp = client.get("/api/v1/analytics/agent-performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "7d"
        assert "summary" in data
        assert "agents" in data
        assert "hourly_heatmap" in data
        # Summary keys
        summary = data["summary"]
        assert "total_executions" in summary
        assert "avg_success_rate" in summary
        assert "avg_duration_seconds" in summary
        assert "total_errors" in summary

    def test_custom_period_1h(self, client: TestClient):
        """Short period (1h) is accepted and returned."""
        resp = client.get("/api/v1/analytics/agent-performance?period=1h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "1h"
        assert len(data["agents"]) > 0

    def test_custom_period_30d(self, client: TestClient):
        """Longer period (30d) is accepted and returns data."""
        resp = client.get("/api/v1/analytics/agent-performance?period=30d")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "30d"
        # 30d should have more executions than 1h
        assert data["summary"]["total_executions"] > 0

    def test_agent_type_filter(self, client: TestClient):
        """Filter by agent_type returns only that type."""
        resp = client.get("/api/v1/analytics/agent-performance?agent_type=investigation")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["agent_type"] == "investigation"

    def test_invalid_period_rejected(self, client: TestClient):
        """Invalid period format is rejected (422)."""
        resp = client.get("/api/v1/analytics/agent-performance?period=invalid")
        assert resp.status_code == 422

    def test_empty_data_when_engine_returns_none(self, client: TestClient):
        """Falls back to demo data when engine returns None."""
        mock_engine = AsyncMock()
        mock_engine.agent_performance = AsyncMock(return_value=None)
        analytics.set_engine(mock_engine)

        resp = client.get("/api/v1/analytics/agent-performance")
        assert resp.status_code == 200
        data = resp.json()
        # Demo data should have all 4 agent types
        assert len(data["agents"]) == 4
        agent_types = {a["agent_type"] for a in data["agents"]}
        assert agent_types == {
            "investigation",
            "remediation",
            "security",
            "learning",
        }

    def test_engine_data_when_available(self, client: TestClient):
        """Uses engine data when engine returns a result."""
        engine_result = {
            "period": "7d",
            "summary": {
                "total_executions": 100,
                "avg_success_rate": 0.91,
                "avg_duration_seconds": 45.0,
                "total_errors": 9,
            },
            "agents": [
                {
                    "agent_type": "investigation",
                    "total_executions": 100,
                    "success_rate": 0.91,
                    "avg_duration_seconds": 45.0,
                    "error_count": 9,
                    "p50_duration": 30.0,
                    "p95_duration": 80.0,
                    "p99_duration": 150.0,
                    "trend": [],
                }
            ],
            "hourly_heatmap": [],
        }
        mock_engine = AsyncMock()
        mock_engine.agent_performance = AsyncMock(return_value=engine_result)
        analytics.set_engine(mock_engine)

        resp = client.get("/api/v1/analytics/agent-performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_executions"] == 100
        assert data["summary"]["avg_success_rate"] == 0.91
        assert len(data["agents"]) == 1

    def test_agent_metrics_have_required_fields(self, client: TestClient):
        """Each agent entry has all required metric fields."""
        resp = client.get("/api/v1/analytics/agent-performance")
        assert resp.status_code == 200
        data = resp.json()
        required_fields = {
            "agent_type",
            "total_executions",
            "success_rate",
            "avg_duration_seconds",
            "error_count",
            "p50_duration",
            "p95_duration",
            "p99_duration",
            "trend",
        }
        for agent in data["agents"]:
            assert required_fields.issubset(set(agent.keys())), (
                f"Missing fields in {agent['agent_type']}: {required_fields - set(agent.keys())}"
            )

    def test_success_rate_within_bounds(self, client: TestClient):
        """Success rates are between 0.0 and 1.0."""
        resp = client.get("/api/v1/analytics/agent-performance")
        data = resp.json()
        for agent in data["agents"]:
            assert 0.0 <= agent["success_rate"] <= 1.0, (
                f"{agent['agent_type']} success_rate {agent['success_rate']} out of range"
            )
        assert 0.0 <= data["summary"]["avg_success_rate"] <= 1.0

    def test_hourly_heatmap_structure(self, client: TestClient):
        """Heatmap contains hour/day/count entries."""
        resp = client.get("/api/v1/analytics/agent-performance")
        data = resp.json()
        heatmap = data["hourly_heatmap"]
        assert len(heatmap) == 7 * 24  # 7 days x 24 hours
        for cell in heatmap:
            assert "hour" in cell
            assert "day" in cell
            assert "count" in cell
            assert 0 <= cell["hour"] <= 23
            assert cell["day"] in {
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
            }
            assert cell["count"] >= 0

    def test_demo_data_deterministic(self, client: TestClient):
        """Same period returns same demo data (seeded RNG)."""
        r1 = client.get("/api/v1/analytics/agent-performance?period=7d")
        r2 = client.get("/api/v1/analytics/agent-performance?period=7d")
        assert r1.json() == r2.json()

    def test_trend_data_present(self, client: TestClient):
        """Each agent has trend data with date/executions/rate."""
        resp = client.get("/api/v1/analytics/agent-performance")
        data = resp.json()
        for agent in data["agents"]:
            assert len(agent["trend"]) > 0
            for point in agent["trend"]:
                assert "date" in point
                assert "executions" in point
                assert "success_rate" in point
                assert point["executions"] >= 1

    def test_existing_analytics_endpoints_still_work(self, client: TestClient):
        """New endpoint does not break existing analytics."""
        for path in [
            "/api/v1/analytics/mttr",
            "/api/v1/analytics/resolution-rate",
            "/api/v1/analytics/agent-accuracy",
            "/api/v1/analytics/summary",
        ]:
            resp = client.get(path)
            assert resp.status_code == 200, f"Existing endpoint {path} broken"
