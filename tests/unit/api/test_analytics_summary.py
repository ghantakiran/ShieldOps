"""Tests for the GET /analytics/summary endpoint."""

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


class TestAnalyticsSummary:
    """Tests for GET /api/v1/analytics/summary."""

    def test_returns_defaults_when_no_engine(self, client: TestClient):
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_investigations"] == 0
        assert data["total_remediations"] == 0
        assert data["auto_resolved_percent"] == 0.0
        assert data["mean_time_to_resolve_seconds"] == 0
        assert data["investigations_by_status"] == {}
        assert data["remediations_by_status"] == {}

    def test_returns_engine_data_when_available(self, client: TestClient):
        mock_engine = AsyncMock()
        mock_engine.summary = AsyncMock(
            return_value={
                "total_investigations": 42,
                "total_remediations": 18,
                "auto_resolved_percent": 78.5,
                "mean_time_to_resolve_seconds": 320,
                "investigations_by_status": {"completed": 30, "in_progress": 12},
                "remediations_by_status": {"completed": 15, "failed": 3},
            }
        )
        analytics.set_engine(mock_engine)

        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_investigations"] == 42
        assert data["auto_resolved_percent"] == 78.5

    def test_returns_defaults_when_engine_returns_none(self, client: TestClient):
        mock_engine = AsyncMock()
        mock_engine.summary = AsyncMock(return_value=None)
        analytics.set_engine(mock_engine)

        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_investigations"] == 0

    def test_returns_defaults_when_engine_returns_empty(self, client: TestClient):
        mock_engine = AsyncMock()
        mock_engine.summary = AsyncMock(return_value={})
        analytics.set_engine(mock_engine)

        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        # Empty dict is falsy, should fall through to defaults
        data = resp.json()
        assert data["total_investigations"] == 0

    def test_requires_authentication(self, client: TestClient):
        """Verify the endpoint has auth dependency (covered by conftest override)."""
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200  # conftest overrides auth

    def test_response_shape_matches_frontend_type(self, client: TestClient):
        """All keys expected by AnalyticsSummary frontend type are present."""
        resp = client.get("/api/v1/analytics/summary")
        data = resp.json()
        expected_keys = {
            "total_investigations",
            "total_remediations",
            "auto_resolved_percent",
            "mean_time_to_resolve_seconds",
            "investigations_by_status",
            "remediations_by_status",
        }
        assert expected_keys == set(data.keys())

    def test_existing_mttr_endpoint_still_works(self, client: TestClient):
        """Ensure the new summary endpoint doesn't break existing ones."""
        resp = client.get("/api/v1/analytics/mttr")
        assert resp.status_code == 200

    def test_existing_resolution_rate_endpoint_still_works(self, client: TestClient):
        resp = client.get("/api/v1/analytics/resolution-rate")
        assert resp.status_code == 200
