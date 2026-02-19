"""Tests for the GET /cost/summary endpoint."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app
from shieldops.api.routes import cost


@pytest.fixture(autouse=True)
def _reset_runner():
    """Reset the cost runner between tests."""
    original = cost._runner
    cost._runner = None
    yield
    cost._runner = original


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_runner(analyses=None, state=None):
    runner = MagicMock()
    runner.list_analyses.return_value = analyses or []
    runner.get_analysis.return_value = state
    return runner


class TestCostSummary:
    """Tests for GET /api/v1/cost/summary."""

    def test_returns_defaults_when_no_analyses(self, client: TestClient):
        cost.set_runner(_make_mock_runner())
        resp = client.get("/api/v1/cost/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_daily"] == 0
        assert data["total_monthly"] == 0
        assert data["top_services"] == []
        assert data["anomalies"] == []

    def test_returns_defaults_when_no_completed_analyses(self, client: TestClient):
        cost.set_runner(_make_mock_runner(analyses=[{"status": "running", "analysis_id": "a1"}]))
        resp = client.get("/api/v1/cost/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly"] == 0

    def test_returns_data_from_completed_analysis(self, client: TestClient):
        state = MagicMock()
        state.total_monthly_spend = 15000
        state.change_percent = 5.2
        state.service_breakdown = []
        state.cost_anomalies = []
        runner = _make_mock_runner(
            analyses=[{"status": "complete", "analysis_id": "a1"}],
            state=state,
        )
        cost.set_runner(runner)

        resp = client.get("/api/v1/cost/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly"] == 15000
        assert data["total_daily"] == 500.0

    def test_returns_defaults_when_analysis_state_is_none(self, client: TestClient):
        runner = _make_mock_runner(
            analyses=[{"status": "complete", "analysis_id": "a1"}],
            state=None,
        )
        cost.set_runner(runner)

        resp = client.get("/api/v1/cost/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly"] == 0

    def test_response_shape_matches_frontend_type(self, client: TestClient):
        cost.set_runner(_make_mock_runner())
        resp = client.get("/api/v1/cost/summary")
        data = resp.json()
        expected_keys = {
            "total_daily",
            "total_monthly",
            "change_percent",
            "top_services",
            "anomalies",
        }
        assert expected_keys == set(data.keys())

    def test_existing_analyses_endpoint_still_works(self, client: TestClient):
        cost.set_runner(_make_mock_runner())
        resp = client.get("/api/v1/cost/analyses")
        assert resp.status_code == 200
