"""Tests for onboarding wizard API endpoints.

Tests cover:
- GET /onboarding/status (default state, with progress)
- POST /onboarding/step/{step_name} (complete, skip, invalid step, validation)
- POST /onboarding/validate-cloud (success, missing fields, per-provider)
- POST /onboarding/deploy-agent (success, invalid type)
- POST /onboarding/trigger-demo (success, default scenario)
- Skip step
- Completed org state
- Database unavailable
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import onboarding


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(onboarding.router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def _reset_module_repo() -> Any:
    original = onboarding._repository
    onboarding._repository = None
    yield
    onboarding._repository = original


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_onboarding_progress = AsyncMock(return_value=[])
    repo.update_onboarding_step = AsyncMock(return_value=None)
    repo.update_organization = AsyncMock(return_value=None)
    return repo


def _build_client(mock_repo: AsyncMock) -> TestClient:
    app = _create_test_app()
    onboarding.set_repository(mock_repo)
    return TestClient(app, raise_server_exceptions=False)


def _make_progress(
    steps: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Build a list of onboarding progress dicts.

    Each tuple is (step_name, status).
    """
    result: list[dict[str, Any]] = []
    for step_name, status in steps or []:
        result.append(
            {
                "id": f"onb-{step_name[:6]}",
                "org_id": "default",
                "step_name": step_name,
                "status": status,
                "metadata": {},
                "completed_at": (
                    "2026-02-20T12:00:00+00:00" if status in ("completed", "skipped") else None
                ),
                "created_at": "2026-02-20T11:00:00+00:00",
            }
        )
    return result


# ================================================================
# GET /onboarding/status
# ================================================================


class TestGetOnboardingStatus:
    def test_returns_all_steps_default(self, mock_repo: AsyncMock) -> None:
        """Status endpoint returns all 5 steps with pending status."""
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["org_id"] == "default"
        assert len(data["steps"]) == 5
        assert data["current_step"] == "create_org"
        assert data["completed"] is False
        # All steps should be pending
        for step in data["steps"]:
            assert step["status"] == "pending"

    def test_returns_progress_from_db(self, mock_repo: AsyncMock) -> None:
        """Status endpoint reflects DB progress."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress(
                [
                    ("create_org", "completed"),
                    ("connect_cloud", "completed"),
                ]
            )
        )
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_step"] == "deploy_agent"
        assert data["completed"] is False
        # First two steps should be completed
        assert data["steps"][0]["status"] == "completed"
        assert data["steps"][1]["status"] == "completed"
        assert data["steps"][2]["status"] == "pending"

    def test_custom_org_id(self, mock_repo: AsyncMock) -> None:
        """Status endpoint accepts custom org_id parameter."""
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status?org_id=org-custom")
        assert resp.status_code == 200
        mock_repo.get_onboarding_progress.assert_called_once_with("org-custom")


# ================================================================
# POST /onboarding/step/{step_name}
# ================================================================


class TestCompleteStep:
    def test_complete_step(self, mock_repo: AsyncMock) -> None:
        """Completing a step updates the DB and returns new state."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress([("create_org", "completed")])
        )
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/create_org",
            json={
                "status": "completed",
                "metadata": {"name": "Acme Corp", "industry": "saas"},
            },
        )
        assert resp.status_code == 200
        mock_repo.update_onboarding_step.assert_called_once_with(
            org_id="default",
            step="create_org",
            status="completed",
            metadata={"name": "Acme Corp", "industry": "saas"},
        )

    def test_invalid_step_name(self, mock_repo: AsyncMock) -> None:
        """Invalid step name returns 400."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/bogus_step",
            json={"status": "completed", "metadata": {}},
        )
        assert resp.status_code == 400
        assert "Invalid step name" in resp.json()["detail"]

    def test_create_org_requires_name(self, mock_repo: AsyncMock) -> None:
        """Completing create_org without name returns 422."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/create_org",
            json={"status": "completed", "metadata": {}},
        )
        assert resp.status_code == 422
        assert "Organization name is required" in resp.json()["detail"]

    def test_create_org_empty_name(self, mock_repo: AsyncMock) -> None:
        """Completing create_org with empty string name returns 422."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/create_org",
            json={"status": "completed", "metadata": {"name": "  "}},
        )
        assert resp.status_code == 422

    def test_skip_step(self, mock_repo: AsyncMock) -> None:
        """Skipping a step records 'skipped' status."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress([("configure_playbook", "skipped")])
        )
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/configure_playbook",
            json={"status": "skipped"},
        )
        assert resp.status_code == 200
        mock_repo.update_onboarding_step.assert_called_once_with(
            org_id="default",
            step="configure_playbook",
            status="skipped",
            metadata={},
        )

    def test_completed_org_updates_settings(self, mock_repo: AsyncMock) -> None:
        """When all steps done, org settings get onboarding_completed flag."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress(
                [
                    ("create_org", "completed"),
                    ("connect_cloud", "completed"),
                    ("deploy_agent", "completed"),
                    ("configure_playbook", "skipped"),
                    ("run_demo", "completed"),
                ]
            )
        )
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/run_demo",
            json={"status": "completed", "metadata": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] is True
        mock_repo.update_organization.assert_called_once()

    def test_invalid_status_value(self, mock_repo: AsyncMock) -> None:
        """Invalid status value is rejected by Pydantic."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/step/create_org",
            json={"status": "in_progress", "metadata": {}},
        )
        assert resp.status_code == 422


# ================================================================
# POST /onboarding/validate-cloud
# ================================================================


class TestValidateCloud:
    def test_aws_validation_success(self, mock_repo: AsyncMock) -> None:
        """Valid AWS credentials return success with services."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/validate-cloud",
            json={
                "provider": "aws",
                "credentials": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "aws"
        assert "EC2" in data["services_discovered"]
        # Should update the connect_cloud step
        mock_repo.update_onboarding_step.assert_called_once()

    def test_gcp_validation_success(self, mock_repo: AsyncMock) -> None:
        """Valid GCP credentials return success."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/validate-cloud",
            json={
                "provider": "gcp",
                "credentials": {
                    "project_id": "my-project-123",
                    "service_account_key": '{"type": "service_account"}',
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "gcp"
        assert "Compute Engine" in data["services_discovered"]

    def test_azure_validation_success(self, mock_repo: AsyncMock) -> None:
        """Valid Azure credentials return success."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/validate-cloud",
            json={
                "provider": "azure",
                "credentials": {
                    "subscription_id": "sub-123",
                    "tenant_id": "tenant-123",
                    "client_id": "client-123",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_missing_credentials(self, mock_repo: AsyncMock) -> None:
        """Missing credential fields return success=false."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/validate-cloud",
            json={
                "provider": "aws",
                "credentials": {"access_key_id": "AKIA..."},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "secret_access_key" in data["message"]

    def test_invalid_provider(self, mock_repo: AsyncMock) -> None:
        """Invalid provider is rejected by Pydantic."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/validate-cloud",
            json={
                "provider": "digitalocean",
                "credentials": {},
            },
        )
        assert resp.status_code == 422


# ================================================================
# POST /onboarding/deploy-agent
# ================================================================


class TestDeployAgent:
    def test_deploy_agent_success(self, mock_repo: AsyncMock) -> None:
        """Valid agent type deploys and returns agent_id."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/deploy-agent",
            json={"agent_type": "investigation", "environment": "development"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["agent_type"] == "investigation"
        assert data["agent_id"].startswith("agt-")
        assert data["environment"] == "development"
        mock_repo.update_onboarding_step.assert_called_once()

    def test_deploy_invalid_agent_type(self, mock_repo: AsyncMock) -> None:
        """Invalid agent type returns 400."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/deploy-agent",
            json={"agent_type": "chaos_monkey", "environment": "production"},
        )
        assert resp.status_code == 400
        assert "Invalid agent type" in resp.json()["detail"]


# ================================================================
# POST /onboarding/trigger-demo
# ================================================================


class TestTriggerDemo:
    def test_trigger_demo_success(self, mock_repo: AsyncMock) -> None:
        """Demo trigger returns investigation_id and success."""
        client = _build_client(mock_repo)
        resp = client.post(
            "/api/v1/onboarding/trigger-demo",
            json={"scenario": "high_cpu_alert"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["investigation_id"].startswith("inv-demo-")
        assert data["scenario"] == "high_cpu_alert"
        mock_repo.update_onboarding_step.assert_called_once()

    def test_trigger_demo_default_scenario(self, mock_repo: AsyncMock) -> None:
        """Demo trigger with no body uses default scenario."""
        client = _build_client(mock_repo)
        resp = client.post("/api/v1/onboarding/trigger-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "high_cpu_alert"


# ================================================================
# Database unavailable
# ================================================================


class TestDatabaseUnavailable:
    def test_status_without_db_returns_503(self) -> None:
        """Endpoints return 503 when no repository is available."""
        app = _create_test_app()
        # Explicitly ensure no repository is set
        onboarding._repository = None
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 503
        assert "Database unavailable" in resp.json()["detail"]


# ================================================================
# Edge cases
# ================================================================


class TestEdgeCases:
    def test_step_order_preserved(self, mock_repo: AsyncMock) -> None:
        """Steps are returned in the canonical order regardless of DB order."""
        # Return steps in reverse DB order
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress(
                [
                    ("run_demo", "pending"),
                    ("create_org", "completed"),
                ]
            )
        )
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        step_names = [s["step_name"] for s in resp.json()["steps"]]
        assert step_names == [
            "create_org",
            "connect_cloud",
            "deploy_agent",
            "configure_playbook",
            "run_demo",
        ]

    def test_all_steps_completed_shows_completed(self, mock_repo: AsyncMock) -> None:
        """When all 5 steps are done, completed is True."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress(
                [
                    ("create_org", "completed"),
                    ("connect_cloud", "completed"),
                    ("deploy_agent", "completed"),
                    ("configure_playbook", "completed"),
                    ("run_demo", "completed"),
                ]
            )
        )
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    def test_mixed_completed_and_skipped(self, mock_repo: AsyncMock) -> None:
        """Mixed completed/skipped steps mark onboarding as done."""
        mock_repo.get_onboarding_progress = AsyncMock(
            return_value=_make_progress(
                [
                    ("create_org", "completed"),
                    ("connect_cloud", "skipped"),
                    ("deploy_agent", "completed"),
                    ("configure_playbook", "skipped"),
                    ("run_demo", "completed"),
                ]
            )
        )
        client = _build_client(mock_repo)
        resp = client.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        assert resp.json()["completed"] is True
